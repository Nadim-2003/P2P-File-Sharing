#!/usr/bin/env python3
"""
Quick Start Guide for P2P File-Sharing System

This script demonstrates how to use the system with simple examples.
"""

import sys
import os

# Add project to path
sys.path.insert(0, os.path.dirname(__file__))

from shared.chunking import FileChunker
from shared.utils import FileUtils, MessageBuilder
import tempfile
import shutil

def example_chunking():
    """Example 1: File Chunking"""
    print("\n" + "="*60)
    print("EXAMPLE 1: File Chunking and Merging")
    print("="*60)
    
    # Create temporary directory
    test_dir = tempfile.mkdtemp()
    
    try:
        # Create a test file
        test_file = os.path.join(test_dir, "test_data.txt")
        print(f"\n1. Creating test file: {test_file}")
        with open(test_file, 'w') as f:
            f.write("Hello from P2P System! " * 10000)  # ~230 KB
        
        file_size = FileUtils.get_file_size(test_file)
        print(f"   File size: {file_size} bytes")
        
        # Initialize chunker with 256 KB chunks
        chunk_size = 256 * 1024
        chunker = FileChunker(chunk_size)
        print(f"\n2. Chunking with size: {chunk_size} bytes")
        
        # Split file into chunks
        chunks_dir = os.path.join(test_dir, "chunks")
        num_chunks = chunker.split_file(test_file, chunks_dir)
        print(f"   Created {num_chunks} chunks")
        
        # Display chunk information
        for i in range(num_chunks):
            chunk_size_actual = chunker.get_chunk_size(chunks_dir, i)
            print(f"   Chunk {i}: {chunk_size_actual} bytes")
        
        # Merge chunks back
        merged_file = os.path.join(test_dir, "merged_file.txt")
        print(f"\n3. Merging chunks into: {merged_file}")
        success = chunker.merge_chunks(chunks_dir, merged_file, num_chunks)
        
        if success:
            print("   Merge successful!")
            
            # Verify files are identical
            with open(test_file, 'rb') as f1:
                original = f1.read()
            with open(merged_file, 'rb') as f2:
                merged = f2.read()
            
            if original == merged:
                print("   ✓ Original and merged files are identical!")
            else:
                print("   ✗ Files differ!")
        
        # Verify chunks
        verified = chunker.verify_chunks(chunks_dir, num_chunks)
        print(f"\n4. Chunk verification: {'✓ PASSED' if verified else '✗ FAILED'}")
        
        total_size = chunker.get_total_size(chunks_dir, num_chunks)
        print(f"   Total chunk size: {total_size} bytes")
        
    finally:
        # Cleanup
        shutil.rmtree(test_dir, ignore_errors=True)
        print(f"\n5. Cleaned up temporary files")


def example_file_utils():
    """Example 2: File Utilities"""
    print("\n" + "="*60)
    print("EXAMPLE 2: File Utilities")
    print("="*60)
    
    test_dir = tempfile.mkdtemp()
    
    try:
        # Create test file
        test_file = os.path.join(test_dir, "test.bin")
        file_size = 1024 * 1024  # 1 MB
        print(f"\n1. Creating {file_size} byte file")
        
        with open(test_file, 'wb') as f:
            f.write(b"X" * file_size)
        
        # Get file size
        size = FileUtils.get_file_size(test_file)
        print(f"   File size: {size} bytes = {size/1024/1024:.2f} MB")
        
        # Calculate chunks needed
        chunk_size = 256 * 1024
        num_chunks = FileUtils.calculate_num_chunks(file_size, chunk_size)
        print(f"\n2. With chunk size {chunk_size} bytes:")
        print(f"   Number of chunks: {num_chunks}")
        print(f"   Bytes per chunk: {chunk_size}")
        
        # Validate chunk size
        valid_sizes = [262144, 512000, 100, 2000000]
        print(f"\n3. Chunk size validation:")
        for size in valid_sizes:
            valid = FileUtils.validate_chunk_size(size)
            status = "✓ Valid" if valid else "✗ Invalid"
            print(f"   {size} bytes: {status}")
        
    finally:
        shutil.rmtree(test_dir, ignore_errors=True)


def example_messages():
    """Example 3: Message Protocol"""
    print("\n" + "="*60)
    print("EXAMPLE 3: Protocol Messages")
    print("="*60)
    
    print("\n1. REGISTER Message (Share a file)")
    register_msg = MessageBuilder.register_message(
        "a1b2c3d4e5f6g7h8", "movie.mp4", 40, "peer-001", 
        "192.168.1.100", 6000
    )
    import json
    print(json.dumps(register_msg, indent=2))
    
    print("\n2. QUERY Message (Request file info)")
    query_msg = MessageBuilder.query_message("a1b2c3d4e5f6g7h8")
    print(json.dumps(query_msg, indent=2))
    
    print("\n3. CHUNK_REQUEST Message (Download chunk)")
    chunk_req_msg = MessageBuilder.chunk_request_message("a1b2c3d4e5f6g7h8", 5)
    print(json.dumps(chunk_req_msg, indent=2))
    
    print("\n4. CHUNK_RESPONSE Message (Serve chunk)")
    chunk_resp_msg = MessageBuilder.chunk_response_message(
        "a1b2c3d4e5f6g7h8", 5, 262144, "success"
    )
    print(json.dumps(chunk_resp_msg, indent=2))


def main():
    """Run all examples"""
    print("\n" + "="*60)
    print("P2P FILE-SHARING SYSTEM - QUICK START EXAMPLES")
    print("="*60)
    
    try:
        example_chunking()
        example_file_utils()
        example_messages()
        
        print("\n" + "="*60)
        print("NEXT STEPS:")
        print("="*60)
        print("\n1. Start the tracker server:")
        print("   python tracker/tracker_server.py")
        print("\n2. Start peer clients in separate terminals:")
        print("   python peer/peer_client.py")
        print("\n3. Use the GUI to share and download files!")
        print("\n" + "="*60)
        
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
