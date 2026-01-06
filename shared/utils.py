"""
Shared utilities for P2P File-Sharing System

Provides common functionality for TCP communication and message handling.
"""

import socket
import json
import logging
from typing import Dict, Optional, Tuple

logger = logging.getLogger(__name__)

# Default configuration
DEFAULT_CHUNK_SIZE = 262144  # 256 KB
MAX_CHUNK_SIZE = 1048576     # 1 MB
BUFFER_SIZE = 4096


class SocketUtils:
    """Utilities for socket communication."""
    
    @staticmethod
    def send_message(sock: socket.socket, message: Dict) -> bool:
        """
        Send a JSON message over a socket.
        
        Args:
            sock: Socket to send on
            message: Dictionary to send as JSON
            
        Returns:
            True if successful, False otherwise
        """
        try:
            data = json.dumps(message).encode('utf-8')
            # Prefix message with 8-byte big-endian length for framing
            length_prefix = len(data).to_bytes(8, byteorder='big')
            sock.sendall(length_prefix + data)
            return True
        except Exception as e:
            logger.error(f"Failed to send message: {e}")
            return False
    
    @staticmethod
    def receive_message(sock: socket.socket, timeout: Optional[float] = None) -> Optional[Dict]:
        """
        Receive a JSON message from a socket.
        
        Args:
            sock: Socket to receive from
            timeout: Optional timeout in seconds
            
        Returns:
            Dictionary if successful, None otherwise
        """
        try:
            if timeout is not None:
                sock.settimeout(timeout)

            # Read 8-byte length prefix first
            prefix = b''
            while len(prefix) < 8:
                chunk = sock.recv(8 - len(prefix))
                if not chunk:
                    return None
                prefix += chunk

            msg_length = int.from_bytes(prefix, byteorder='big')
            # Read the exact message length
            data = b''
            while len(data) < msg_length:
                to_read = min(BUFFER_SIZE, msg_length - len(data))
                chunk = sock.recv(to_read)
                if not chunk:
                    logger.error("Connection closed while receiving message body")
                    return None
                data += chunk

            message = json.loads(data.decode('utf-8'))
            return message

        except socket.timeout:
            logger.warning("Socket receive timeout")
            return None
        except json.JSONDecodeError:
            logger.error("Invalid JSON received")
            return None
        except Exception as e:
            logger.error(f"Failed to receive message: {e}")
            return None
    
    @staticmethod
    def send_chunk_data(sock: socket.socket, chunk_data: bytes) -> bool:
        """
        Send binary chunk data over a socket.
        
        Args:
            sock: Socket to send on
            chunk_data: Bytes to send
            
        Returns:
            True if successful, False otherwise
        """
        try:
            sock.sendall(chunk_data)
            return True
        except Exception as e:
            logger.error(f"Failed to send chunk data: {e}")
            return False
    
    @staticmethod
    def receive_chunk_data(sock: socket.socket, size: int, timeout: Optional[float] = None) -> Optional[bytes]:
        """
        Receive binary chunk data from a socket.
        
        Args:
            sock: Socket to receive from
            size: Expected size of chunk data
            timeout: Optional timeout in seconds
            
        Returns:
            Bytes if successful, None otherwise
        """
        try:
            if timeout is not None:
                sock.settimeout(timeout)
            
            data = b''
            while len(data) < size:
                remaining = size - len(data)
                chunk = sock.recv(min(BUFFER_SIZE, remaining))
                if not chunk:
                    logger.error("Connection closed while receiving chunk data")
                    return None
                data += chunk
            
            return data
            
        except socket.timeout:
            logger.warning("Socket receive timeout")
            return None
        except Exception as e:
            logger.error(f"Failed to receive chunk data: {e}")
            return None
    
    @staticmethod
    def connect_to_server(host: str, port: int, timeout: float = 5.0) -> Optional[socket.socket]:
        """
        Create a socket and connect to a server.
        
        Args:
            host: Server hostname or IP
            port: Server port
            timeout: Connection timeout in seconds
            
        Returns:
            Connected socket if successful, None otherwise
        """
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            sock.connect((host, port))
            return sock
        except Exception as e:
            logger.error(f"Failed to connect to {host}:{port}: {e}")
            return None


class FileUtils:
    """Utilities for file operations."""
    
    @staticmethod
    def validate_chunk_size(chunk_size: int) -> bool:
        """Validate chunk size is within acceptable range."""
        return DEFAULT_CHUNK_SIZE <= chunk_size <= MAX_CHUNK_SIZE
    
    @staticmethod
    def calculate_num_chunks(file_size: int, chunk_size: int) -> int:
        """Calculate the number of chunks needed for a file."""
        return (file_size + chunk_size - 1) // chunk_size
    
    @staticmethod
    def get_file_size(filepath: str) -> Optional[int]:
        """Get the size of a file in bytes."""
        try:
            import os
            return os.path.getsize(filepath)
        except Exception as e:
            logger.error(f"Failed to get file size: {e}")
            return None


class MessageBuilder:
    """Builder for constructing protocol messages."""
    
    @staticmethod
    def register_message(file_id: str, filename: str, num_chunks: int, 
                        peer_id: str, host: str, port: int) -> Dict:
        """Build a REGISTER message."""
        return {
            "type": "REGISTER",
            "file_id": file_id,
            "filename": filename,
            "num_chunks": num_chunks,
            "peer_id": peer_id,
            "host": host,
            "port": port
        }
    
    @staticmethod
    def query_message(file_id: str) -> Dict:
        """Build a QUERY message."""
        return {
            "type": "QUERY",
            "file_id": file_id
        }
    
    @staticmethod
    def unregister_message(file_id: str, peer_id: str) -> Dict:
        """Build an UNREGISTER message."""
        return {
            "type": "UNREGISTER",
            "file_id": file_id,
            "peer_id": peer_id
        }
    
    @staticmethod
    def chunk_request_message(file_id: str, chunk_index: int) -> Dict:
        """Build a CHUNK_REQUEST message."""
        return {
            "type": "CHUNK_REQUEST",
            "file_id": file_id,
            "chunk_index": chunk_index
        }
    
    @staticmethod
    def chunk_response_message(file_id: str, chunk_index: int, 
                              chunk_size: int, status: str = "success") -> Dict:
        """Build a CHUNK_RESPONSE message."""
        return {
            "type": "CHUNK_RESPONSE",
            "file_id": file_id,
            "chunk_index": chunk_index,
            "chunk_size": chunk_size,
            "status": status
        }
