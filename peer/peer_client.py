"""
Peer Client with Enhanced Tkinter GUI for P2P File-Sharing System

Allows users to share and download files with real-time statistics.
Shows seed speed, download speed, and which peer transfers which file.

NO LOGIN SYSTEM - Uses persistent peer identity like qBittorrent
"""

import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, ttk
import threading
import socket
import json
import os
import logging
import sys
import hashlib
import uuid
import time
from datetime import datetime
from typing import Dict, Optional, List
from collections import defaultdict
import pickle

# Add shared module to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from shared.utils import SocketUtils, MessageBuilder, FileUtils
from shared.chunking import FileChunker
from peer_identity import PeerIdentity
from state_manager import StateManager

def get_local_ip():
    """Get local IP address for network communication."""
    try:
        # Create a socket to determine the local IP
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        # Connect to a public DNS server (doesn't actually send data)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
        return local_ip
    except Exception:
        return "127.0.0.1"

# Configuration
TRACKER_HOST = '192.168.0.202'#'192.168.10.82'
TRACKER_PORT = 5000
PEER_PORT_START = 6000  # Starting port for peer clients
PEER_PORT_END = 6100    # Ending port range
CHUNK_SIZE = 262144  # 256 KB
DOWNLOAD_TIMEOUT = 10.0
MAX_PARALLEL_DOWNLOADS = 5  # Maximum parallel chunk downloads

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def find_available_port(start_port=PEER_PORT_START, end_port=PEER_PORT_END):
    """Find an available port.
    
    Args:
        start_port: Start of port range
        end_port: End of port range
    
    Returns:
        Available port number
    """
    import random
    import time
    
    # Try random ports
    ports = list(range(start_port, end_port + 1))
    random.shuffle(ports)
    
    for port in ports:
        try:
            test_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            test_socket.bind(('0.0.0.0', port))
            actual_port = test_socket.getsockname()[1]
            test_socket.close()
            time.sleep(0.1)
            logger.info(f"Found available port: {port}")
            return actual_port
        except OSError:
            continue
    
    raise RuntimeError(f"No available ports in range {start_port}-{end_port}")


class TransferStats:
    """Track transfer statistics."""
    
    def __init__(self):
        self.lock = threading.RLock()
        self.transfers: Dict[str, Dict] = {}  # peer_id -> transfer info
        self.upload_bytes = 0
        self.download_bytes = 0
        self.upload_start_time = time.time()
        self.download_start_time = time.time()
    
    def add_upload(self, bytes_count: int, peer_id: str, file_id: str, chunk_idx: int):
        """Record uploaded bytes."""
        with self.lock:
            self.upload_bytes += bytes_count
            key = f"upload_{peer_id}_{file_id}_{chunk_idx}"
            self.transfers[key] = {
                "type": "upload",
                "peer": peer_id,
                "file_id": file_id,
                "chunk": chunk_idx,
                "bytes": bytes_count,
                "time": datetime.now().isoformat()
            }
    
    def add_download(self, bytes_count: int, peer_addr: str, file_id: str, chunk_idx: int):
        """Record downloaded bytes."""
        with self.lock:
            self.download_bytes += bytes_count
            key = f"download_{peer_addr}_{file_id}_{chunk_idx}"
            self.transfers[key] = {
                "type": "download",
                "peer": peer_addr,
                "file_id": file_id,
                "chunk": chunk_idx,
                "bytes": bytes_count,
                "time": datetime.now().isoformat()
            }
    
    def get_upload_speed(self) -> float:
        """Get current upload speed in KB/s."""
        with self.lock:
            elapsed = time.time() - self.upload_start_time
            if elapsed < 1:
                return 0
            return (self.upload_bytes / elapsed) / 1024
    
    def get_download_speed(self) -> float:
        """Get current download speed in KB/s."""
        with self.lock:
            elapsed = time.time() - self.download_start_time
            if elapsed < 1:
                return 0
            return (self.download_bytes / elapsed) / 1024
    
    def get_active_transfers(self) -> List[Dict]:
        """Get recent transfers (last 20)."""
        with self.lock:
            items = list(self.transfers.values())
            return items[-20:] if items else []


class PeerServer:
    """Server component of peer that serves chunks to other peers."""
    
    def __init__(self, port: int, chunks_directory: str, stats: TransferStats):
        self.port = port
        self.chunks_directory = chunks_directory
        self.server_socket = None
        self.running = False
        self.thread = None
        self.stats = stats
        self.active_connections = defaultdict(int)  # Track active connections per peer
    
    def start(self):
        """Start the peer server in a background thread."""
        self.thread = threading.Thread(target=self._run_server, daemon=True)
        self.thread.start()
    
    def _run_server(self):
        """Run the peer server."""
        try:
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_socket.bind(('0.0.0.0', self.port))
            self.server_socket.listen(5)
            self.running = True
            logger.info(f"Peer server started on port {self.port}")
            
            while self.running:
                try:
                    client_socket, client_address = self.server_socket.accept()
                    self.active_connections[client_address[0]] += 1
                    handler_thread = threading.Thread(
                        target=self._handle_chunk_request,
                        args=(client_socket, client_address),
                        daemon=True
                    )
                    handler_thread.start()
                except Exception as e:
                    if self.running:
                        logger.error(f"Error accepting connection: {e}")
        
        except Exception as e:
            logger.error(f"Peer server error: {e}")
        finally:
            if self.server_socket:
                self.server_socket.close()
    
    def _handle_chunk_request(self, client_socket: socket.socket, client_address):
        """Handle incoming chunk request from another peer."""
        peer_ip = client_address[0]
        try:
            message = SocketUtils.receive_message(client_socket, timeout=5.0)
            if not message:
                return
            
            if message.get("type") != "CHUNK_REQUEST":
                return
            
            file_id = message.get("file_id")
            chunk_index = message.get("chunk_index")
            
            # Construct chunk path
            file_chunk_dir = os.path.join(self.chunks_directory, file_id)
            chunk_filename = os.path.join(file_chunk_dir, f"chunk_{chunk_index}")
            
            if os.path.exists(chunk_filename):
                with open(chunk_filename, 'rb') as f:
                    chunk_data = f.read()
                
                # Send response header
                response = MessageBuilder.chunk_response_message(
                    file_id, chunk_index, len(chunk_data), "success"
                )
                if SocketUtils.send_message(client_socket, response):
                    # Send chunk data
                    SocketUtils.send_chunk_data(client_socket, chunk_data)
                    
                    # Record statistics
                    self.stats.add_upload(len(chunk_data), peer_ip, file_id, chunk_index)
                    
                    logger.info(f"Served chunk {chunk_index} of file {file_id} to {peer_ip}")
            else:
                response = MessageBuilder.chunk_response_message(
                    file_id, chunk_index, 0, "not_found"
                )
                SocketUtils.send_message(client_socket, response)
                logger.warning(f"Chunk not found: {chunk_filename}")
        
        except Exception as e:
            logger.error(f"Error handling chunk request: {e}")
        finally:
            try:
                client_socket.close()
                self.active_connections[peer_ip] = max(0, self.active_connections[peer_ip] - 1)
            except:
                pass
    
    def stop(self):
        """Stop the peer server."""
        self.running = False
        if self.server_socket:
            try:
                self.server_socket.close()
            except:
                pass


