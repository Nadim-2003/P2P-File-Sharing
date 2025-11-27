"""
Unit Tests for P2P File-Sharing System

Tests for file chunking, merging, and basic functionality.
"""

import unittest
import os
import tempfile
import shutil
import sys
import hashlib

# Add shared module to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from shared.chunking import FileChunker
from shared.utils import FileUtils, SocketUtils, MessageBuilder


class TestFileChunking(unittest.TestCase):
    """Test file chunking and merging functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.test_dir = tempfile.mkdtemp()
        self.chunk_size = 1024  # 1 KB for testing
        self.chunker = FileChunker(self.chunk_size)
    
    def tearDown(self):
        """Clean up test fixtures."""
        shutil.rmtree(self.test_dir, ignore_errors=True)
    
    def test_split_file(self):
        """Test file splitting into chunks."""
        # Create test file
        test_file = os.path.join(self.test_dir, "test_file.txt")
        test_data = "A" * (1024 * 3)  # 3 KB
        
        with open(test_file, 'w') as f:
            f.write(test_data)
        
        # Split file
        chunks_dir = os.path.join(self.test_dir, "chunks")
        num_chunks = self.chunker.split_file(test_file, chunks_dir)
        
        # Verify
        self.assertEqual(num_chunks, 3, "Should create 3 chunks for 3 KB file with 1 KB chunks")
        self.assertTrue(os.path.exists(os.path.join(chunks_dir, "chunk_0")))
        self.assertTrue(os.path.exists(os.path.join(chunks_dir, "chunk_1")))
        self.assertTrue(os.path.exists(os.path.join(chunks_dir, "chunk_2")))
    
    def test_merge_chunks(self):
        """Test merging chunks back into original file."""
        # Create test file
        test_file = os.path.join(self.test_dir, "test_file.txt")
        test_data = "Test content for merging" * 100  # ~2.4 KB
        
        with open(test_file, 'wb') as f:
            f.write(test_data.encode())
        
        # Split file
        chunks_dir = os.path.join(self.test_dir, "chunks")
        num_chunks = self.chunker.split_file(test_file, chunks_dir)
        
        # Merge back
        merged_file = os.path.join(self.test_dir, "merged_file.txt")
        success = self.chunker.merge_chunks(chunks_dir, merged_file, num_chunks)
        
        # Verify
        self.assertTrue(success, "Merging should succeed")
        
        with open(merged_file, 'rb') as f:
            merged_data = f.read().decode()
        
        self.assertEqual(merged_data, test_data, "Merged file should match original")
    
    def test_get_chunk(self):
        """Test retrieving a specific chunk."""
        # Create test file
        test_file = os.path.join(self.test_dir, "test_file.txt")
        with open(test_file, 'w') as f:
            f.write("ABCD" * 256)  # 1 KB
        
        # Split file
        chunks_dir = os.path.join(self.test_dir, "chunks")
        self.chunker.split_file(test_file, chunks_dir)
        
        # Get chunk
        chunk_data = self.chunker.get_chunk(chunks_dir, 0)
        
        # Verify
        self.assertIsNotNone(chunk_data, "Chunk should be retrieved")
        self.assertEqual(len(chunk_data), 1024, "Chunk should be 1 KB")
    
    def test_save_chunk(self):
        """Test saving a chunk."""
        chunks_dir = os.path.join(self.test_dir, "chunks")
        test_data = b"Test chunk data"
        
        success = self.chunker.save_chunk(chunks_dir, 0, test_data)
        
        # Verify
        self.assertTrue(success, "Saving chunk should succeed")
        self.assertTrue(os.path.exists(os.path.join(chunks_dir, "chunk_0")))
        
        with open(os.path.join(chunks_dir, "chunk_0"), 'rb') as f:
            saved_data = f.read()
        
        self.assertEqual(saved_data, test_data, "Saved chunk should match original")
    
    def test_verify_chunks(self):
        """Test chunk verification."""
        # Create test file
        test_file = os.path.join(self.test_dir, "test_file.txt")
        with open(test_file, 'w') as f:
            f.write("X" * 4096)
        
        # Split file
        chunks_dir = os.path.join(self.test_dir, "chunks")
        num_chunks = self.chunker.split_file(test_file, chunks_dir)
        
        # Verify all chunks exist
        verified = self.chunker.verify_chunks(chunks_dir, num_chunks)
        self.assertTrue(verified, "All chunks should be verified")
        
        # Remove one chunk and verify again
        os.remove(os.path.join(chunks_dir, "chunk_1"))
        verified = self.chunker.verify_chunks(chunks_dir, num_chunks)
        self.assertFalse(verified, "Should fail when chunk is missing")
    
    def test_get_total_size(self):
        """Test getting total size of all chunks."""
        # Create test file
        test_file = os.path.join(self.test_dir, "test_file.txt")
        original_size = 1024 * 5  # 5 KB
        
        with open(test_file, 'wb') as f:
            f.write(b"Z" * original_size)
        
        # Split file
        chunks_dir = os.path.join(self.test_dir, "chunks")
        num_chunks = self.chunker.split_file(test_file, chunks_dir)
        
        # Get total size
        total_size = self.chunker.get_total_size(chunks_dir, num_chunks)
        
        # Verify
        self.assertEqual(total_size, original_size, "Total chunk size should match original file size")


class TestFileUtils(unittest.TestCase):
    """Test file utility functions."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.test_dir = tempfile.mkdtemp()
    
    def tearDown(self):
        """Clean up test fixtures."""
        shutil.rmtree(self.test_dir, ignore_errors=True)
    
    def test_validate_chunk_size(self):
        """Test chunk size validation."""
        # Valid sizes
        self.assertTrue(FileUtils.validate_chunk_size(262144))  # 256 KB
        self.assertTrue(FileUtils.validate_chunk_size(512000))  # 512 KB
        
        # Invalid sizes
        self.assertFalse(FileUtils.validate_chunk_size(100))    # Too small
        self.assertFalse(FileUtils.validate_chunk_size(2000000)) # Too large
    
    def test_calculate_num_chunks(self):
        """Test chunk count calculation."""
        chunk_size = 1024
        
        # Exact multiple
        self.assertEqual(FileUtils.calculate_num_chunks(1024 * 5, chunk_size), 5)
        
        # Not exact multiple (should round up)
        self.assertEqual(FileUtils.calculate_num_chunks(1024 * 5 + 100, chunk_size), 6)
        
        # Single chunk
        self.assertEqual(FileUtils.calculate_num_chunks(512, chunk_size), 1)
    
    def test_get_file_size(self):
        """Test getting file size."""
        # Create test file
        test_file = os.path.join(self.test_dir, "test_file.txt")
        test_size = 1024 * 100  # 100 KB
        
        with open(test_file, 'wb') as f:
            f.write(b"X" * test_size)
        
        # Get size
        size = FileUtils.get_file_size(test_file)
        
        # Verify
        self.assertEqual(size, test_size, "File size should match")
        
        # Non-existent file
        size = FileUtils.get_file_size("/nonexistent/file")
        self.assertIsNone(size, "Should return None for non-existent file")


