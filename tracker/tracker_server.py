"""
Tracker Server for P2P File-Sharing System

Maintains a mapping between file IDs and the list of peers that have those files.
Handles peer registration and responds to queries for available peers.
"""

import os
import sys
import socket
import json
import threading
import logging
from typing import Dict, List, Set
import signal

# Ensure project root is on sys.path so imports like `from shared.utils` work
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from shared.utils import SocketUtils

# Configuration
# Change to '0.0.0.0' to accept connections from other laptops on the network
# Keep '127.0.0.1' for local-only testing
TRACKER_HOST = '192.168.0.202'#'192.168.10.82'  # Listen on all network interfaces
TRACKER_PORT = 5000
BUFFER_SIZE = 4096

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class TrackerServer:
    """
    Lightweight tracker server that maintains file-to-peer mappings.
    
    Data structure:
    {
        "file_id": {
            "filename": str,
            "num_chunks": int,
            "peers": [
                {"host": str, "port": int, "peer_id": str},
                ...
            ]
        }
    }
    """
    
    def __init__(self, host=TRACKER_HOST, port=TRACKER_PORT):
        self.host = host
        self.port = port
        self.server_socket = None
        self.running = threading.Event()
        self.running.set()
        self.files: Dict[str, Dict] = {}  # file_id -> file metadata and peers
        self.lock = threading.RLock()  # Thread-safe access to files dictionary
        
    def start(self):
        """Start the tracker server and listen for incoming connections."""
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        
        try:
            self.server_socket.bind((self.host, self.port))
            self.server_socket.listen(5)
            logger.info(f"Tracker Server started on {self.host}:{self.port}")
            
            while self.running.is_set():
                try:
                    client_socket, client_address = self.server_socket.accept()
                    logger.info(f"Connection from {client_address}")
                    
                    # Handle client in a separate thread
                    client_thread = threading.Thread(
                        target=self.handle_client,
                        args=(client_socket, client_address)
                    )
                    client_thread.daemon = True
                    client_thread.start()
                    
                except Exception as e:
                    logger.error(f"Error accepting connection: {e}")
                    
        except Exception as e:
            logger.error(f"Failed to start tracker server: {e}")
        finally:
            try:
                if self.server_socket:
                    self.server_socket.close()
            except Exception:
                pass

    def shutdown(self):
        """Gracefully stop the tracker server."""
        logger.info("Tracker server shutting down...")
        self.running.clear()
        try:
            if self.server_socket:
                self.server_socket.close()
        except Exception as e:
            logger.error(f"Error closing server socket: {e}")
            
    def handle_client(self, client_socket, client_address):
        """Handle a single client connection."""
        try:
            while True:
                message = SocketUtils.receive_message(client_socket)
                if not message:
                    break

                logger.info(f"Received from {client_address}: {message}")
                response = self.process_message(message)
                SocketUtils.send_message(client_socket, response)
                
        except json.JSONDecodeError:
            logger.error(f"Invalid JSON received from {client_address}")
            response = {"status": "error", "message": "Invalid JSON"}
            try:
                client_socket.send(json.dumps(response).encode('utf-8'))
            except:
                pass
        except Exception as e:
            logger.error(f"Error handling client {client_address}: {e}")
        finally:
            client_socket.close()
            logger.info(f"Connection closed from {client_address}")
            
    def process_message(self, message: Dict) -> Dict:
        """
        Process incoming messages from peers.
        
        Message types:
        1. REGISTER - Register a file with the tracker
        2. QUERY - Query for peers that have a specific file
        3. UNREGISTER - Unregister a file from the tracker
        4. SEARCH_BY_NAME - Search files by filename
        5. ANNOUNCE - BitTorrent-style announce (started/stopped/completed)
        """
        msg_type = message.get("type")
        
        if msg_type == "REGISTER":
            return self.handle_register(message)
        elif msg_type == "QUERY":
            return self.handle_query(message)
        elif msg_type == "UNREGISTER":
            return self.handle_unregister(message)
        elif msg_type == "SEARCH_BY_NAME":
            return self.handle_search_by_name(message)
        elif msg_type == "ANNOUNCE":
            return self.handle_announce(message)
        else:
            return {"status": "error", "message": f"Unknown message type: {msg_type}"}
            
    def handle_register(self, message: Dict) -> Dict:
        """
        Handle peer registration for a file.
        
        Expected message format:
        {
            "type": "REGISTER",
            "file_id": str,
            "filename": str,
            "num_chunks": int,
            "peer_id": str,
            "host": str,
            "port": int
        }
        """
        file_id = message.get("file_id")
        filename = message.get("filename")
        num_chunks = message.get("num_chunks")
        peer_id = message.get("peer_id")
        host = message.get("host")
        port = message.get("port")
        
        if not all([file_id, filename, num_chunks, peer_id, host, port]):
            return {"status": "error", "message": "Missing required fields"}
        
        with self.lock:
            if file_id not in self.files:
                self.files[file_id] = {
                    "filename": filename,
                    "num_chunks": num_chunks,
                    "peers": []
                }
            
            # Check if peer already registered
            peer_info = {"host": host, "port": port, "peer_id": peer_id}
            peers = self.files[file_id]["peers"]
            
            if not any(p["peer_id"] == peer_id for p in peers):
                peers.append(peer_info)
                logger.info(f"Peer {peer_id} registered for file {file_id}")
            else:
                logger.info(f"Peer {peer_id} already registered for file {file_id}")
        
        return {
            "status": "success",
            "message": f"Successfully registered file {file_id}",
            "file_id": file_id
        }
        
    def handle_query(self, message: Dict) -> Dict:
        """
        Handle query for peers that have a specific file.
        
        Expected message format:
        {
            "type": "QUERY",
            "file_id": str
        }
        """
        file_id = message.get("file_id")
        
        if not file_id:
            return {"status": "error", "message": "Missing file_id"}
        
        with self.lock:
            if file_id not in self.files:
                return {
                    "status": "error",
                    "message": f"File {file_id} not found",
                    "peers": []
                }
            
            file_info = self.files[file_id]
            return {
                "status": "success",
                "file_id": file_id,
                "filename": file_info["filename"],
                "num_chunks": file_info["num_chunks"],
                "peers": file_info["peers"]
            }
            
    def handle_unregister(self, message: Dict) -> Dict:
        """
        Handle peer unregistration (removal of peer from file's peer list).
        
        Expected message format:
        {
            "type": "UNREGISTER",
            "file_id": str,
            "peer_id": str
        }
        """
        file_id = message.get("file_id")
        peer_id = message.get("peer_id")
        
        if not file_id or not peer_id:
            return {"status": "error", "message": "Missing required fields"}
        
        with self.lock:
            if file_id not in self.files:
                return {"status": "error", "message": f"File {file_id} not found"}
            
            peers = self.files[file_id]["peers"]
            original_count = len(peers)
            self.files[file_id]["peers"] = [p for p in peers if p["peer_id"] != peer_id]
            
            if len(self.files[file_id]["peers"]) < original_count:
                logger.info(f"Peer {peer_id} unregistered from file {file_id}")
                return {"status": "success", "message": f"Peer {peer_id} unregistered"}
            else:
                return {"status": "error", "message": f"Peer {peer_id} not found for file {file_id}"}
    
    def handle_search_by_name(self, message: Dict) -> Dict:
        """
        Handle search for files by filename (case-insensitive partial match).
        
        Expected message format:
        {
            "type": "SEARCH_BY_NAME",
            "filename": str
        }
        """
        search_term = message.get("filename", "").lower().strip()
        
        if not search_term:
            return {"status": "error", "message": "Missing filename search term"}
        
        with self.lock:
            matching_files = []
            
            # Debug: log all files in tracker
            logger.info(f"Searching for '{search_term}' in {len(self.files)} registered files")
            for fid, finfo in self.files.items():
                logger.debug(f"  File: {finfo['filename']} (ID: {fid})")
            
            for file_id, file_info in self.files.items():
                filename = file_info["filename"].lower()
                if search_term in filename:
                    matching_files.append({
                        "file_id": file_id,
                        "filename": file_info["filename"],
                        "num_chunks": file_info["num_chunks"],
                        "peers": file_info["peers"]
                    })
            
            if not matching_files:
                logger.info(f"No files found matching '{search_term}'")
                return {
                    "status": "error",
                    "message": f"No files found matching '{search_term}'",
                    "files": []
                }
            
            logger.info(f"Found {len(matching_files)} file(s) matching '{search_term}'")
            return {
                "status": "success",
                "message": f"Found {len(matching_files)} file(s) matching '{search_term}'",
                "files": matching_files
            }
    
    def handle_announce(self, message: Dict) -> Dict:
        """
        Handle BitTorrent-style announce events.
        
        Expected message format:
        {
            "type": "ANNOUNCE",
            "event": "started" | "stopped" | "completed",
            "info_hash": str,  # file_id
            "peer_id": str,
            "host": str,
            "port": int,
            "filename": str,  # for started events
            "num_chunks": int  # for started events
        }
        
        Events:
        - started: Peer started downloading/seeding (register with tracker)
        - stopped: Peer stopped (unregister from tracker)
        - completed: Peer completed download (became seeder)
        """
        event = message.get("event")
        info_hash = message.get("info_hash")
        peer_id = message.get("peer_id")
        
        if not all([event, info_hash, peer_id]):
            return {"status": "error", "message": "Missing required fields (event, info_hash, peer_id)"}
        
        if event == "started":
            # Register peer with tracker
            filename = message.get("filename", "unknown")
            num_chunks = message.get("num_chunks", 0)
            host = message.get("host")
            port = message.get("port")
            
            if not all([host, port]):
                return {"status": "error", "message": "Missing host or port for started event"}
            
            with self.lock:
                if info_hash not in self.files:
                    self.files[info_hash] = {
                        "filename": filename,
                        "num_chunks": num_chunks,
                        "peers": []
                    }
                
                peer_info = {"host": host, "port": port, "peer_id": peer_id}
                peers = self.files[info_hash]["peers"]
                
                if not any(p["peer_id"] == peer_id for p in peers):
                    peers.append(peer_info)
                    logger.info(f"Announce [started]: {peer_id} for {info_hash[:8]}... ({filename})")
            
            return {"status": "success", "message": "Announced started"}
        
        elif event == "stopped":
            # Unregister peer from tracker
            with self.lock:
                if info_hash in self.files:
                    peers = self.files[info_hash]["peers"]
                    original_count = len(peers)
                    self.files[info_hash]["peers"] = [p for p in peers if p["peer_id"] != peer_id]
                    
                    if len(self.files[info_hash]["peers"]) < original_count:
                        logger.info(f"Announce [stopped]: {peer_id} for {info_hash[:8]}...")
                        return {"status": "success", "message": "Announced stopped"}
            
            return {"status": "success", "message": "Peer was not registered"}
        
        elif event == "completed":
            # Peer completed download (just log it, peer stays registered)
            logger.info(f"Announce [completed]: {peer_id} completed {info_hash[:8]}...")
            return {"status": "success", "message": "Announced completed"}
        
        else:
            return {"status": "error", "message": f"Unknown announce event: {event}"}
                
    def get_stats(self) -> Dict:
        """Get tracker server statistics."""
        with self.lock:
            total_files = len(self.files)
            total_peers = sum(len(f["peers"]) for f in self.files.values())
            
            return {
                "total_files": total_files,
                "total_peers": total_peers,
                "files": self.files
            }


if __name__ == "__main__":
    tracker = TrackerServer()

    def _handle_sigint(signum, frame):
        tracker.shutdown()
        sys.exit(0)

    signal.signal(signal.SIGINT, _handle_sigint)

    try:
        tracker.start()
    except KeyboardInterrupt:
        tracker.shutdown()