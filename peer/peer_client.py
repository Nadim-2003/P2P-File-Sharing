"""
Peer Client with Enhanced Tkinter GUI for P2P File-Sharing System

Allows users to share and download files with real-time statistics.
Shows seed speed, download speed, and which peer transfers which file.
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

# Add shared module to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from shared.utils import SocketUtils, MessageBuilder, FileUtils
from shared.chunking import FileChunker

# Configuration
TRACKER_HOST = '127.0.0.1'
TRACKER_PORT = 5000
PEER_PORT = 6000
CHUNK_SIZE = 262144  # 256 KB
DOWNLOAD_TIMEOUT = 10.0

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


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
        self.root.title("P2P File-Sharing Client - Advanced")
        self.root.geometry("1200x900")
        
        self.peer_id = str(uuid.uuid4())[:8]
        self.peer_port = PEER_PORT
        self.tracker_host = TRACKER_HOST
        self.tracker_port = TRACKER_PORT
        self.shared_directory = "shared"
        self.downloads_directory = "downloads"
        self.chunks_directory = os.path.join(self.shared_directory, "chunks")
        
        # Create directories
        os.makedirs(self.shared_directory, exist_ok=True)
        os.makedirs(self.downloads_directory, exist_ok=True)
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
        
        # Download history
        self.download_history: List[Dict] = []
        
        # Shared files tracking
        self.shared_files: Dict[str, Dict] = {}
        
        self._setup_ui()
        self._log(f"Peer ID: {self.peer_id}")
        self._log(f"Peer Server running on port {self.peer_port}")
        
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
        """Setup dashboard tab with overview and transfers."""
        dashboard_frame = ttk.Frame(notebook)
        notebook.add(dashboard_frame, text="Dashboard")
        
        container = ttk.Frame(dashboard_frame)
        container.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Info section
        info_frame = ttk.LabelFrame(container, text="Peer Information", padding=10)
        info_frame.pack(fill=tk.X, pady=5)
        
        # Left info
        left_frame = ttk.Frame(info_frame)
        left_frame.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        tk.Label(left_frame, text=f"Peer ID:", font=("Arial", 9, "bold")).pack(anchor=tk.W)
        tk.Label(left_frame, text=f"{self.peer_id}", font=("Arial", 10, "italic"), 
                fg="darkblue").pack(anchor=tk.W, padx=10)
        
        tk.Label(left_frame, text=f"Port:", font=("Arial", 9, "bold")).pack(anchor=tk.W, pady=(5,0))
        tk.Label(left_frame, text=f"{self.peer_port}", font=("Arial", 10, "italic"),
                fg="darkgreen").pack(anchor=tk.W, padx=10)
        
        # Right speed
        right_frame = ttk.Frame(info_frame)
        right_frame.pack(side=tk.RIGHT, fill=tk.X)
        
        # Upload speed
        ttk.Label(right_frame, text="📤 Upload Speed:", font=("Arial", 9, "bold")).pack(anchor=tk.W)
        self.upload_speed_var = tk.StringVar(value="0 KB/s")
        tk.Label(right_frame, textvariable=self.upload_speed_var, font=("Arial", 12, "bold"),
                fg="green").pack(anchor=tk.W, padx=10)
        
        # Download speed
        ttk.Label(right_frame, text="📥 Download Speed:", font=("Arial", 9, "bold")).pack(anchor=tk.W, pady=(5,0))
        self.download_speed_var = tk.StringVar(value="0 KB/s")
        tk.Label(right_frame, textvariable=self.download_speed_var, font=("Arial", 12, "bold"),
                fg="blue").pack(anchor=tk.W, padx=10)
        
        # Active transfers
        transfers_frame = ttk.LabelFrame(container, text="Active Transfers", padding=10)
        transfers_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        columns = ("Type", "Peer", "File ID", "Chunk", "Bytes", "Time")
        self.transfers_tree = ttk.Treeview(transfers_frame, columns=columns, height=12, show="headings")
        
        self.transfers_tree.column("Type", width=70, anchor=tk.CENTER)
        self.transfers_tree.column("Peer", width=140, anchor=tk.W)
        self.transfers_tree.column("File ID", width=100, anchor=tk.W)
        self.transfers_tree.column("Chunk", width=70, anchor=tk.CENTER)
        self.transfers_tree.column("Bytes", width=90, anchor=tk.CENTER)
        self.transfers_tree.column("Time", width=120, anchor=tk.W)
        
        for col in columns:
            self.transfers_tree.heading(col, text=col)
        
        scrollbar = ttk.Scrollbar(transfers_frame, orient=tk.VERTICAL, command=self.transfers_tree.yview)
        self.transfers_tree.configure(yscroll=scrollbar.set)
        
        self.transfers_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.transfers_tree.tag_configure("upload", foreground="green")
        self.transfers_tree.tag_configure("download", foreground="blue")
    
    def _setup_share_tab(self, notebook):
        """Setup file sharing tab."""
        share_frame = ttk.Frame(notebook)
        notebook.add(share_frame, text="Share Files")
        
        container = ttk.Frame(share_frame)
        container.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # File selection
        select_frame = ttk.LabelFrame(container, text="Select File to Share", padding=10)
        select_frame.pack(fill=tk.X, pady=5)
        
        self.share_file_var = tk.StringVar(value="No file selected")
        tk.Label(select_frame, textvariable=self.share_file_var, font=("Arial", 10),
                fg="darkblue").pack(pady=5)
        
        btn_frame = ttk.Frame(select_frame)
        btn_frame.pack(pady=5)
        ttk.Button(btn_frame, text="📁 Browse File", command=self._select_file_to_share).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="📤 Share File", command=self._share_file).pack(side=tk.LEFT, padx=5)
        
        # Shared files list
        shared_frame = ttk.LabelFrame(container, text="Shared Files", padding=10)
        shared_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        columns = ("Filename", "File ID", "Chunks", "Status")
        self.shared_tree = ttk.Treeview(shared_frame, columns=columns, height=12, show="headings")
        
        self.shared_tree.column("Filename", width=200, anchor=tk.W)
        self.shared_tree.column("File ID", width=150, anchor=tk.W)
        self.shared_tree.column("Chunks", width=80, anchor=tk.CENTER)
        self.shared_tree.column("Status", width=100, anchor=tk.CENTER)
        
        for col in columns:
            self.shared_tree.heading(col, text=col)
        
        scrollbar = ttk.Scrollbar(shared_frame, orient=tk.VERTICAL, command=self.shared_tree.yview)
        self.shared_tree.configure(yscroll=scrollbar.set)
        
        self.shared_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    
    def _setup_download_tab(self, notebook):
        """Setup file download tab with search."""
        download_frame = ttk.Frame(notebook)
        notebook.add(download_frame, text="Download Files")
        
        container = ttk.Frame(download_frame)
        container.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Search/Query section
        query_frame = ttk.LabelFrame(container, text="Search for Files", padding=10)
        query_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(query_frame, text="File ID:").pack(side=tk.LEFT, padx=5)
        self.file_id_var = tk.StringVar()
        ttk.Entry(query_frame, textvariable=self.file_id_var, width=40).pack(side=tk.LEFT, padx=5)
        ttk.Button(query_frame, text="🔍 Search", command=self._search_file).pack(side=tk.LEFT, padx=5)
        
        # Download section
        download_section = ttk.LabelFrame(container, text="Download", padding=10)
        download_section.pack(fill=tk.X, pady=5)
        
        ttk.Button(download_section, text="⬇️ Download File", 
                  command=self._download_file).pack(side=tk.LEFT, padx=5)
        
        # Search results
        results_frame = ttk.LabelFrame(container, text="Search Results", padding=10)
        results_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        self.search_results_text = scrolledtext.ScrolledText(results_frame, height=8, wrap=tk.WORD,
                                                            state=tk.DISABLED)
        self.search_results_text.pack(fill=tk.BOTH, expand=True)
        
        # Download history with search
        history_frame = ttk.LabelFrame(container, text="Download History (Search by Name)", padding=10)
        history_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        # Search box
        search_box_frame = ttk.Frame(history_frame)
        search_box_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(search_box_frame, text="Search:").pack(side=tk.LEFT, padx=5)
        self.history_search_var = tk.StringVar()
        self.history_search_var.trace("w", self._filter_download_history)
        ttk.Entry(search_box_frame, textvariable=self.history_search_var, width=40).pack(side=tk.LEFT, padx=5)
        ttk.Button(search_box_frame, text="Clear", command=self._clear_history_search).pack(side=tk.LEFT, padx=5)
        
        # History tree
        columns = ("Filename", "Date", "Size", "Status")
        self.history_tree = ttk.Treeview(history_frame, columns=columns, height=8, show="headings")
        
        self.history_tree.column("Filename", width=250, anchor=tk.W)
        self.history_tree.column("Date", width=150, anchor=tk.CENTER)
        self.history_tree.column("Size", width=100, anchor=tk.CENTER)
        self.history_tree.column("Status", width=100, anchor=tk.CENTER)
        
        for col in columns:
            self.history_tree.heading(col, text=col)
        
        scrollbar = ttk.Scrollbar(history_frame, orient=tk.VERTICAL, command=self.history_tree.yview)
        self.history_tree.configure(yscroll=scrollbar.set)
        
        self.history_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    
    def _setup_stats_tab(self, notebook):
        """Setup statistics tab."""
        stats_frame = ttk.Frame(notebook)
        notebook.add(stats_frame, text="Statistics")
        
        container = ttk.Frame(stats_frame)
        container.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Stats display
        stats_info = ttk.LabelFrame(container, text="Statistics Overview", padding=10)
        stats_info.pack(fill=tk.X, pady=5)
        
        # Stats labels
        frame_row1 = ttk.Frame(stats_info)
        frame_row1.pack(fill=tk.X, pady=5)
        
        ttk.Label(frame_row1, text="Total Upload Speed:", font=("Arial", 10, "bold")).pack(side=tk.LEFT, padx=10)
        self.total_upload_var = tk.StringVar(value="0 KB/s")
        tk.Label(frame_row1, textvariable=self.total_upload_var, font=("Arial", 11, "bold"),
                fg="green").pack(side=tk.LEFT, padx=10)
        
        ttk.Label(frame_row1, text="Total Download Speed:", font=("Arial", 10, "bold")).pack(side=tk.LEFT, padx=10)
        self.total_download_var = tk.StringVar(value="0 KB/s")
        tk.Label(frame_row1, textvariable=self.total_download_var, font=("Arial", 11, "bold"),
                fg="blue").pack(side=tk.LEFT, padx=10)
        
        # Transfers log
        log_frame = ttk.LabelFrame(container, text="Detailed Transfer Log", padding=10)
        log_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        columns = ("Time", "Type", "Peer", "File", "Chunk", "Bytes")
        self.stats_tree = ttk.Treeview(log_frame, columns=columns, height=15, show="headings")
        
        self.stats_tree.column("Time", width=120, anchor=tk.CENTER)
        self.stats_tree.column("Type", width=80, anchor=tk.CENTER)
        self.stats_tree.column("Peer", width=150, anchor=tk.W)
        self.stats_tree.column("File", width=120, anchor=tk.W)
        self.stats_tree.column("Chunk", width=80, anchor=tk.CENTER)
        self.stats_tree.column("Bytes", width=100, anchor=tk.CENTER)
        
        for col in columns:
            self.stats_tree.heading(col, text=col)
        
        scrollbar = ttk.Scrollbar(log_frame, orient=tk.VERTICAL, command=self.stats_tree.yview)
        self.stats_tree.configure(yscroll=scrollbar.set)
        
        self.stats_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.stats_tree.tag_configure("upload", foreground="green")
        self.stats_tree.tag_configure("download", foreground="blue")
    
    def _setup_settings_tab(self, notebook):
        """Setup settings tab."""
        settings_frame = ttk.Frame(notebook)
        notebook.add(settings_frame, text="Settings")
        
        container = ttk.Frame(settings_frame)
        container.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Tracker configuration
        tracker_frame = ttk.LabelFrame(container, text="Tracker Configuration", padding=10)
        tracker_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(tracker_frame, text="Tracker Host:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        self.tracker_host_var = tk.StringVar(value=self.tracker_host)
        ttk.Entry(tracker_frame, textvariable=self.tracker_host_var, width=30).grid(row=0, column=1, padx=5, pady=5)
        
        ttk.Label(tracker_frame, text="Tracker Port:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        self.tracker_port_var = tk.StringVar(value=str(self.tracker_port))
        ttk.Entry(tracker_frame, textvariable=self.tracker_port_var, width=30).grid(row=1, column=1, padx=5, pady=5)
        
        # Status log
        log_frame = ttk.LabelFrame(container, text="Status Log", padding=10)
        log_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        self.log_text = scrolledtext.ScrolledText(log_frame, height=15, wrap=tk.WORD, state=tk.DISABLED)
        self.log_text.pack(fill=tk.BOTH, expand=True)
        
        # Control buttons
        btn_frame = ttk.Frame(container)
        btn_frame.pack(fill=tk.X, pady=10)
        
        ttk.Button(btn_frame, text="🗑️ Clear Log", command=self._clear_log).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="📂 Open Downloads Folder", command=self._open_downloads).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="📂 Open Shared Folder", command=self._open_shared).pack(side=tk.LEFT, padx=5)
    
    def _log(self, message: str):
        """Add a message to the log."""
        self.log_text.config(state=tk.NORMAL)
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.insert(tk.END, f"[{timestamp}] {message}\n")
        self.log_text.see(tk.END)
        self.log_text.config(state=tk.DISABLED)
        logger.info(message)
    
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
        """Search for a file on tracker."""
        file_id = self.file_id_var.get().strip()
        if not file_id:
            self.search_results_text.config(state=tk.NORMAL)
            self.search_results_text.delete(1.0, tk.END)
            self.search_results_text.insert(tk.END, "Please enter a file ID to search")
            self.search_results_text.config(state=tk.DISABLED)
            return
        
        def do_search():
            try:
                self._log(f"Searching for file: {file_id}")
                file_info = self._query_tracker(file_id)
                
                self.search_results_text.config(state=tk.NORMAL)
                self.search_results_text.delete(1.0, tk.END)
                
                if file_info:
                    result = f"✓ File Found!\n\n"
                    result += f"File ID: {file_info.get('file_id', 'N/A')}\n"
                    result += f"Filename: {file_info.get('filename', 'N/A')}\n"
                    result += f"Chunks: {file_info.get('num_chunks', 0)}\n"
                    result += f"Available Peers: {len(file_info.get('peers', []))}\n\n"
                    
                    result += "Peers Seeding:\n"
                    result += "-" * 50 + "\n"
                    
                    for i, peer in enumerate(file_info.get('peers', []), 1):
                        result += f"{i}. {peer.get('host')}:{peer.get('port')}\n"
                    
                    self._log(f"Found file with {len(file_info.get('peers', []))} peers")
                else:
                    result = "✗ File not found on tracker\n\nMake sure the file ID is correct."
                    self._log("File not found")
                
                self.search_results_text.insert(tk.END, result)
                self.search_results_text.config(state=tk.DISABLED)
            
            except Exception as e:
                self.search_results_text.config(state=tk.NORMAL)
                self.search_results_text.delete(1.0, tk.END)
                self.search_results_text.insert(tk.END, f"Error: {e}")
                self.search_results_text.config(state=tk.DISABLED)
                self._log(f"Search error: {e}")
        
        thread = threading.Thread(target=do_search, daemon=True)
        thread.start()
    
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
                self.history_tree.insert("", "end", values=(
                    entry.get("filename", "N/A"),
                    entry.get("date", "N/A"),
                    entry.get("size", "N/A"),
                    entry.get("status", "N/A")
                ), tags=(entry.get("status", "").lower(),))
        
        self.history_tree.tag_configure("completed", foreground="green")
        self.history_tree.tag_configure("failed", foreground="red")
    
    def _clear_history_search(self):
        """Clear history search."""
        self.history_search_var.set("")
    
    def _update_stats(self):
        """Periodically update statistics display."""
        while True:
            try:
                time.sleep(1)
                upload_speed = self.stats.get_upload_speed()
                download_speed = self.stats.get_download_speed()
                
                self.upload_speed_var.set(f"{upload_speed:.2f} KB/s")
                self.download_speed_var.set(f"{download_speed:.2f} KB/s")
                self.total_upload_var.set(f"{upload_speed:.2f} KB/s")
                self.total_download_var.set(f"{download_speed:.2f} KB/s")
                
                self._refresh_transfers()
                self._refresh_stats_tree()
            except Exception as e:
                logger.error(f"Stats update error: {e}")
    
    def _refresh_transfers(self):
        """Refresh the transfers display."""
        try:
            # Clear existing items
            for item in self.transfers_tree.get_children():
                self.transfers_tree.delete(item)
            
            # Add transfer records
            transfers = self.stats.get_active_transfers()
            for transfer in transfers:
                transfer_type = transfer.get("type", "").upper()
                peer = transfer.get("peer", "N/A")
                file_id = transfer.get("file_id", "N/A")[:8]
                chunk = transfer.get("chunk", 0)
                bytes_count = transfer.get("bytes", 0)
                time_str = transfer.get("time", "")[-8:]  # Last 8 chars (time part)
                
                # Color based on type
                tags = ("upload",) if transfer_type == "UPLOAD" else ("download",)
                
                self.transfers_tree.insert("", "end", values=(
                    transfer_type,
                    peer,
                    file_id,
                    chunk,
                    f"{bytes_count/1024:.1f} KB",
                    time_str
                ), tags=tags)
            
            # Configure tag colors
            self.transfers_tree.tag_configure("upload", foreground="green")
            self.transfers_tree.tag_configure("download", foreground="blue")
            
        except Exception as e:
            logger.error(f"Refresh transfers error: {e}")
    
    def _refresh_stats_tree(self):
        """Refresh statistics tree."""
        try:
            # Clear existing items
            for item in self.stats_tree.get_children():
                self.stats_tree.delete(item)
            
            # Add transfer records
            transfers = self.stats.get_active_transfers()
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
                    time_str[-8:],
                    transfer_type,
                    peer,
                    file_id,
                    chunk,
                    f"{bytes_count/1024:.1f} KB"
                ), tags=tags)
        
        except Exception as e:
            logger.error(f"Refresh stats tree error: {e}")
    
    def _update_shared_files(self):
        """Update shared files list."""
        try:
            # Clear tree
            for item in self.shared_tree.get_children():
                self.shared_tree.delete(item)
            
            # Add shared files
            for file_id, file_info in self.shared_files.items():
                self.shared_tree.insert("", "end", values=(
                    file_info.get("filename", "N/A"),
                    file_id[:8],
                    file_info.get("chunks", 0),
                    "Active"
                ), tags=("active",))
            
            self.shared_tree.tag_configure("active", foreground="green")
        
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
                    
                    self._update_shared_files()
                    messagebox.showinfo("Success", f"File shared successfully!\nFile ID: {file_id}")
                else:
                    self._log("ERROR: Failed to register with tracker")
                    messagebox.showerror("Error", "Failed to register with tracker")
            
            except Exception as e:
                self._log(f"ERROR: {e}")
                messagebox.showerror("Error", str(e))
        
        thread = threading.Thread(target=do_share, daemon=True)
        thread.start()
    
    def _download_file(self):
        """Download a file by ID."""
        file_id = self.file_id_var.get().strip()
        if not file_id:
            messagebox.showerror("Error", "Please enter a file ID")
            return
        
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
                
                self._log(f"File: {filename}, Chunks: {num_chunks}, Available peers: {len(peers)}")
                
                if not peers:
                    self._log("ERROR: No peers have this file")
                    messagebox.showerror("Error", "No peers have this file")
                    return
                
                # Download chunks
                download_dir = os.path.join(self.downloads_directory, file_id)
                os.makedirs(download_dir, exist_ok=True)
                
                self._log(f"Downloading {num_chunks} chunks from peers...")
                downloaded_chunks = 0
                
                for chunk_index in range(num_chunks):
                    # Try to download from peers
                    chunk_data = None
                    for peer in peers:
                        try:
                            chunk_data = self._download_chunk(
                                peer["host"], peer["port"], file_id, chunk_index
                            )
                            if chunk_data:
                                self._log(f"Downloaded chunk {chunk_index} from {peer['host']}:{peer['port']}")
                                break
                        except Exception as e:
                            self._log(f"Failed to download chunk from {peer['host']}: {e}")
                    
                    if chunk_data:
                        if self.chunker.save_chunk(download_dir, chunk_index, chunk_data):
                            downloaded_chunks += 1
                        else:
                            self._log(f"Failed to save chunk {chunk_index}")
                    else:
                        self._log(f"ERROR: Could not download chunk {chunk_index}")
                        break
                
                # Merge chunks
                if downloaded_chunks == num_chunks:
                    output_file = os.path.join(self.downloads_directory, filename)
                    self._log(f"Merging {num_chunks} chunks...")
                    
                    if self.chunker.merge_chunks(download_dir, output_file, num_chunks):
                        self._log(f"Download complete! File saved to: {output_file}")
                        
                        # Get file size
                        try:
                            file_size = os.path.getsize(output_file)
                            size_str = f"{file_size/1024/1024:.1f} MB" if file_size > 1024*1024 else f"{file_size/1024:.1f} KB"
                        except:
                            size_str = "Unknown"
                        
                        # Record in download history
                        self.download_history.append({
                            "filename": filename,
                            "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            "size": size_str,
                            "status": "Completed"
                        })
                        
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
                        
                        # Record failed download
                        self.download_history.append({
                            "filename": filename,
                            "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            "size": "N/A",
                            "status": "Failed"
                        })
                        
                        self._filter_download_history()
                        messagebox.showerror("Error", "Failed to merge chunks")
                else:
                    self._log(f"ERROR: Downloaded {downloaded_chunks}/{num_chunks} chunks")
                    
                    # Record failed download
                    self.download_history.append({
                        "filename": filename,
                        "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "size": "N/A",
                        "status": "Failed"
                    })
                    
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
                    "source": "downloaded"  # Mark as downloaded and reshared
                }
                
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
                '127.0.0.1', self.peer_port
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
        self.peer_server.stop()
        self.root.destroy()


def main():
    root = tk.Tk()
    client = PeerClient(root)
    root.protocol("WM_DELETE_WINDOW", client.on_closing)
    root.mainloop()


if __name__ == "__main__":
    main()