class PeerClient:
    """GUI client for P2P file sharing with enhanced statistics."""
    
    def __init__(self, root: tk.Tk):
        self.root = root
        
        # Initialize persistent peer identity (like qBittorrent)
        self.identity = PeerIdentity()
        self.peer_id = self.identity.get_peer_id()
        
        self.root.title(f"P2P File Sharing Client - Peer: {self.peer_id[:12]}")
        self.root.geometry("1300x850")
        
        # Initialize state manager first (to load saved port)
        self.state_mgr = StateManager(self.identity.get_state_file(), self.peer_id)
        
        # Get local IP for network communication
        self.local_ip = get_local_ip()
        logger.info(f"Local IP address: {self.local_ip}")
        
        # Get or assign port (reuse saved port if available)
        saved_port = self.state_mgr.state.get('peer_metadata', {}).get('port')
        if saved_port:
            # Try to use saved port
            try:
                test_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                test_socket.bind(('0.0.0.0', saved_port))
                test_socket.close()
                self.peer_port = saved_port
                logger.info(f"Reusing saved port {self.peer_port} for peer {self.peer_id}")
            except OSError:
                # Saved port not available, find new one
                self.peer_port = find_available_port()
                logger.info(f"Saved port busy, assigned new port {self.peer_port}")
        else:
            # First run, find available port
            self.peer_port = find_available_port()
            logger.info(f"Assigned port {self.peer_port} to peer {self.peer_id}")
        
        # Save port to state
        self.state_mgr.state['peer_metadata']['port'] = self.peer_port
        self.state_mgr.dirty = True
        
        self.tracker_host = TRACKER_HOST
        self.tracker_port = TRACKER_PORT
        
        # Use identity directories
        self.shared_directory = self.identity.get_uploads_dir()
        self.downloads_directory = self.identity.get_downloads_dir()
        self.chunks_directory = os.path.join(self.shared_directory, "chunks")
        
        # Create directories
        os.makedirs(self.chunks_directory, exist_ok=True)
        
        # Statistics
        self.stats = TransferStats()
        
        # Start peer server
        self.peer_server = PeerServer(self.peer_port, self.chunks_directory, self.stats)
        self.peer_server.start()
        
        # File chunker
        self.chunker = FileChunker(CHUNK_SIZE)
        
        # Active downloads
        self.active_downloads: Dict[str, Dict] = {}
        
        # Progress tracking for UI
        self.current_download_progress = None  # Will hold progress bar reference
        self.current_upload_progress = None
        
        # Peer counts cache
        self.peer_counts_cache: Dict[str, Dict] = {}  # file_id -> {seeders, leechers}
        
        # Pause control for downloads
        self.download_paused = {}  # file_id -> True/False
        self.download_cancelled = {}  # file_id -> True/False
        
        # Load shared files and download history from state
        self.shared_files: Dict[str, Dict] = {}
        self.download_history: List[Dict] = []
        self._load_from_state()
        
        self._setup_ui()
        self._log(f"Persistent Peer ID: {self.peer_id}")
        self._log(f"Peer Server running on port {self.peer_port}")
        self._log(f"Loaded {len(self.shared_files)} shared files and {len(self.download_history)} downloads")
        
        # Re-register previously shared files with tracker
        self._re_register_shared_files()
        
        # Start statistics update thread
        self.update_thread = threading.Thread(target=self._update_stats, daemon=True)
        self.update_thread.start()
    
    def _setup_ui(self):
        """Setup the advanced user interface with tabs."""
        # Create notebook (tabs)
        notebook = ttk.Notebook(self.root)
        notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Tab 1: Dashboard
        self._setup_dashboard_tab(notebook)
        
        # Tab 2: Share Files
        self._setup_share_tab(notebook)
        
        # Tab 3: Download Files
        self._setup_download_tab(notebook)
        
        # Tab 4: Statistics
        self._setup_stats_tab(notebook)
        
        # Tab 5: Settings
        self._setup_settings_tab(notebook)
    
    def _setup_dashboard_tab(self, notebook):
        """Setup elegant dashboard like uTorrent."""
        dashboard_frame = ttk.Frame(notebook)
        notebook.add(dashboard_frame, text="Dashboard")
        
        # Main content area
        main_area = ttk.Frame(dashboard_frame)
        main_area.pack(fill=tk.BOTH, expand=True, padx=0, pady=0)
        
        # Statistics panel at top
        stats_panel = tk.Frame(main_area, bg="#ffffff", height=80, relief=tk.RIDGE, bd=1)
        stats_panel.pack(fill=tk.X, side=tk.TOP, padx=5, pady=5)
        stats_panel.pack_propagate(False)
        
        # Left side - Peer Info
        left_info = tk.Frame(stats_panel, bg="#ffffff")
        left_info.pack(side=tk.LEFT, fill=tk.Y, padx=15, pady=10)
        
        tk.Label(left_info, text="Peer ID:", bg="#ffffff", fg="#666666", 
                font=("Segoe UI", 8)).pack(anchor=tk.W)
        tk.Label(left_info, text=self.peer_id[:16], bg="#ffffff", fg="#0066cc", 
                font=("Segoe UI", 10, "bold")).pack(anchor=tk.W)
        
        tk.Label(left_info, text=f"Port: {self.peer_port}", bg="#ffffff", fg="#666666", 
                font=("Segoe UI", 8)).pack(anchor=tk.W, pady=(5,0))
        
        # Center - Upload Stats
        upload_stats = tk.Frame(stats_panel, bg="#ffffff")
        upload_stats.pack(side=tk.LEFT, fill=tk.Y, padx=20, pady=10)
        
        tk.Label(upload_stats, text="UPLOADED", bg="#ffffff", fg="#666666", 
                font=("Segoe UI", 8)).pack(anchor=tk.W)
        
        self.total_shared_var = tk.StringVar(value="0")
        files_up_label = tk.Label(upload_stats, textvariable=self.total_shared_var, bg="#ffffff", 
                                 fg="#008000", font=("Segoe UI", 18, "bold"))
        files_up_label.pack(anchor=tk.W)
        tk.Label(upload_stats, text="files", bg="#ffffff", fg="#666666", 
                font=("Segoe UI", 8)).pack(anchor=tk.W)
        
        self.total_upload_data_var = tk.StringVar(value="0 MB")
        tk.Label(upload_stats, textvariable=self.total_upload_data_var, bg="#ffffff", 
                fg="#008000", font=("Segoe UI", 9, "bold")).pack(anchor=tk.W, pady=(3,0))
        
        # Center Right - Download Stats  
        download_stats = tk.Frame(stats_panel, bg="#ffffff")
        download_stats.pack(side=tk.LEFT, fill=tk.Y, padx=20, pady=10)
        
        tk.Label(download_stats, text="DOWNLOADED", bg="#ffffff", fg="#666666", 
                font=("Segoe UI", 8)).pack(anchor=tk.W)
        
        self.total_downloaded_var = tk.StringVar(value="0")
        files_down_label = tk.Label(download_stats, textvariable=self.total_downloaded_var, bg="#ffffff", 
                                   fg="#0066cc", font=("Segoe UI", 18, "bold"))
        files_down_label.pack(anchor=tk.W)
        tk.Label(download_stats, text="files", bg="#ffffff", fg="#666666", 
                font=("Segoe UI", 8)).pack(anchor=tk.W)
        
        self.total_download_data_var = tk.StringVar(value="0 MB")
        tk.Label(download_stats, textvariable=self.total_download_data_var, bg="#ffffff", 
                fg="#0066cc", font=("Segoe UI", 9, "bold")).pack(anchor=tk.W, pady=(3,0))
        
        # Right side - Current Speeds (fixed width to prevent overlap)
        speed_stats = tk.Frame(stats_panel, bg="#ffffff", width=160)
        speed_stats.pack(side=tk.RIGHT, fill=tk.Y, padx=10, pady=10)
        speed_stats.pack_propagate(False)
        
        tk.Label(speed_stats, text="CURRENT SPEEDS", bg="#ffffff", fg="#666666", 
                font=("Segoe UI", 8)).pack(anchor=tk.W, pady=(0,5))
        
        speed_frame = tk.Frame(speed_stats, bg="#ffffff")
        speed_frame.pack(anchor=tk.W, pady=(0,2))
        
        tk.Label(speed_frame, text="▲", bg="#ffffff", fg="#008000", 
                font=("Segoe UI", 9)).pack(side=tk.LEFT, padx=(0,3))
        self.upload_speed_display = tk.StringVar(value="0.0 KB/s")
        tk.Label(speed_frame, textvariable=self.upload_speed_display, bg="#ffffff", 
                fg="#008000", font=("Segoe UI", 9, "bold"), width=13, anchor=tk.W).pack(side=tk.LEFT)
        
        speed_frame2 = tk.Frame(speed_stats, bg="#ffffff")
        speed_frame2.pack(anchor=tk.W, pady=(2,0))
        
        tk.Label(speed_frame2, text="▼", bg="#ffffff", fg="#0066cc", 
                font=("Segoe UI", 9)).pack(side=tk.LEFT, padx=(0,3))
        self.download_speed_display = tk.StringVar(value="0.0 KB/s")
        tk.Label(speed_frame2, textvariable=self.download_speed_display, bg="#ffffff", 
                fg="#0066cc", font=("Segoe UI", 9, "bold"), width=13, anchor=tk.W).pack(side=tk.LEFT)
        
        # Separator
        separator = tk.Frame(main_area, bg="#cccccc", height=1)
        separator.pack(fill=tk.X, padx=5)
        
        # Toolbar
        toolbar = tk.Frame(main_area, bg="#f0f0f0", height=30)
        toolbar.pack(fill=tk.X, side=tk.TOP)
        
        toolbar_label = tk.Label(toolbar, text="All Torrents", font=("Segoe UI", 9, "bold"), 
                                bg="#f0f0f0", fg="#333333")
        toolbar_label.pack(side=tk.LEFT, padx=10, pady=5)
        
        # Main torrent list
        list_frame = ttk.Frame(main_area)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=0, pady=0)
        
        columns = ("Name", "Size", "Done", "Status", "Seeds", "Peers", "Down Speed", "Up Speed")
        self.dashboard_tree = ttk.Treeview(list_frame, columns=columns, show="headings", selectmode="browse", height=15)
        
        # Column configuration
        self.dashboard_tree.column("Name", width=280, anchor=tk.W)
        self.dashboard_tree.column("Size", width=80, anchor=tk.E)
        self.dashboard_tree.column("Done", width=60, anchor=tk.E)
        self.dashboard_tree.column("Status", width=100, anchor=tk.W)
        self.dashboard_tree.column("Seeds", width=50, anchor=tk.CENTER)
        self.dashboard_tree.column("Peers", width=50, anchor=tk.CENTER)
        self.dashboard_tree.column("Down Speed", width=90, anchor=tk.E)
        self.dashboard_tree.column("Up Speed", width=90, anchor=tk.E)
        
        # Headers
        for col in columns:
            self.dashboard_tree.heading(col, text=col, anchor=tk.W if col == "Name" or col == "Status" else tk.CENTER)
        
        # Scrollbar
        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.dashboard_tree.yview)
        self.dashboard_tree.configure(yscroll=scrollbar.set)
        
        self.dashboard_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Configure colors for rows
        self.dashboard_tree.tag_configure("seeding", foreground="#008000")
        self.dashboard_tree.tag_configure("downloading", foreground="#0066cc")
        self.dashboard_tree.tag_configure("paused", foreground="#999999")
        self.dashboard_tree.tag_configure("error", foreground="#cc0000")
        
        # Status bar at bottom (like uTorrent)
        status_bar = tk.Frame(dashboard_frame, bg="#e8e8e8", height=25, relief=tk.SUNKEN, bd=1)
        status_bar.pack(fill=tk.X, side=tk.BOTTOM)
        
        self.upload_speed_var = tk.StringVar(value="▲ 0.0 KB/s")
        self.download_speed_var = tk.StringVar(value="▼ 0.0 KB/s")
        
        tk.Label(status_bar, textvariable=self.download_speed_var, bg="#e8e8e8", 
                fg="#0066cc", font=("Segoe UI", 8)).pack(side=tk.LEFT, padx=10)
        
        tk.Label(status_bar, textvariable=self.upload_speed_var, bg="#e8e8e8", 
                fg="#008000", font=("Segoe UI", 8)).pack(side=tk.LEFT, padx=10)
        
        tk.Label(status_bar, text=f"Peer: {self.peer_id[:12]}", bg="#e8e8e8", 
                fg="#555555", font=("Segoe UI", 8)).pack(side=tk.RIGHT, padx=10)
    
    def _setup_share_tab(self, notebook):
        """Setup file sharing tab with modern layout."""
        share_frame = ttk.Frame(notebook)
        notebook.add(share_frame, text="Share Files")
        
        container = ttk.Frame(share_frame)
        container.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Toolbar
        toolbar = tk.Frame(container, bg="#f0f0f0", height=40)
        toolbar.pack(fill=tk.X, pady=(0, 0))
        
        ttk.Button(toolbar, text="Add File", command=self._select_file_to_share, 
                  width=12).pack(side=tk.LEFT, padx=5, pady=5)
        ttk.Button(toolbar, text="Share", command=self._share_file,
                  width=12).pack(side=tk.LEFT, padx=5, pady=5)
        ttk.Button(toolbar, text="Remove", command=self._remove_shared_file,
                  width=12).pack(side=tk.LEFT, padx=5, pady=5)
        
        self.share_file_var = tk.StringVar(value="No file selected")
        tk.Label(toolbar, textvariable=self.share_file_var, bg="#f0f0f0",
                fg="#555555", font=("Segoe UI", 9)).pack(side=tk.LEFT, padx=20)
        
        # Shared files list with enhanced columns
        shared_frame = ttk.Frame(container)
        shared_frame.pack(fill=tk.BOTH, expand=True, pady=0)
        
        columns = ("Filename", "File ID", "Size", "Progress", "Role", "Seeders", "Leechers", "Upload Speed", "Status")
        self.shared_tree = ttk.Treeview(shared_frame, columns=columns, height=12, show="headings")
        
        self.shared_tree.column("Filename", width=200, anchor=tk.W)
        self.shared_tree.column("File ID", width=85, anchor=tk.W)
        self.shared_tree.column("Size", width=80, anchor=tk.CENTER)
        self.shared_tree.column("Progress", width=80, anchor=tk.CENTER)
        self.shared_tree.column("Role", width=80, anchor=tk.CENTER)
        self.shared_tree.column("Seeders", width=70, anchor=tk.CENTER)
        self.shared_tree.column("Leechers", width=70, anchor=tk.CENTER)
        self.shared_tree.column("Upload Speed", width=110, anchor=tk.CENTER)
        self.shared_tree.column("Status", width=100, anchor=tk.CENTER)
        
        for col in columns:
            self.shared_tree.heading(col, text=col)
        
        scrollbar = ttk.Scrollbar(shared_frame, orient=tk.VERTICAL, command=self.shared_tree.yview)
        self.shared_tree.configure(yscroll=scrollbar.set)
        
        self.shared_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.shared_tree.tag_configure("seeding", foreground="#008000")
        self.shared_tree.tag_configure("leeching", foreground="#0066cc")
        self.shared_tree.tag_configure("active", foreground="#008000")
    
    def _setup_download_tab(self, notebook):
        """Setup file download tab with modern search and active downloads."""
        download_frame = ttk.Frame(notebook)
        notebook.add(download_frame, text="Download")
        
        container = ttk.Frame(download_frame)
        container.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # === SEARCH SECTION ===
        search_bar = tk.Frame(container, bg="#f0f0f0", height=35)
        search_bar.pack(fill=tk.X, pady=(0, 0))
        
        ttk.Label(search_bar, text="Search:", background="#f0f0f0").pack(side=tk.LEFT, padx=5)
        
        self.search_mode_var = tk.StringVar(value="filename")
        ttk.Radiobutton(search_bar, text="Name", variable=self.search_mode_var, 
                       value="filename", command=self._on_search_mode_change).pack(side=tk.LEFT, padx=3)
        ttk.Radiobutton(search_bar, text="ID", variable=self.search_mode_var, 
                       value="file_id", command=self._on_search_mode_change).pack(side=tk.LEFT, padx=3)
        
        self.file_id_var = tk.StringVar()
        search_entry = ttk.Entry(search_bar, textvariable=self.file_id_var, width=40)
        search_entry.pack(side=tk.LEFT, padx=5)
        ttk.Button(search_bar, text="Search", command=self._search_file, width=10).pack(side=tk.LEFT, padx=5)
        ttk.Button(search_bar, text="Download Selected", command=self._download_selected_from_results, width=18).pack(side=tk.LEFT, padx=5)
        
        # === SEARCH RESULTS TABLE ===
        results_label = tk.Label(container, text="Search Results", bg="#f0f0f0", fg="#333333", 
                                font=("Segoe UI", 9, "bold"), anchor=tk.W, height=2)
        results_label.pack(fill=tk.X)
        
        results_frame = ttk.Frame(container)
        results_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 5))
        
        # Results treeview
        columns = ("File Name", "File ID", "Size", "Seeders", "Leechers", "Availability")
        self.search_results_tree = ttk.Treeview(results_frame, columns=columns, height=6, show="headings")
        
        self.search_results_tree.column("File Name", width=220, anchor=tk.W)
        self.search_results_tree.column("File ID", width=85, anchor=tk.W)
        self.search_results_tree.column("Size", width=90, anchor=tk.CENTER)
        self.search_results_tree.column("Seeders", width=70, anchor=tk.CENTER)
        self.search_results_tree.column("Leechers", width=70, anchor=tk.CENTER)
        self.search_results_tree.column("Availability", width=100, anchor=tk.CENTER)
        
        for col in columns:
            self.search_results_tree.heading(col, text=col)
        
        scrollbar_results = ttk.Scrollbar(results_frame, orient=tk.VERTICAL, command=self.search_results_tree.yview)
        self.search_results_tree.configure(yscroll=scrollbar_results.set)
        
        self.search_results_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar_results.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.search_results_tree.tag_configure("available", foreground="#008000")
        self.search_results_tree.tag_configure("limited", foreground="orange")
        self.search_results_tree.tag_configure("unavailable", foreground="red")
        
        # === ACTIVE DOWNLOADS ===
        active_label = tk.Label(container, text="Active Downloads", bg="#f0f0f0", fg="#333333", 
                               font=("Segoe UI", 9, "bold"), anchor=tk.W, height=2)
        active_label.pack(fill=tk.X)
        
        active_frame = ttk.Frame(container)
        active_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 5))
        
        # Buttons for active downloads
        btn_frame = tk.Frame(active_frame, bg="#ffffff")
        btn_frame.pack(fill=tk.X, pady=(2, 2))
        ttk.Button(btn_frame, text="⏸ Pause", command=self._pause_download, width=12).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="▶ Resume", command=self._resume_download, width=12).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="✖ Cancel", command=self._cancel_download, width=12).pack(side=tk.LEFT, padx=5)
        
        columns_active = ("Name", "Size", "Progress", "Status", "Seeds", "Peers", "Down Speed", "Up Speed", "ETA")
        self.active_downloads_tree = ttk.Treeview(active_frame, columns=columns_active, height=5, show="headings")
        
        self.active_downloads_tree.column("Name", width=180, anchor=tk.W)
        self.active_downloads_tree.column("Size", width=70, anchor=tk.CENTER)
        self.active_downloads_tree.column("Progress", width=70, anchor=tk.CENTER)
        self.active_downloads_tree.column("Status", width=100, anchor=tk.CENTER)
        self.active_downloads_tree.column("Seeds", width=50, anchor=tk.CENTER)
        self.active_downloads_tree.column("Peers", width=50, anchor=tk.CENTER)
        self.active_downloads_tree.column("Down Speed", width=90, anchor=tk.CENTER)
        self.active_downloads_tree.column("Up Speed", width=90, anchor=tk.CENTER)
        self.active_downloads_tree.column("ETA", width=80, anchor=tk.CENTER)
        
        for col in columns_active:
            self.active_downloads_tree.heading(col, text=col)
        
        scrollbar_active = ttk.Scrollbar(active_frame, orient=tk.VERTICAL, command=self.active_downloads_tree.yview)
        self.active_downloads_tree.configure(yscroll=scrollbar_active.set)
        
        self.active_downloads_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar_active.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.active_downloads_tree.tag_configure("downloading", foreground="#0066cc")
        self.active_downloads_tree.tag_configure("paused", foreground="#999999")
        self.active_downloads_tree.tag_configure("completed", foreground="#008000")
        self.active_downloads_tree.tag_configure("error", foreground="#cc0000")
        
        # === DOWNLOAD HISTORY ===
        history_label = tk.Label(container, text="Download History", bg="#f0f0f0", fg="#333333", 
                                font=("Segoe UI", 9, "bold"), anchor=tk.W, height=2)
        history_label.pack(fill=tk.X)
        
        history_container = ttk.Frame(container)
        history_container.pack(fill=tk.BOTH, expand=True, pady=(0, 5))
        
        # Search box
        search_box_frame = ttk.Frame(history_container)
        search_box_frame.pack(fill=tk.X, pady=(0, 5))
        
        ttk.Label(search_box_frame, text="Filter:", font=("Arial", 9)).pack(side=tk.LEFT, padx=5)
        self.history_search_var = tk.StringVar()
        self.history_search_var.trace("w", self._filter_download_history)
        ttk.Entry(search_box_frame, textvariable=self.history_search_var, width=40).pack(side=tk.LEFT, padx=5)
        ttk.Button(search_box_frame, text="Clear", command=self._clear_history_search).pack(side=tk.LEFT, padx=5)
        
        # History tree with enhanced columns
        columns_history = ("Name", "Size", "Progress", "Status", "Seeds", "Peers", "Down Speed", "Up Speed")
        self.history_tree = ttk.Treeview(history_container, columns=columns_history, height=6, show="headings")
        
        self.history_tree.column("Name", width=220, anchor=tk.W)
        self.history_tree.column("Size", width=80, anchor=tk.CENTER)
        self.history_tree.column("Progress", width=80, anchor=tk.CENTER)
        self.history_tree.column("Status", width=100, anchor=tk.CENTER)
        self.history_tree.column("Seeds", width=60, anchor=tk.CENTER)
        self.history_tree.column("Peers", width=60, anchor=tk.CENTER)
        self.history_tree.column("Down Speed", width=100, anchor=tk.CENTER)
        self.history_tree.column("Up Speed", width=100, anchor=tk.CENTER)
        
        for col in columns_history:
            self.history_tree.heading(col, text=col)
        
        scrollbar_history = ttk.Scrollbar(history_container, orient=tk.VERTICAL, command=self.history_tree.yview)
        self.history_tree.configure(yscroll=scrollbar_history.set)
        
        self.history_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar_history.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.history_tree.tag_configure("completed", foreground="#008000")
        self.history_tree.tag_configure("failed", foreground="#cc0000")
        self.history_tree.tag_configure("downloading", foreground="#0066cc")
    
    def _setup_stats_tab(self, notebook):
        """Setup statistics tab with modern layout."""
        stats_frame = ttk.Frame(notebook)
        notebook.add(stats_frame, text="Statistics")
        
        container = ttk.Frame(stats_frame)
        container.pack(fill=tk.BOTH, expand=True, padx=0, pady=0)
        
        # Stats bar at top
        stats_bar = tk.Frame(container, bg="#f0f0f0", height=40)
        stats_bar.pack(fill=tk.X)
        
        stats_grid = ttk.Frame(stats_bar)
        stats_grid.pack(expand=True)
        
        # Upload Speed
        ttk.Label(stats_grid, text="Upload:", background="#f0f0f0", foreground="#555555").grid(row=0, column=0, padx=10, pady=8, sticky=tk.E)
        self.total_upload_var = tk.StringVar(value="0 KB/s")
        tk.Label(stats_grid, textvariable=self.total_upload_var, background="#f0f0f0",
                foreground="#008000", font=("Segoe UI", 10, "bold")).grid(row=0, column=1, padx=5, pady=8, sticky=tk.W)
        
        # Download Speed  
        ttk.Label(stats_grid, text="Download:", background="#f0f0f0", foreground="#555555").grid(row=0, column=2, padx=10, pady=8, sticky=tk.E)
        self.total_download_var = tk.StringVar(value="0 KB/s")
        tk.Label(stats_grid, textvariable=self.total_download_var, background="#f0f0f0",
                foreground="#0066cc", font=("Segoe UI", 10, "bold")).grid(row=0, column=3, padx=5, pady=8, sticky=tk.W)
        
        # Transfer log label
        log_label = tk.Label(container, text="Recent Transfers", bg="#f0f0f0", fg="#333333",
                            font=("Segoe UI", 9, "bold"), anchor=tk.W, height=2)
        log_label.pack(fill=tk.X)
        
        # Transfers log
        log_frame = ttk.Frame(container)
        log_frame.pack(fill=tk.BOTH, expand=True, pady=0)
        
        columns = ("Time", "Type", "Peer", "File", "Chunk", "Size")
        self.stats_tree = ttk.Treeview(log_frame, columns=columns, height=20, show="headings")
        
        self.stats_tree.column("Time", width=100, anchor=tk.W)
        self.stats_tree.column("Type", width=80, anchor=tk.CENTER)
        self.stats_tree.column("Peer", width=150, anchor=tk.W)
        self.stats_tree.column("File", width=120, anchor=tk.W)
        self.stats_tree.column("Chunk", width=70, anchor=tk.CENTER)
        self.stats_tree.column("Size", width=100, anchor=tk.E)
        
        for col in columns:
            self.stats_tree.heading(col, text=col)
        
        scrollbar = ttk.Scrollbar(log_frame, orient=tk.VERTICAL, command=self.stats_tree.yview)
        self.stats_tree.configure(yscroll=scrollbar.set)
        
        self.stats_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.stats_tree.tag_configure("upload", foreground="#008000")
        self.stats_tree.tag_configure("download", foreground="#0066cc")
    
    def _setup_settings_tab(self, notebook):
        """Setup settings tab with modern layout."""
        settings_frame = ttk.Frame(notebook)
        notebook.add(settings_frame, text="Settings")
        
        container = ttk.Frame(settings_frame)
        container.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Tracker configuration
        tracker_frame = ttk.LabelFrame(container, text="Tracker Configuration", padding=10)
        tracker_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(tracker_frame, text="Tracker Host:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        self.tracker_host_var = tk.StringVar(value=self.tracker_host)
        ttk.Entry(tracker_frame, textvariable=self.tracker_host_var, width=30).grid(row=0, column=1, padx=5, pady=5)
        
        ttk.Label(tracker_frame, text="Tracker Port:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        self.tracker_port_var = tk.StringVar(value=str(self.tracker_port))
        ttk.Entry(tracker_frame, textvariable=self.tracker_port_var, width=30).grid(row=1, column=1, padx=5, pady=5)
        
        # Control buttons
        btn_frame = ttk.Frame(container)
        btn_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Button(btn_frame, text="📂 Open Downloads Folder", command=self._open_downloads).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="📂 Open Shared Folder", command=self._open_shared).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="🗑️ Clear Log", command=self._clear_log).pack(side=tk.LEFT, padx=5)
        
        # Status log
        log_frame = ttk.LabelFrame(container, text="Status Log", padding=10)
        log_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 5))
        
        self.log_text = scrolledtext.ScrolledText(log_frame, height=18, wrap=tk.WORD, state=tk.DISABLED)
        self.log_text.pack(fill=tk.BOTH, expand=True)
    
    def _log(self, message: str):
        """Add a message to the log."""
        self.log_text.config(state=tk.NORMAL)
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.insert(tk.END, f"[{timestamp}] {message}\n")
        self.log_text.see(tk.END)
        self.log_text.config(state=tk.DISABLED)
        logger.info(message)
    
    def _load_from_state(self):
        """Load shared files and download history from state manager."""
        try:
            torrents = self.state_mgr.get_all_torrents()
            
            # Load shared files (seeding torrents)
            for info_hash, torrent in torrents.items():
                # Check if chunks still exist
                file_chunk_dir = os.path.join(self.chunks_directory, info_hash)
                
                if torrent['status'] in ['seeding', 'downloading']:
                    # Only load if chunks exist OR if it's a new download
                    if os.path.exists(file_chunk_dir) or torrent['status'] == 'downloading':
                        self.shared_files[info_hash] = {
                            'filename': torrent['filename'],
                            'chunks': torrent['total_pieces'],
                            'date_shared': torrent.get('added_at', ''),
                            'completed_pieces': len(torrent['completed_pieces'])
                        }
                    else:
                        logger.warning(f"Chunks missing for {torrent['filename']}, skipping")
            
            # Load download history from state
            self.download_history = self.state_mgr.state.get('download_history', [])
            
            logger.info(f"Loaded {len(self.shared_files)} shared files and {len(self.download_history)} downloads from state")
        except Exception as e:
            logger.error(f"Failed to load state: {e}")
    
    def _save_state(self):
        """Save current state (just trigger state manager save)."""
        try:
            # State manager auto-saves every 30 seconds
            # Force a save now
            self.state_mgr.save()
            logger.debug("State saved")
        except Exception as e:
            logger.error(f"Failed to save state: {e}")
    
    def _re_register_shared_files(self):
        """Re-register all previously shared files with the tracker."""
        if not self.shared_files:
            return
        
        self._log(f"Re-registering {len(self.shared_files)} previously shared files...")
        
        for file_id, file_info in list(self.shared_files.items()):
            try:
                # Check if chunks still exist
                file_chunk_dir = os.path.join(self.chunks_directory, file_id)
                if not os.path.exists(file_chunk_dir):
                    self._log(f"⚠️ Chunks missing for {file_info.get('filename', file_id)}")
                    # Don't delete - just skip re-registration
                    continue
                
                # Re-register with tracker
                filename = file_info.get("filename", "unknown")
                num_chunks = file_info.get("chunks", 0)
                
                if self._register_file(file_id, filename, num_chunks):
                    self._log(f"✓ Re-registered: {filename} (ID: {file_id[:8]})")
                    # Announce started to tracker
                    self._announce_to_tracker("started", file_id)
                else:
                    self._log(f"⚠️ Failed to re-register: {filename}")
                    
            except Exception as e:
                logger.error(f"Error re-registering file {file_id}: {e}")
        
        # Update UI
        self._update_shared_files()
        self._filter_download_history()
    
    def _clear_log(self):
        """Clear the log."""
        self.log_text.config(state=tk.NORMAL)
        self.log_text.delete(1.0, tk.END)
        self.log_text.config(state=tk.DISABLED)
    
    def _open_downloads(self):
        """Open downloads folder."""
        try:
            import subprocess
            import sys
            
            downloads_path = os.path.abspath(self.downloads_directory)
            if sys.platform == "win32":
                os.startfile(downloads_path)
            elif sys.platform == "darwin":
                subprocess.Popen(["open", downloads_path])
            else:
                subprocess.Popen(["xdg-open", downloads_path])
            
            self._log(f"Opened downloads folder: {downloads_path}")
        except Exception as e:
            messagebox.showerror("Error", f"Could not open folder: {e}")
    
    def _open_shared(self):
        """Open shared folder."""
        try:
            import subprocess
            import sys
            
            shared_path = os.path.abspath(self.shared_directory)
            if sys.platform == "win32":
                os.startfile(shared_path)
            elif sys.platform == "darwin":
                subprocess.Popen(["open", shared_path])
            else:
                subprocess.Popen(["xdg-open", shared_path])
            
            self._log(f"Opened shared folder: {shared_path}")
        except Exception as e:
            messagebox.showerror("Error", f"Could not open folder: {e}")
    
    def _search_file(self):
        """Search for a file on tracker by filename or file ID."""
        search_term = self.file_id_var.get().strip()
        search_mode = self.search_mode_var.get()
        
        if not search_term:
            messagebox.showinfo("Input Required", f"Please enter a {'file name' if search_mode == 'filename' else 'file ID'} to search")
            return
        
        def do_search():
            try:
                # Clear previous results
                for item in self.search_results_tree.get_children():
                    self.search_results_tree.delete(item)
                
                if search_mode == "filename":
                    self._log(f"Searching for files matching: {search_term}")
                    search_results = self._search_by_filename(search_term)
                    
                    if search_results and search_results.get('files'):
                        files = search_results.get('files', [])
                        self._log(f"Found {len(files)} file(s) matching '{search_term}'")
                        
                        for file_info in files:
                            file_id = file_info.get('file_id', 'N/A')
                            filename = file_info.get('filename', 'N/A')
                            num_chunks = file_info.get('num_chunks', 0)
                            peers = file_info.get('peers', [])
                            num_peers = len(peers)
                            
                            # Calculate size estimate (chunks * CHUNK_SIZE)
                            size_bytes = num_chunks * CHUNK_SIZE
                            if size_bytes > 1024*1024:
                                size_str = f"{size_bytes/1024/1024:.1f} MB"
                            else:
                                size_str = f"{size_bytes/1024:.1f} KB"
                            
                            # Determine availability
                            if num_peers >= 3:
                                availability = "High"
                                tag = "available"
                            elif num_peers >= 1:
                                availability = "Medium"
                                tag = "limited"
                            else:
                                availability = "None"
                                tag = "unavailable"
                            
                            # Insert into tree with file_id as iid
                            self.search_results_tree.insert("", "end", iid=file_id, values=(
                                filename,
                                file_id[:8] + "...",
                                size_str,
                                f"🟢 {num_peers}",
                                "0",  # Leechers (not tracked yet)
                                availability
                            ), tags=(tag,))
                    else:
                        self._log(f"No files found matching '{search_term}'")
                        messagebox.showinfo("No Results", f"No files found matching '{search_term}'")
                    
                else:  # search by file_id
                    self._log(f"Searching for file: {search_term}")
                    file_info = self._query_tracker(search_term)
                    
                    if file_info:
                        file_id = file_info.get('file_id', search_term)
                        filename = file_info.get('filename', 'N/A')
                        num_chunks = file_info.get('num_chunks', 0)
                        peers = file_info.get('peers', [])
                        num_peers = len(peers)
                        
                        # Calculate size
                        size_bytes = num_chunks * CHUNK_SIZE
                        if size_bytes > 1024*1024:
                            size_str = f"{size_bytes/1024/1024:.1f} MB"
                        else:
                            size_str = f"{size_bytes/1024:.1f} KB"
                        
                        # Determine availability
                        if num_peers >= 3:
                            availability = "High"
                            tag = "available"
                        elif num_peers >= 1:
                            availability = "Medium"
                            tag = "limited"
                        else:
                            availability = "None"
                            tag = "unavailable"
                        
                        self.search_results_tree.insert("", "end", iid=file_id, values=(
                            filename,
                            file_id[:8] + "...",
                            size_str,
                            f"🟢 {num_peers}",
                            "0",
                            availability
                        ), tags=(tag,))
                        
                        self._log(f"Found file with {num_peers} peers")
                    else:
                        self._log("File not found")
                        messagebox.showinfo("Not Found", "File not found on tracker")
            
            except Exception as e:
                self._log(f"Search error: {e}")
                messagebox.showerror("Search Error", str(e))
        
        thread = threading.Thread(target=do_search, daemon=True)
        thread.start()
    
    def _pause_download(self):
        """Pause the selected active download."""
        selected = self.active_downloads_tree.selection()
        if not selected:
            messagebox.showwarning("No Selection", "Please select a download to pause")
            return
        
        file_id = selected[0]
        self.download_paused[file_id] = True
        self._log(f"Paused download: {file_id[:8]}")
        
        # Update status in tree
        try:
            item = self.active_downloads_tree.item(file_id)
            values = list(item['values'])
            values[3] = "⏸ Paused"
            if len(values) == 8:  # Old format without ETA
                values.append("-")
            else:
                values[8] = "-"  # No ETA when paused
            self.active_downloads_tree.item(file_id, values=values, tags=("paused",))
        except:
            pass
    
    def _resume_download(self):
        """Resume the selected paused download."""
        selected = self.active_downloads_tree.selection()
        if not selected:
            messagebox.showwarning("No Selection", "Please select a download to resume")
            return
        
        file_id = selected[0]
        if file_id in self.download_paused:
            self.download_paused[file_id] = False
            self._log(f"Resumed download: {file_id[:8]}")
            
            # Update status in tree
            try:
                item = self.active_downloads_tree.item(file_id)
                values = list(item['values'])
                values[3] = "⬇️ Downloading"
                if len(values) == 8:  # Old format without ETA
                    values.append("...")
                else:
                    values[8] = "..."  # ETA will be recalculated
                self.active_downloads_tree.item(file_id, values=values, tags=("downloading",))
            except:
                pass
    
    def _cancel_download(self):
        """Cancel the selected download."""
        selected = self.active_downloads_tree.selection()
        if not selected:
            messagebox.showwarning("No Selection", "Please select a download to cancel")
            return
        
        file_id = selected[0]
        result = messagebox.askyesno("Confirm Cancel", "Are you sure you want to cancel this download?")
        
        if result:
            self.download_cancelled[file_id] = True
            self._log(f"Cancelled download: {file_id[:8]}")
            
            # Remove from active downloads
            try:
                self.active_downloads_tree.delete(file_id)
            except:
                pass
    
    def _download_selected_from_results(self):
        """Download the selected file from search results."""
        selected = self.search_results_tree.selection()
        if not selected:
            messagebox.showwarning("No Selection", "Please select a file from search results")
            return
        
        # Get file_id from iid
        file_id = selected[0]
        self.file_id_var.set(file_id)
        self._download_file()
    
    def _on_search_mode_change(self):
        """Update the label when search mode changes."""
        # No label to update anymore - removed from UI
        pass
    
    def _filter_download_history(self, *args):
        """Filter download history by name."""
        search_term = self.history_search_var.get().lower()
        
        # Clear tree
        for item in self.history_tree.get_children():
            self.history_tree.delete(item)
        
        # Filter and display
        for entry in self.download_history:
            filename = entry.get("filename", "").lower()
            if search_term in filename:
                status = entry.get("status", "N/A")
                
                # Handle progress - completed downloads should show 100%
                if status == "Completed":
                    progress = "100%"
                else:
                    progress = entry.get("progress", "0%")
                
                # Get current peer counts from tracker (not old cached values)
                file_id = entry.get("file_id")
                seeds = 0
                peers = 0
                
                if file_id and file_id in self.peer_counts_cache:
                    peer_counts = self.peer_counts_cache.get(file_id, {})
                    seeds = peer_counts.get("seeders", 0)
                    peers = peer_counts.get("leechers", 0)
                elif file_id:
                    # Try to get from entry if available
                    seeds = entry.get("seeders", 0)
                    peers = entry.get("leechers", 0)
                
                down_speed = entry.get("down_speed", "0 KB/s")
                up_speed = entry.get("up_speed", "0 KB/s")
                
                self.history_tree.insert("", "end", values=(
                    entry.get("filename", "N/A"),
                    entry.get("size", "N/A"),
                    progress,
                    status,
                    seeds,
                    peers,
                    down_speed,
                    up_speed
                ), tags=(status.lower(),))
        
        self.history_tree.tag_configure("completed", foreground="green")
        self.history_tree.tag_configure("failed", foreground="red")
    
    def _clear_history_search(self):
        """Clear history search."""
        self.history_search_var.set("")
    
    def _update_stats(self):
        """Periodically update statistics display and peer counts."""
        update_counter = 0
        dashboard_counter = 0
        while True:
            try:
                time.sleep(1)
                upload_speed = self.stats.get_upload_speed()
                download_speed = self.stats.get_download_speed()
                
                # Update speed displays (every second)
                self.upload_speed_var.set(f"▲ {upload_speed:.1f} KB/s")
                self.download_speed_var.set(f"▼ {download_speed:.1f} KB/s")
                self.upload_speed_display.set(f"{upload_speed:.1f} KB/s")
                self.download_speed_display.set(f"{download_speed:.1f} KB/s")
                self.total_upload_var.set(f"{upload_speed:.2f} KB/s")
                self.total_download_var.set(f"{download_speed:.2f} KB/s")
                
                # Update file counts (every second)
                self.total_shared_var.set(str(len(self.shared_files)))
                completed_downloads = len([h for h in self.download_history if h.get('status') == 'Completed'])
                self.total_downloaded_var.set(str(completed_downloads))
                
                # Update data totals (every second)
                upload_mb = self.stats.upload_bytes / (1024 * 1024)
                download_mb = self.stats.download_bytes / (1024 * 1024)
                
                if upload_mb >= 1024:
                    self.total_upload_data_var.set(f"{upload_mb/1024:.2f} GB")
                else:
                    self.total_upload_data_var.set(f"{upload_mb:.1f} MB")
                
                if download_mb >= 1024:
                    self.total_download_data_var.set(f"{download_mb/1024:.2f} GB")
                else:
                    self.total_download_data_var.set(f"{download_mb:.1f} MB")
                
                # Update dashboard tree every 3 seconds to reduce flickering
                dashboard_counter += 1
                if dashboard_counter >= 3:
                    self._refresh_dashboard()
                    dashboard_counter = 0
                
                # Update stats tree every 2 seconds
                if update_counter % 2 == 0:
                    self._refresh_stats_tree()
                
                # Update peer counts every 10 seconds
                update_counter += 1
                if update_counter >= 10:
                    self._update_peer_counts_cache()
                    self._update_shared_files()
                    update_counter = 0
                    
            except Exception as e:
                logger.error(f"Stats update error: {e}")
    
    def _refresh_dashboard(self):
        """Refresh the main dashboard with all files."""
        try:
            # Get current items to check if update is needed
            current_items = set(self.dashboard_tree.get_children())
            expected_items = set(self.shared_files.keys())
            
            # Only do full refresh if items changed
            if current_items != expected_items:
                for item in self.dashboard_tree.get_children():
                    self.dashboard_tree.delete(item)
            
            # Add or update shared files
            for file_id, file_info in self.shared_files.items():
                role = self.state_mgr.get_role(file_id)
                progress = self.state_mgr.get_progress(file_id)
                peer_counts = self.peer_counts_cache.get(file_id, {"seeders": 0, "leechers": 0})
                
                # Calculate size
                num_chunks = file_info.get("chunks", 0)
                size_bytes = num_chunks * CHUNK_SIZE
                if size_bytes > 1024*1024:
                    size_str = f"{size_bytes/1024/1024:.1f} MB"
                else:
                    size_str = f"{size_bytes/1024:.0f} KB"
                
                # Get speeds
                upload_speed = self.stats.get_upload_speed()
                
                # Determine status and tag
                if role == "SEEDER":
                    status = "Seeding"
                    tag = "seeding"
                elif progress < 100:
                    status = "Downloading"
                    tag = "downloading"
                else:
                    status = "Finished"
                    tag = "seeding"
                
                values = (
                    file_info.get("filename", "N/A"),
                    size_str,
                    f"{progress:.0f}%",
                    status,
                    peer_counts.get("seeders", 0),
                    peer_counts.get("leechers", 0),
                    "0 KB/s",
                    f"{upload_speed:.1f} KB/s" if upload_speed > 0 and progress == 100 else "0 KB/s"
                )
                
                # Update existing item or insert new one
                if self.dashboard_tree.exists(file_id):
                    self.dashboard_tree.item(file_id, values=values, tags=(tag,))
                else:
                    self.dashboard_tree.insert("", "end", iid=file_id, values=values, tags=(tag,))
        
        except Exception as e:
            logger.error(f"Refresh dashboard error: {e}")
    
    def _refresh_stats_tree(self):
        """Refresh statistics tree."""
        try:
            transfers = self.stats.get_active_transfers()
            
            # Only update if count changed significantly (avoid flickering)
            current_count = len(self.stats_tree.get_children())
            new_count = len(transfers)
            
            if abs(current_count - new_count) > 5 or current_count == 0:
                # Clear existing items
                for item in self.stats_tree.get_children():
                    self.stats_tree.delete(item)
            else:
                # Just update the tree less frequently
                return
            
            # Add transfer records
            for transfer in transfers:
                transfer_type = transfer.get("type", "").upper()
                peer = transfer.get("peer", "N/A")
                file_id = transfer.get("file_id", "N/A")[:8]
                chunk = transfer.get("chunk", 0)
                bytes_count = transfer.get("bytes", 0)
                time_str = transfer.get("time", "")
                
                # Color based on type
                tags = ("upload",) if transfer_type == "UPLOAD" else ("download",)
                
                self.stats_tree.insert("", "end", values=(
                    time_str[-8:] if len(time_str) > 8 else time_str,
                    transfer_type,
                    peer,
                    file_id,
                    chunk,
                    f"{bytes_count/1024:.1f} KB"
                ), tags=tags)
        
        except Exception as e:
            logger.error(f"Refresh stats tree error: {e}")
    
    def _update_shared_files(self):
        """Update shared files list with seeding/leeching status and peer counts."""
        try:
            # Get current items to check if update is needed
            current_items = set(self.shared_tree.get_children())
            expected_items = set(self.shared_files.keys())
            
            # Only clear if items changed
            if current_items != expected_items:
                for item in self.shared_tree.get_children():
                    self.shared_tree.delete(item)
            
            # Update or add shared files
            for file_id, file_info in self.shared_files.items():
                # Get role and progress from state manager
                role = self.state_mgr.get_role(file_id)
                progress = self.state_mgr.get_progress(file_id)
                
                # Get peer counts from cache or query
                peer_counts = self.peer_counts_cache.get(file_id, {"seeders": 0, "leechers": 0})
                seeders = peer_counts.get("seeders", 0)
                leechers = peer_counts.get("leechers", 0)
                
                # Calculate size
                num_chunks = file_info.get("chunks", 0)
                size_bytes = num_chunks * CHUNK_SIZE
                if size_bytes > 1024*1024:
                    size_str = f"{size_bytes/1024/1024:.1f} MB"
                else:
                    size_str = f"{size_bytes/1024:.1f} KB"
                
                # Get upload speed for this file (approximate from total)
                upload_speed = self.stats.get_upload_speed()
                upload_speed_str = f"{upload_speed:.2f} KB/s" if upload_speed > 0 else "0 KB/s"
                
                # Determine status
                if role == "SEEDER":
                    status = "✅ Seeding"
                    tag = "seeding"
                elif role == "LEECHER":
                    status = "⬇️ Downloading"
                    tag = "leeching"
                else:
                    status = "Active"
                    tag = "active"
                
                values = (
                    file_info.get("filename", "N/A"),
                    file_id[:8] + "...",  # Display shortened ID
                    size_str,
                    f"{progress:.1f}%",
                    role,
                    f"🟢 {seeders}",
                    f"🟠 {leechers}",
                    upload_speed_str,
                    status
                )
                
                # Update existing item or insert new one
                if self.shared_tree.exists(file_id):
                    self.shared_tree.item(file_id, values=values, tags=(tag,))
                else:
                    self.shared_tree.insert("", "end", iid=file_id, values=values, tags=(tag,))
            
            self.shared_tree.tag_configure("seeding", foreground="green")
            self.shared_tree.tag_configure("leeching", foreground="blue")
            self.shared_tree.tag_configure("active", foreground="darkgreen")
        
        except Exception as e:
            logger.error(f"Update shared files error: {e}")
    
    def _select_file_to_share(self):
        """Open file dialog to select a file to share."""
        filename = filedialog.askopenfilename()
        if filename:
            self.share_file_path = filename
            self.share_file_var.set(os.path.basename(filename))
            self._log(f"Selected file: {filename}")
    
    def _share_file(self):
        """Share the selected file."""
        if not hasattr(self, 'share_file_path'):
            messagebox.showerror("Error", "Please select a file first")
            return
        
        def do_share():
            try:
                self._log(f"Starting file sharing process...")
                
                # Calculate file ID (hash of file content)
                file_id = self._calculate_file_id(self.share_file_path)
                self._log(f"File ID: {file_id}")
                
                # Create directory for this file's chunks
                file_chunk_dir = os.path.join(self.chunks_directory, file_id)
                os.makedirs(file_chunk_dir, exist_ok=True)
                
                # Split file into chunks
                self._log(f"Splitting file into chunks (size: {CHUNK_SIZE} bytes)...")
                num_chunks = self.chunker.split_file(self.share_file_path, file_chunk_dir)
                
                if num_chunks is None:
                    self._log("ERROR: Failed to split file")
                    messagebox.showerror("Error", "Failed to split file")
                    return
                
                self._log(f"Created {num_chunks} chunks")
                
                # Register with tracker
                self._log(f"Registering with tracker...")
                if self._register_file(file_id, os.path.basename(self.share_file_path), num_chunks):
                    self._log(f"Successfully shared file! File ID: {file_id}")
                    
                    # Record shared file
                    self.shared_files[file_id] = {
                        "filename": os.path.basename(self.share_file_path),
                        "chunks": num_chunks,
                        "date_shared": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    }
                    
                    # Add to state manager
                    self.state_mgr.add_torrent(
                        info_hash=file_id,
                        filename=os.path.basename(self.share_file_path),
                        total_size=os.path.getsize(self.share_file_path),
                        piece_length=CHUNK_SIZE,
                        total_pieces=num_chunks,
                        save_path=file_chunk_dir,
                        status="seeding"
                    )
                    
                    # Mark all pieces as completed (since we just created them)
                    for i in range(num_chunks):
                        self.state_mgr.update_piece_completion(file_id, i)
                    
                    # Save state to disk
                    self._save_state()
                    
                    self._update_shared_files()
                    
                    # Announce to tracker
                    self._announce_to_tracker("started", file_id)
                    
                    messagebox.showinfo("Success", f"File shared successfully!\nFile ID: {file_id}")
                else:
                    self._log("ERROR: Failed to register with tracker")
                    messagebox.showerror("Error", "Failed to register with tracker")
            
            except Exception as e:
                self._log(f"ERROR: {e}")
                messagebox.showerror("Error", str(e))
        
        thread = threading.Thread(target=do_share, daemon=True)
        thread.start()
    
    def _remove_shared_file(self):
        """Remove selected shared file."""
        selected = self.shared_tree.selection()
        if not selected:
            messagebox.showwarning("No Selection", "Please select a file to remove")
            return
        
        # Get full file_id from tree item iid (identifier)
        file_id = selected[0]  # The iid is the full file_id
        
        # Get filename from values
        item = self.shared_tree.item(selected[0])
        filename = item['values'][0]  # Filename column
        
        # Confirm deletion
        result = messagebox.askyesno(
            "Confirm Removal",
            f"Remove '{filename}' from shared files?\n\nThis will:\n" +
            "• Unregister from tracker\n" +
            "• Remove from state\n" +
            "• Delete chunks from disk\n\n" +
            "Continue?",
            icon='warning'
        )
        
        if not result:
            return
        
        def do_remove():
            try:
                self._log(f"Removing shared file: {filename} (ID: {file_id})")
                
                # 1. Announce stopped to tracker
                self._announce_to_tracker("stopped", file_id)
                
                # 2. Unregister from tracker
                try:
                    sock = SocketUtils.connect_to_server(
                        self.tracker_host_var.get(),
                        int(self.tracker_port_var.get())
                    )
                    if sock:
                        message = MessageBuilder.unregister_message(file_id, self.peer_id)
                        SocketUtils.send_message(sock, message)
                        sock.close()
                        self._log(f"Unregistered from tracker")
                except Exception as e:
                    self._log(f"Warning: Failed to unregister from tracker: {e}")
                
                # 3. Remove from state manager
                if file_id in self.state_mgr.state['torrents']:
                    del self.state_mgr.state['torrents'][file_id]
                    self.state_mgr.dirty = True
                    self._log(f"Removed from state")
                
                # 4. Delete chunks from disk
                file_chunk_dir = os.path.join(self.chunks_directory, file_id)
                if os.path.exists(file_chunk_dir):
                    import shutil
                    shutil.rmtree(file_chunk_dir)
                    self._log(f"Deleted chunks from disk")
                
                # 5. Remove from shared_files
                if file_id in self.shared_files:
                    del self.shared_files[file_id]
                
                # 6. Save state
                self._save_state()
                
                # 7. Update UI
                self._update_shared_files()
                
                self._log(f"Successfully removed {filename}")
                messagebox.showinfo("Success", f"Removed '{filename}' from shared files")
                
            except Exception as e:
                self._log(f"ERROR removing file: {e}")
                messagebox.showerror("Error", f"Failed to remove file: {e}")
        
        thread = threading.Thread(target=do_remove, daemon=True)
        thread.start()
    
    def _download_file(self):
        """Download a file by ID or filename."""
        input_value = self.file_id_var.get().strip()
        if not input_value:
            messagebox.showerror("Error", "Please enter a file ID or filename")
            return
        
        # Check if input looks like a file ID (16 hex characters)
        # If not, treat it as filename and search for it
        if len(input_value) != 16 or not all(c in '0123456789abcdefABCDEF' for c in input_value):
            if self.search_mode_var.get() == "filename":
                # Search for file by name first
                self._log(f"Searching for file: {input_value}")
                search_results = self._search_by_filename(input_value)
                
                if not search_results or not search_results.get('files'):
                    messagebox.showerror("Error", f"No files found matching '{input_value}'")
                    return
                
                files = search_results.get('files', [])
                
                # If multiple files, let user choose
                if len(files) > 1:
                    choice_msg = "Multiple files found. Select one:\n\n"
                    for i, f in enumerate(files, 1):
                        choice_msg += f"{i}. {f.get('filename')} (ID: {f.get('file_id')[:8]}...)\n"
                    choice_msg += "\nPlease search more specifically or use File ID"
                    messagebox.showinfo("Multiple Results", choice_msg)
                    return
                
                # Use the found file ID
                file_id = files[0].get('file_id')
                self._log(f"Found file ID: {file_id}")
            else:
                messagebox.showerror("Error", "Invalid file ID format. Must be 16 hex characters.")
                return
        else:
            file_id = input_value
        
        def do_download():
            try:
                self._log(f"Starting download for file ID: {file_id}")
                
                # Query tracker for file info
                self._log("Querying tracker for file information...")
                file_info = self._query_tracker(file_id)
                
                if not file_info:
                    self._log("ERROR: File not found on tracker")
                    messagebox.showerror("Error", "File not found on tracker")
                    return
                
                filename = file_info.get("filename", "downloaded_file")
                num_chunks = file_info.get("num_chunks", 0)
                peers = file_info.get("peers", [])
                
                # Calculate size
                size_bytes = num_chunks * CHUNK_SIZE
                if size_bytes > 1024*1024:
                    size_str = f"{size_bytes/1024/1024:.1f} MB"
                else:
                    size_str = f"{size_bytes/1024:.1f} KB"
                
                self._log(f"File: {filename}, Chunks: {num_chunks}, Available peers: {len(peers)}")
                
                if not peers:
                    self._log("ERROR: No peers have this file")
                    messagebox.showerror("Error", "No peers have this file")
                    return
                
                # Add to active downloads display
                self.active_downloads_tree.insert("", 0, iid=file_id, values=(
                    filename,
                    size_str,
                    "0%",
                    "⬇️ Downloading",
                    len(peers),
                    len(peers),
                    "0 KB/s",
                    "0 KB/s"
                ), tags=("downloading",))
                
                # Download chunks
                download_dir = os.path.join(self.downloads_directory, file_id)
                os.makedirs(download_dir, exist_ok=True)
                
                self._log(f"Downloading {num_chunks} chunks from {len(peers)} peer(s) using parallel download...")
                downloaded_chunks = 0
                start_time = time.time()
                
                # Use thread pool for parallel downloads
                from concurrent.futures import ThreadPoolExecutor, as_completed
                
                def download_chunk_task(chunk_idx):
                    """Download a single chunk from available peers."""
                    # Round-robin or random peer selection for load balancing
                    import random
                    shuffled_peers = random.sample(peers, len(peers))
                    
                    for peer in shuffled_peers:
                        try:
                            chunk_data = self._download_chunk(
                                peer["host"], peer["port"], file_id, chunk_idx
                            )
                            if chunk_data:
                                self._log(f"✓ Chunk {chunk_idx}/{num_chunks-1} from {peer['host']}:{peer['port']}")
                                return (chunk_idx, chunk_data, peer)
                        except Exception as e:
                            logger.debug(f"Peer {peer['host']}:{peer['port']} failed for chunk {chunk_idx}: {e}")
                            continue
                    
                    return (chunk_idx, None, None)
                
                # Download chunks in parallel with progress tracking
                with ThreadPoolExecutor(max_workers=min(MAX_PARALLEL_DOWNLOADS, num_chunks)) as executor:
                    # Submit all chunk download tasks
                    future_to_chunk = {executor.submit(download_chunk_task, i): i for i in range(num_chunks)}
                    
                    # Process completed downloads
                    for future in as_completed(future_to_chunk):
                        # Check if download was cancelled
                        if self.download_cancelled.get(file_id, False):
                            self._log(f"Download cancelled by user")
                            executor.shutdown(wait=False, cancel_futures=True)
                            return
                        
                        # Check if download is paused
                        while self.download_paused.get(file_id, False):
                            time.sleep(0.5)
                            if self.download_cancelled.get(file_id, False):
                                return
                        
                        chunk_idx, chunk_data, peer = future.result()
                        
                        if chunk_data:
                            if self.chunker.save_chunk(download_dir, chunk_idx, chunk_data):
                                downloaded_chunks += 1
                                # Show progress
                                progress_pct = (downloaded_chunks / num_chunks) * 100
                                
                                # Calculate download speed
                                elapsed = time.time() - start_time
                                if elapsed > 0:
                                    speed_kbps = (downloaded_chunks * CHUNK_SIZE / elapsed) / 1024
                                    speed_str = f"{speed_kbps:.2f} KB/s"
                                    
                                    # Calculate ETA
                                    remaining_chunks = num_chunks - downloaded_chunks
                                    remaining_bytes = remaining_chunks * CHUNK_SIZE
                                    if speed_kbps > 0:
                                        eta_seconds = remaining_bytes / (speed_kbps * 1024)
                                        if eta_seconds < 60:
                                            eta_str = f"{int(eta_seconds)}s"
                                        elif eta_seconds < 3600:
                                            eta_str = f"{int(eta_seconds/60)}m {int(eta_seconds%60)}s"
                                        else:
                                            eta_str = f"{int(eta_seconds/3600)}h {int((eta_seconds%3600)/60)}m"
                                    else:
                                        eta_str = "∞"
                                else:
                                    speed_str = "0 KB/s"
                                    eta_str = "∞"
                                
                                # Update active downloads tree
                                try:
                                    self.active_downloads_tree.item(file_id, values=(
                                        filename,
                                        size_str,
                                        f"{progress_pct:.1f}%",
                                        "⬇️ Downloading",
                                        len(peers),
                                        len(peers),
                                        speed_str,
                                        "0 KB/s",
                                        eta_str
                                    ))
                                except:
                                    pass
                                
                                self._log(f"📥 Progress: {downloaded_chunks}/{num_chunks} chunks ({progress_pct:.1f}%)")
                            else:
                                self._log(f"✗ Failed to save chunk {chunk_idx}")
                        else:
                            self._log(f"✗ Could not download chunk {chunk_idx} from any peer")
                
                # Merge chunks
                if downloaded_chunks == num_chunks:
                    output_file = os.path.join(self.downloads_directory, filename)
                    self._log(f"Merging {num_chunks} chunks...")
                    
                    # Update status
                    try:
                        self.active_downloads_tree.item(file_id, values=(
                            filename,
                            size_str,
                            "100%",
                            "✅ Completed",
                            len(peers),
                            len(peers),
                            "0 KB/s",
                            "0 KB/s",
                            "-"
                        ), tags=("completed",))
                    except:
                        pass
                    
                    if self.chunker.merge_chunks(download_dir, output_file, num_chunks):
                        self._log(f"Download complete! File saved to: {output_file}")
                        
                        # Get file size
                        try:
                            file_size = os.path.getsize(output_file)
                            size_str = f"{file_size/1024/1024:.1f} MB" if file_size > 1024*1024 else f"{file_size/1024:.1f} KB"
                        except:
                            size_str = "Unknown"
                        
                        # Calculate average speed
                        elapsed = time.time() - start_time
                        avg_speed = (downloaded_chunks * CHUNK_SIZE / elapsed) / 1024 if elapsed > 0 else 0
                        
                        # Record in download history
                        self.download_history.append({
                            "filename": filename,
                            "file_id": file_id,
                            "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            "size": size_str,
                            "status": "Completed",
                            "progress": "100%",
                            "seeders": len(peers),
                            "leechers": 0,
                            "down_speed": f"{avg_speed:.1f} KB/s",
                            "up_speed": "0 KB/s"
                        })
                        
                        # Save download history to state
                        self.state_mgr.state['download_history'] = self.download_history
                        self.state_mgr.dirty = True
                        self._save_state()
                        
                        self._filter_download_history()
                        
                        # Ask user if they want to share the downloaded file
                        share_response = messagebox.askyesno(
                            "Share Downloaded File",
                            f"Would you like to share this file?\n\n{filename}\n\nFile ID: {file_id}"
                        )
                        
                        if share_response:
                            self._auto_share_file(output_file, file_id, num_chunks)
                            messagebox.showinfo("Success", 
                                f"File downloaded and shared successfully!\n\n{output_file}\n\nFile ID: {file_id}")
                        else:
                            messagebox.showinfo("Success", f"File downloaded successfully!\n{output_file}")
                    else:
                        self._log("ERROR: Failed to merge chunks")
                        
                        # Update status to error
                        try:
                            self.active_downloads_tree.item(file_id, values=(
                                filename,
                                size_str,
                                f"{downloaded_chunks/num_chunks*100:.1f}%",
                                "❌ Failed",
                                len(peers),
                                len(peers),
                                "0 KB/s",
                                "0 KB/s",
                                "-"
                            ), tags=("error",))
                        except:
                            pass
                        
                        # Record failed download
                        self.download_history.append({
                            "filename": filename,
                            "file_id": file_id,
                            "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            "size": "N/A",
                            "status": "Failed",
                            "progress": f"{downloaded_chunks/num_chunks*100:.0f}%",
                            "seeders": len(peers),
                            "leechers": 0,
                            "down_speed": "0 KB/s",
                            "up_speed": "0 KB/s"
                        })
                        
                        self.state_mgr.state['download_history'] = self.download_history
                        self.state_mgr.dirty = True
                        self._save_state()
                        self._filter_download_history()
                        messagebox.showerror("Error", "Failed to merge chunks")
                else:
                    self._log(f"ERROR: Downloaded {downloaded_chunks}/{num_chunks} chunks")
                    
                    # Update status to error
                    try:
                        self.active_downloads_tree.item(file_id, values=(
                            filename,
                            size_str,
                            f"{downloaded_chunks/num_chunks*100:.1f}%",
                            "❌ Failed",
                            len(peers),
                            len(peers),
                            "0 KB/s",
                            "0 KB/s",
                            "-"
                        ), tags=("error",))
                    except:
                        pass
                    
                    # Record failed download
                    self.download_history.append({
                        "filename": filename,
                        "file_id": file_id,
                        "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "size": "N/A",
                        "status": "Failed",
                        "progress": f"{downloaded_chunks/num_chunks*100:.0f}%",
                        "seeders": len(peers),
                        "leechers": 0,
                        "down_speed": "0 KB/s",
                        "up_speed": "0 KB/s"
                    })
                    
                    self.state_mgr.state['download_history'] = self.download_history
                    self.state_mgr.dirty = True
                    self._save_state()
                    self._filter_download_history()
                    messagebox.showerror("Error", f"Only downloaded {downloaded_chunks}/{num_chunks} chunks")
            
            except Exception as e:
                self._log(f"ERROR: {e}")
                messagebox.showerror("Error", str(e))
        
        thread = threading.Thread(target=do_download, daemon=True)
        thread.start()
    
    def _calculate_file_id(self, filepath: str) -> str:
        """Calculate file ID using SHA256 hash of file content."""
        sha256_hash = hashlib.sha256()
        with open(filepath, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()[:16]  # First 16 characters
    
    def _auto_share_file(self, filepath: str, file_id: str, num_chunks: int):
        """Automatically share a downloaded file."""
        try:
            self._log(f"Auto-sharing downloaded file: {os.path.basename(filepath)}")
            
            # Create directory for this file's chunks
            file_chunk_dir = os.path.join(self.chunks_directory, file_id)
            os.makedirs(file_chunk_dir, exist_ok=True)
            
            # Split file into chunks
            self._log(f"Splitting file into chunks (size: {CHUNK_SIZE} bytes)...")
            result_chunks = self.chunker.split_file(filepath, file_chunk_dir)
            
            if result_chunks is None:
                self._log("ERROR: Failed to split file for sharing")
                messagebox.showerror("Error", "Failed to split file for sharing")
                return False
            
            self._log(f"Created {result_chunks} chunks for sharing")
            
            # Register with tracker
            self._log(f"Registering downloaded file with tracker...")
            if self._register_file(file_id, os.path.basename(filepath), result_chunks):
                self._log(f"Successfully shared downloaded file! File ID: {file_id}")
                
                # Record shared file
                self.shared_files[file_id] = {
                    "filename": os.path.basename(filepath),
                    "chunks": result_chunks,
                    "date_shared": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "source": "downloaded",  # Mark as downloaded and reshared
                    "completed_pieces": result_chunks
                }
                
                # Add to state manager (CRITICAL FIX)
                self.state_mgr.add_torrent(
                    info_hash=file_id,
                    filename=os.path.basename(filepath),
                    total_size=os.path.getsize(filepath),
                    piece_length=CHUNK_SIZE,
                    total_pieces=result_chunks,
                    save_path=file_chunk_dir,
                    status="seeding"
                )
                
                # Mark all pieces as completed (since we just created them)
                for i in range(result_chunks):
                    self.state_mgr.update_piece_completion(file_id, i)
                
                # Save state to disk
                self._save_state()
                
                # Announce to tracker that we're now seeding
                self._announce_to_tracker("started", file_id)
                
                self._update_shared_files()
                return True
            else:
                self._log("ERROR: Failed to register downloaded file with tracker")
                messagebox.showerror("Error", "Failed to register file with tracker")
                return False
        
        except Exception as e:
            self._log(f"ERROR in auto-share: {e}")
            messagebox.showerror("Error", f"Auto-share failed: {e}")
            return False
    
    def _register_file(self, file_id: str, filename: str, num_chunks: int) -> bool:
        """Register file with tracker."""
        try:
            sock = SocketUtils.connect_to_server(
                self.tracker_host_var.get(), 
                int(self.tracker_port_var.get())
            )
            if not sock:
                return False
            
            message = MessageBuilder.register_message(
                file_id, filename, num_chunks, self.peer_id, 
                self.local_ip, self.peer_port
            )
            
            if SocketUtils.send_message(sock, message):
                response = SocketUtils.receive_message(sock)
                sock.close()
                return response and response.get("status") == "success"
            
            sock.close()
            return False
        
        except Exception as e:
            self._log(f"Registration error: {e}")
            return False
    
    def _query_peer_counts(self, file_id: str) -> Dict[str, int]:
        """Query tracker for seeder and leecher counts for a file."""
        try:
            file_info = self._query_tracker(file_id)
            if not file_info:
                return {"seeders": 0, "leechers": 0}
            
            peers = file_info.get("peers", [])
            # In this implementation, we don't track seeder/leecher distinction at tracker level
            # So we'll consider all peers as potential seeders
            # A better implementation would track this at the tracker
            return {
                "seeders": len(peers),
                "leechers": 0  # Would need tracker modification to track this
            }
        except Exception as e:
            logger.error(f"Error querying peer counts: {e}")
            return {"seeders": 0, "leechers": 0}
    
    def _update_peer_counts_cache(self):
        """Update peer counts cache for all shared files."""
        for file_id in self.shared_files.keys():
            counts = self._query_peer_counts(file_id)
            self.peer_counts_cache[file_id] = counts
    
    def _query_tracker(self, file_id: str) -> Optional[Dict]:
        """Query tracker for file information."""
        try:
            sock = SocketUtils.connect_to_server(
                self.tracker_host_var.get(),
                int(self.tracker_port_var.get())
            )
            if not sock:
                return None
            
            message = MessageBuilder.query_message(file_id)
            
            if SocketUtils.send_message(sock, message):
                response = SocketUtils.receive_message(sock)
                sock.close()
                return response if response and response.get("status") == "success" else None
            
            sock.close()
            return None
        
        except Exception as e:
            self._log(f"Query error: {e}")
            return None
    
    def _search_by_filename(self, filename: str) -> Optional[Dict]:
        """Search for files by filename on tracker."""
        try:
            sock = SocketUtils.connect_to_server(
                self.tracker_host_var.get(),
                int(self.tracker_port_var.get())
            )
            if not sock:
                return None
            
            message = MessageBuilder.search_by_name_message(filename)
            
            if SocketUtils.send_message(sock, message):
                response = SocketUtils.receive_message(sock)
                sock.close()
                return response if response else None
            
            sock.close()
            return None
        
        except Exception as e:
            self._log(f"Search error: {e}")
            return None
    
    def _download_chunk(self, host: str, port: int, file_id: str, chunk_index: int) -> Optional[bytes]:
        """Download a chunk from a peer."""
        try:
            sock = SocketUtils.connect_to_server(host, port, timeout=DOWNLOAD_TIMEOUT)
            if not sock:
                return None
            
            message = MessageBuilder.chunk_request_message(file_id, chunk_index)
            
            if not SocketUtils.send_message(sock, message):
                sock.close()
                return None
            
            response = SocketUtils.receive_message(sock, timeout=DOWNLOAD_TIMEOUT)
            if not response or response.get("status") != "success":
                sock.close()
                return None
            
            chunk_size = response.get("chunk_size", 0)
            chunk_data = SocketUtils.receive_chunk_data(sock, chunk_size, timeout=DOWNLOAD_TIMEOUT)
            sock.close()
            
            # Record statistics
            if chunk_data:
                self.stats.add_download(len(chunk_data), f"{host}:{port}", file_id, chunk_index)
            
            return chunk_data
        
        except Exception as e:
            self._log(f"Chunk download error: {e}")
            return None
    
    def on_closing(self):
        """Handle window closing."""
        # Save state and announce stopped to tracker
        self._save_state()
        self._log("Saving peer state...")
        
        # Announce stopped to tracker for all active torrents
        for file_id in self.shared_files.keys():
            try:
                self._announce_to_tracker("stopped", file_id)
            except:
                pass
        
        # Shutdown state manager cleanly
        self.state_mgr.shutdown()
        
        self.peer_server.stop()
        self.root.destroy()
    
    def _announce_to_tracker(self, event: str, info_hash: str):
        """Send announce event to tracker (BitTorrent-style)."""
        try:
            sock = SocketUtils.connect_to_server(
                self.tracker_host_var.get(),
                int(self.tracker_port_var.get())
            )
            if not sock:
                return
            
            file_info = self.shared_files.get(info_hash, {})
            
            if event == "started":
                message = MessageBuilder.announce_message(
                    event="started",
                    info_hash=info_hash,
                    peer_id=self.peer_id,
                    host='127.0.0.1',
                    port=self.peer_port,
                    filename=file_info.get('filename', 'unknown'),
                    num_chunks=file_info.get('chunks', 0)
                )
            else:
                message = MessageBuilder.announce_message(
                    event=event,
                    info_hash=info_hash,
                    peer_id=self.peer_id
                )
            
            SocketUtils.send_message(sock, message)
            response = SocketUtils.receive_message(sock)
            sock.close()
            
            if response and response.get("status") == "success":
                logger.debug(f"Announced {event} for {info_hash[:8]}...")
        
        except Exception as e:
            logger.error(f"Announce error: {e}")


def main():
    """Start P2P client (no login required)."""
    root = tk.Tk()
    client = PeerClient(root)
    root.protocol("WM_DELETE_WINDOW", client.on_closing)
    root.mainloop()


if __name__ == "__main__":
    main()