class TestMessageBuilder(unittest.TestCase):
    """Test message builder utility."""
    
    def test_register_message(self):
        """Test REGISTER message building."""
        msg = MessageBuilder.register_message("file123", "test.txt", 5, "peer1", "127.0.0.1", 6000)
        
        self.assertEqual(msg["type"], "REGISTER")
        self.assertEqual(msg["file_id"], "file123")
        self.assertEqual(msg["filename"], "test.txt")
        self.assertEqual(msg["num_chunks"], 5)
        self.assertEqual(msg["peer_id"], "peer1")
    
    def test_query_message(self):
        """Test QUERY message building."""
        msg = MessageBuilder.query_message("file123")
        
        self.assertEqual(msg["type"], "QUERY")
        self.assertEqual(msg["file_id"], "file123")
    
    def test_chunk_request_message(self):
        """Test CHUNK_REQUEST message building."""
        msg = MessageBuilder.chunk_request_message("file123", 2)
        
        self.assertEqual(msg["type"], "CHUNK_REQUEST")
        self.assertEqual(msg["file_id"], "file123")
        self.assertEqual(msg["chunk_index"], 2)
    
    def test_chunk_response_message(self):
        """Test CHUNK_RESPONSE message building."""
        msg = MessageBuilder.chunk_response_message("file123", 2, 262144, "success")
        
        self.assertEqual(msg["type"], "CHUNK_RESPONSE")
        self.assertEqual(msg["file_id"], "file123")
        self.assertEqual(msg["chunk_index"], 2)
        self.assertEqual(msg["chunk_size"], 262144)
        self.assertEqual(msg["status"], "success")


class TestLargeFileChunking(unittest.TestCase):
    """Test chunking with larger files."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.test_dir = tempfile.mkdtemp()
        self.chunk_size = 262144  # 256 KB
        self.chunker = FileChunker(self.chunk_size)
    
    def tearDown(self):
        """Clean up test fixtures."""
        shutil.rmtree(self.test_dir, ignore_errors=True)
    
    def test_large_file_chunking(self):
        """Test chunking a larger file (1 MB)."""
        test_file = os.path.join(self.test_dir, "large_file.bin")
        file_size = 1024 * 1024  # 1 MB
        
        # Create test file
        with open(test_file, 'wb') as f:
            f.write(os.urandom(file_size))
        
        # Calculate hash
        with open(test_file, 'rb') as f:
            original_hash = hashlib.sha256(f.read()).hexdigest()
        
        # Split and merge
        chunks_dir = os.path.join(self.test_dir, "chunks")
        num_chunks = self.chunker.split_file(test_file, chunks_dir)
        
        merged_file = os.path.join(self.test_dir, "merged_file.bin")
        self.chunker.merge_chunks(chunks_dir, merged_file, num_chunks)
        
        # Verify hash matches
        with open(merged_file, 'rb') as f:
            merged_hash = hashlib.sha256(f.read()).hexdigest()
        
        self.assertEqual(original_hash, merged_hash, "Large file hash should match after merge")


if __name__ == "__main__":
    unittest.main()
