"""
File Chunking and Merging Module

Provides functionality to split files into fixed-size chunks and merge them back together.
"""

import os
import logging
from typing import Optional, List

logger = logging.getLogger(__name__)


class FileChunker:
    """Handles file splitting and chunk management."""
    
    def __init__(self, chunk_size: int = 262144):  # 256 KB default
        """
        Initialize the file chunker.
        
        Args:
            chunk_size: Size of each chunk in bytes (default: 256 KB)
        """
        if chunk_size <= 0:
            raise ValueError("Chunk size must be positive")
        self.chunk_size = chunk_size
    
    def split_file(self, input_file: str, output_directory: str) -> Optional[int]:
        """
        Split a file into chunks and save them to a directory.
        
        Args:
            input_file: Path to the file to split
            output_directory: Directory to store chunks
            
        Returns:
            Number of chunks created, or None if failed
        """
        try:
            if not os.path.exists(input_file):
                logger.error(f"File not found: {input_file}")
                return None
            
            if not os.path.exists(output_directory):
                os.makedirs(output_directory)
                logger.info(f"Created output directory: {output_directory}")
            
            chunk_count = 0
            with open(input_file, 'rb') as f:
                while True:
                    chunk_data = f.read(self.chunk_size)
                    if not chunk_data:
                        break
                    
                    chunk_filename = os.path.join(output_directory, f"chunk_{chunk_count}")
                    with open(chunk_filename, 'wb') as chunk_file:
                        chunk_file.write(chunk_data)
                    
                    logger.info(f"Created {chunk_filename} ({len(chunk_data)} bytes)")
                    chunk_count += 1
            
            logger.info(f"Successfully split file into {chunk_count} chunks")
            return chunk_count
            
        except Exception as e:
            logger.error(f"Failed to split file: {e}")
            return None
    
    def get_chunk(self, chunk_directory: str, chunk_index: int) -> Optional[bytes]:
        """
        Read a specific chunk from disk.
        
        Args:
            chunk_directory: Directory containing chunks
            chunk_index: Index of the chunk to read
            
        Returns:
            Chunk data as bytes, or None if failed
        """
        try:
            chunk_filename = os.path.join(chunk_directory, f"chunk_{chunk_index}")
            
            if not os.path.exists(chunk_filename):
                logger.error(f"Chunk not found: {chunk_filename}")
                return None
            
            with open(chunk_filename, 'rb') as f:
                chunk_data = f.read()
            
            logger.debug(f"Read chunk {chunk_index} ({len(chunk_data)} bytes)")
            return chunk_data
            
        except Exception as e:
            logger.error(f"Failed to read chunk: {e}")
            return None
    
    def save_chunk(self, chunk_directory: str, chunk_index: int, chunk_data: bytes) -> bool:
        """
        Save a chunk to disk.
        
        Args:
            chunk_directory: Directory to save chunk
            chunk_index: Index of the chunk
            chunk_data: Chunk data as bytes
            
        Returns:
            True if successful, False otherwise
        """
        try:
            if not os.path.exists(chunk_directory):
                os.makedirs(chunk_directory)
            
            chunk_filename = os.path.join(chunk_directory, f"chunk_{chunk_index}")
            with open(chunk_filename, 'wb') as f:
                f.write(chunk_data)
            
            logger.info(f"Saved chunk {chunk_index} ({len(chunk_data)} bytes)")
            return True
            
        except Exception as e:
            logger.error(f"Failed to save chunk: {e}")
            return False
    
    def merge_chunks(self, chunk_directory: str, output_file: str, num_chunks: int) -> bool:
        """
        Merge chunks back into a single file.
        
        Args:
            chunk_directory: Directory containing chunks
            output_file: Path to save the merged file
            num_chunks: Total number of chunks to merge
            
        Returns:
            True if successful, False otherwise
        """
        try:
            with open(output_file, 'wb') as output:
                for chunk_index in range(num_chunks):
                    chunk_filename = os.path.join(chunk_directory, f"chunk_{chunk_index}")
                    
                    if not os.path.exists(chunk_filename):
                        logger.error(f"Missing chunk: {chunk_filename}")
                        return False
                    
                    with open(chunk_filename, 'rb') as chunk_file:
                        chunk_data = chunk_file.read()
                        output.write(chunk_data)
                    
                    logger.debug(f"Merged chunk {chunk_index}")
            
            logger.info(f"Successfully merged {num_chunks} chunks into {output_file}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to merge chunks: {e}")
            return False
    
    def get_chunk_size(self, chunk_directory: str, chunk_index: int) -> Optional[int]:
        """
        Get the size of a specific chunk.
        
        Args:
            chunk_directory: Directory containing chunks
            chunk_index: Index of the chunk
            
        Returns:
            Size in bytes, or None if chunk not found
        """
        try:
            chunk_filename = os.path.join(chunk_directory, f"chunk_{chunk_index}")
            return os.path.getsize(chunk_filename)
        except Exception as e:
            logger.error(f"Failed to get chunk size: {e}")
            return None
    
    def verify_chunks(self, chunk_directory: str, num_chunks: int) -> bool:
        """
        Verify that all chunks exist.
        
        Args:
            chunk_directory: Directory containing chunks
            num_chunks: Expected number of chunks
            
        Returns:
            True if all chunks exist, False otherwise
        """
        try:
            for chunk_index in range(num_chunks):
                chunk_filename = os.path.join(chunk_directory, f"chunk_{chunk_index}")
                if not os.path.exists(chunk_filename):
                    logger.warning(f"Missing chunk: {chunk_filename}")
                    return False
            
            logger.info(f"All {num_chunks} chunks verified")
            return True
            
        except Exception as e:
            logger.error(f"Failed to verify chunks: {e}")
            return False
    
    def get_total_size(self, chunk_directory: str, num_chunks: int) -> Optional[int]:
        """
        Get the total size of all chunks.
        
        Args:
            chunk_directory: Directory containing chunks
            num_chunks: Expected number of chunks
            
        Returns:
            Total size in bytes, or None if failed
        """
        try:
            total_size = 0
            for chunk_index in range(num_chunks):
                chunk_filename = os.path.join(chunk_directory, f"chunk_{chunk_index}")
                if os.path.exists(chunk_filename):
                    total_size += os.path.getsize(chunk_filename)
            
            logger.info(f"Total chunk size: {total_size} bytes")
            return total_size
            
        except Exception as e:
            logger.error(f"Failed to get total size: {e}")
            return None


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    # Example usage
    chunker = FileChunker(chunk_size=256 * 1024)
    
    # Create a test file
    test_file = "test_file.txt"
    with open(test_file, 'w') as f:
        f.write("A" * (1024 * 1024))  # 1 MB file
    
    # Split the file
    num_chunks = chunker.split_file(test_file, "test_chunks")
    print(f"Created {num_chunks} chunks")
    
    # Merge back
    chunker.merge_chunks("test_chunks", "test_file_merged.txt", num_chunks)
    
    # Cleanup
    import shutil
    os.remove(test_file)
    shutil.rmtree("test_chunks")
    if os.path.exists("test_file_merged.txt"):
        os.remove("test_file_merged.txt")
