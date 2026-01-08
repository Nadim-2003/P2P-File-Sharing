"""
State Manager for BitTorrent-like P2P Client

Manages state.json with torrent information, progress, and statistics.
Implements crash-safe periodic flushing and efficient in-memory state.
"""

import json
import os
import time
import threading
import logging
from typing import Dict, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class StateManager:
    """
    Manages persistent state for torrents.
    
    Schema:
    {
        "peer_metadata": {
            "peer_id": str,
            "created_at": str,
            "last_updated": str
        },
        "torrents": {
            "<info_hash>": {
                "info_hash": str,
                "filename": str,
                "total_size": int,
                "piece_length": int,
                "total_pieces": int,
                "completed_pieces": [list of completed piece indices],
                "downloaded_bytes": int,
                "uploaded_bytes": int,
                "status": "downloading" | "seeding" | "paused" | "stopped",
                "save_path": str,
                "added_at": str,
                "completed_at": str | null,
                "last_active": str
            }
        },
        "statistics": {
            "total_downloaded": int,
            "total_uploaded": int,
            "session_start": str
        }
    }
    """
    
    def __init__(self, state_file: str, peer_id: str, auto_save_interval: int = 30):
        """
        Initialize state manager.
        
        Args:
            state_file: Path to state.json
            peer_id: Persistent peer ID
            auto_save_interval: Seconds between automatic saves (default: 30)
        """
        self.state_file = state_file
        self.peer_id = peer_id
        self.auto_save_interval = auto_save_interval
        
        # In-memory state
        self.state = self._load_or_create_state()
        
        # Dirty flag for efficient saving
        self.dirty = False
        self.lock = threading.RLock()
        
        # Auto-save thread
        self.running = True
        self.auto_save_thread = threading.Thread(target=self._auto_save_loop, daemon=True)
        self.auto_save_thread.start()
    
    def _load_or_create_state(self) -> Dict:
        """Load existing state or create new one."""
        if os.path.exists(self.state_file):
            try:
                with open(self.state_file, 'r') as f:
                    state = json.load(f)
                logger.info(f"Loaded state with {len(state.get('torrents', {}))} torrents")
                return state
            except Exception as e:
                logger.error(f"Failed to load state: {e}")
                return self._create_initial_state()
        else:
            logger.info("Creating initial state (first run)")
            return self._create_initial_state()
    
    def _create_initial_state(self) -> Dict:
        """Create initial empty state."""
        return {
            "peer_metadata": {
                "peer_id": self.peer_id,
                "created_at": datetime.now().isoformat(),
                "last_updated": datetime.now().isoformat()
            },
            "torrents": {},
            "statistics": {
                "total_downloaded": 0,
                "total_uploaded": 0,
                "session_start": datetime.now().isoformat()
            }
        }
    
    def add_torrent(self, info_hash: str, filename: str, total_size: int, 
                   piece_length: int, total_pieces: int, save_path: str,
                   status: str = "downloading") -> bool:
        """
        Add a new torrent to state.
        
        Args:
            info_hash: Unique identifier for the torrent (file_id)
            filename: Name of the file
            total_size: Total file size in bytes
            piece_length: Size of each piece/chunk
            total_pieces: Total number of pieces
            save_path: Where the file is/will be saved
            status: Initial status
            
        Returns:
            True if added successfully
        """
        with self.lock:
            if info_hash in self.state["torrents"]:
                logger.warning(f"Torrent {info_hash} already exists")
                return False
            
            self.state["torrents"][info_hash] = {
                "info_hash": info_hash,
                "filename": filename,
                "total_size": total_size,
                "piece_length": piece_length,
                "total_pieces": total_pieces,
                "completed_pieces": [],
                "downloaded_bytes": 0,
                "uploaded_bytes": 0,
                "status": status,
                "save_path": save_path,
                "added_at": datetime.now().isoformat(),
                "completed_at": None,
                "last_active": datetime.now().isoformat()
            }
            
            self.dirty = True
            logger.info(f"Added torrent: {filename} ({info_hash[:8]}...)")
            return True
    
    def update_piece_completion(self, info_hash: str, piece_index: int) -> bool:
        """Mark a piece as completed."""
        with self.lock:
            if info_hash not in self.state["torrents"]:
                return False
            
            torrent = self.state["torrents"][info_hash]
            if piece_index not in torrent["completed_pieces"]:
                torrent["completed_pieces"].append(piece_index)
                torrent["completed_pieces"].sort()
                torrent["last_active"] = datetime.now().isoformat()
                
                # Check if torrent is now complete
                if len(torrent["completed_pieces"]) == torrent["total_pieces"]:
                    if torrent["status"] == "downloading":
                        torrent["status"] = "seeding"
                        torrent["completed_at"] = datetime.now().isoformat()
                        logger.info(f"Torrent completed: {torrent['filename']}")
                
                self.dirty = True
                return True
            return False
    
    def update_stats(self, info_hash: str, downloaded_bytes: int = 0, 
                    uploaded_bytes: int = 0) -> bool:
        """Update download/upload statistics."""
        with self.lock:
            if info_hash not in self.state["torrents"]:
                return False
            
            torrent = self.state["torrents"][info_hash]
            torrent["downloaded_bytes"] += downloaded_bytes
            torrent["uploaded_bytes"] += uploaded_bytes
            torrent["last_active"] = datetime.now().isoformat()
            
            self.state["statistics"]["total_downloaded"] += downloaded_bytes
            self.state["statistics"]["total_uploaded"] += uploaded_bytes
            
            self.dirty = True
            return True
    
    def update_status(self, info_hash: str, status: str) -> bool:
        """Update torrent status."""
        with self.lock:
            if info_hash not in self.state["torrents"]:
                return False
            
            self.state["torrents"][info_hash]["status"] = status
            self.state["torrents"][info_hash]["last_active"] = datetime.now().isoformat()
            self.dirty = True
            return True
    
    def get_torrent(self, info_hash: str) -> Optional[Dict]:
        """Get torrent information."""
        with self.lock:
            return self.state["torrents"].get(info_hash)
    
    def get_all_torrents(self) -> Dict[str, Dict]:
        """Get all torrents."""
        with self.lock:
            return self.state["torrents"].copy()
    
    def get_role(self, info_hash: str) -> str:
        """
        Calculate role dynamically (NEVER stored).
        
        Returns:
            "SEEDER" if all pieces completed, "LEECHER" otherwise
        """
        with self.lock:
            torrent = self.state["torrents"].get(info_hash)
            if not torrent:
                return "UNKNOWN"
            
            if len(torrent["completed_pieces"]) == torrent["total_pieces"]:
                return "SEEDER"
            else:
                return "LEECHER"
    
    def get_progress(self, info_hash: str) -> float:
        """Calculate download progress percentage."""
        with self.lock:
            torrent = self.state["torrents"].get(info_hash)
            if not torrent or torrent["total_pieces"] == 0:
                return 0.0
            
            return (len(torrent["completed_pieces"]) / torrent["total_pieces"]) * 100.0
    
    def get_torrent_summary(self) -> List[Dict]:
        """
        Get UI-ready torrent summary.
        
        Returns list of:
        {
            "name": str,
            "progress": float,
            "role": "SEEDER" | "LEECHER",
            "downloaded": int,
            "uploaded": int,
            "status": str,
            "info_hash": str
        }
        """
        with self.lock:
            summary = []
            for info_hash, torrent in self.state["torrents"].items():
                summary.append({
                    "name": torrent["filename"],
                    "progress": self.get_progress(info_hash),
                    "role": self.get_role(info_hash),
                    "downloaded": torrent["downloaded_bytes"],
                    "uploaded": torrent["uploaded_bytes"],
                    "status": torrent["status"],
                    "info_hash": info_hash
                })
            return summary
    
    def save(self) -> bool:
        """Save state to disk (crash-safe)."""
        with self.lock:
            try:
                self.state["peer_metadata"]["last_updated"] = datetime.now().isoformat()
                
                # Write to temporary file first
                temp_file = self.state_file + ".tmp"
                with open(temp_file, 'w') as f:
                    json.dump(self.state, f, indent=2)
                
                # Atomic rename
                os.replace(temp_file, self.state_file)
                
                self.dirty = False
                logger.debug("State saved successfully")
                return True
            except Exception as e:
                logger.error(f"Failed to save state: {e}")
                return False
    
    def _auto_save_loop(self):
        """Periodic auto-save thread."""
        while self.running:
            time.sleep(self.auto_save_interval)
            if self.dirty:
                self.save()
    
    def shutdown(self):
        """Clean shutdown - save state and stop auto-save thread."""
        logger.info("Shutting down state manager...")
        self.running = False
        if self.dirty:
            self.save()
        logger.info("State manager shutdown complete")


if __name__ == "__main__":
    # Test the state manager
    logging.basicConfig(level=logging.INFO)
    
    state_mgr = StateManager("test_state.json", "TEST-PEER-ID-123")
    
    # Add a torrent
    state_mgr.add_torrent(
        info_hash="abc123def456",
        filename="test_file.mp4",
        total_size=1024000,
        piece_length=256000,
        total_pieces=4,
        save_path="/downloads/test_file.mp4"
    )
    
    # Simulate download progress
    state_mgr.update_piece_completion("abc123def456", 0)
    state_mgr.update_piece_completion("abc123def456", 1)
    state_mgr.update_stats("abc123def456", downloaded_bytes=512000, uploaded_bytes=100000)
    
    print("\nTorrent Summary:")
    for torrent in state_mgr.get_torrent_summary():
        print(f"  {torrent['name']}: {torrent['progress']:.1f}% - {torrent['role']}")
    
    # Save and shutdown
    state_mgr.shutdown()
