"""
Persistent Peer Identity Manager

Manages peer_id.txt to ensure the same device always uses the same peer ID.
NO authentication, NO login - just device-based identity.
"""

import os
import uuid
import logging

logger = logging.getLogger(__name__)


class PeerIdentity:
    """Manages persistent peer identity for BitTorrent-like behavior."""
    
    def __init__(self, data_dir: str = None):
        """
        Initialize peer identity manager.
        
        Args:
            data_dir: Directory to store peer data. Defaults to ~/.minitorrent/
        """
        if data_dir is None:
            data_dir = os.path.join(os.path.expanduser("~"), ".minitorrent")
        
        self.data_dir = os.path.abspath(data_dir)
        self.peer_id_file = os.path.join(self.data_dir, "peer_id.txt")
        self.state_file = os.path.join(self.data_dir, "state.json")
        self.downloads_dir = os.path.join(self.data_dir, "downloads")
        self.uploads_dir = os.path.join(self.data_dir, "uploads")
        
        # Ensure directory structure exists
        self._ensure_directories()
        
        # Load or generate peer ID
        self.peer_id = self._load_or_generate_peer_id()
        
    def _ensure_directories(self):
        """Create necessary directories if they don't exist."""
        os.makedirs(self.data_dir, exist_ok=True)
        os.makedirs(self.downloads_dir, exist_ok=True)
        os.makedirs(self.uploads_dir, exist_ok=True)
        logger.info(f"Data directory: {self.data_dir}")
    
    def _load_or_generate_peer_id(self) -> str:
        """
        Load existing peer_id or generate a new one.
        
        CRITICAL: Once generated, peer_id NEVER changes unless data directory is deleted.
        
        Returns:
            20-character peer ID (BitTorrent standard)
        """
        if os.path.exists(self.peer_id_file):
            # Load existing peer ID
            with open(self.peer_id_file, 'r') as f:
                peer_id = f.read().strip()
            logger.info(f"Loaded existing peer ID: {peer_id[:8]}...")
            return peer_id
        else:
            # Generate new peer ID (first run on this device)
            peer_id = self._generate_peer_id()
            
            # Save it permanently
            with open(self.peer_id_file, 'w') as f:
                f.write(peer_id)
            
            logger.info(f"Generated NEW peer ID: {peer_id[:8]}... (first run on this device)")
            return peer_id
    
    def _generate_peer_id(self) -> str:
        """
        Generate a BitTorrent-style peer ID.
        
        Format: -MT0001-<12 random characters>
        Where MT = MiniTorrent, 0001 = version
        
        Returns:
            20-character peer ID
        """
        # Client ID: -MT0001-
        client_id = "-MT0001-"
        
        # Random 12 characters
        random_part = uuid.uuid4().hex[:12]
        
        peer_id = client_id + random_part
        return peer_id
    
    def get_peer_id(self) -> str:
        """Get the persistent peer ID for this device."""
        return self.peer_id
    
    def get_data_dir(self) -> str:
        """Get the data directory path."""
        return self.data_dir
    
    def get_downloads_dir(self) -> str:
        """Get the downloads directory path."""
        return self.downloads_dir
    
    def get_uploads_dir(self) -> str:
        """Get the uploads directory path."""
        return self.uploads_dir
    
    def get_state_file(self) -> str:
        """Get the state.json file path."""
        return self.state_file


if __name__ == "__main__":
    # Test the peer identity system
    logging.basicConfig(level=logging.INFO)
    
    # First run
    identity = PeerIdentity()
    print(f"Peer ID: {identity.get_peer_id()}")
    print(f"Data dir: {identity.get_data_dir()}")
    print(f"Downloads: {identity.get_downloads_dir()}")
    print(f"Uploads: {identity.get_uploads_dir()}")
    print(f"State file: {identity.get_state_file()}")
    
    # Second run (should load same peer ID)
    identity2 = PeerIdentity()
    print(f"\nSecond run - Peer ID: {identity2.get_peer_id()}")
    print(f"IDs match: {identity.get_peer_id() == identity2.get_peer_id()}")
