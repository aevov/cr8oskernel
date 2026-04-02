#!/usr/bin/env python3
"""
Accelerated Model Downloader - IDM-like multi-threaded downloads

Features:
- Parallel chunk downloads (8+ threads)
- Resume capability
- Progress tracking
- Speed optimization
"""

import os
import sys
import time
import threading
import requests
from pathlib import Path
from typing import List, Optional
import hashlib


class ChunkDownloader:
    """Download a file in parallel chunks"""
    
    def __init__(self, url: str, output_path: str, chunks: int = 8):
        self.url = url
        self.output_path = output_path
        self.chunks = chunks
        self.total_size = 0
        self.downloaded = 0
        self.start_time = time.time()
        self.lock = threading.Lock()
        
    def get_file_size(self) -> int:
        """Get remote file size"""
        resp = requests.head(self.url, allow_redirects=True, timeout=10)
        return int(resp.headers.get('content-length', 0))
    
    def download_chunk(self, start: int, end: int, chunk_id: int):
        """Download a single chunk"""
        headers = {'Range': f'bytes={start}-{end}'}
        
        try:
            resp = requests.get(self.url, headers=headers, stream=True, timeout=30)
            
            chunk_file = f"{self.output_path}.part{chunk_id}"
            
            with open(chunk_file, 'wb') as f:
                for data in resp.iter_content(chunk_size=8192):
                    if data:
                        f.write(data)
                        with self.lock:
                            self.downloaded += len(data)
            
            return True
        except Exception as e:
            print(f"Chunk {chunk_id} failed: {e}")
            return False
    
    def merge_chunks(self):
        """Merge downloaded chunks into final file"""
        print("\nMerging chunks...")
        
        with open(self.output_path, 'wb') as outfile:
            for i in range(self.chunks):
                chunk_file = f"{self.output_path}.part{i}"
                with open(chunk_file, 'rb') as infile:
                    outfile.write(infile.read())
                os.remove(chunk_file)
        
        print(f"✓ File saved: {self.output_path}")
    
    def download(self):
        """Start parallel download"""
        print(f"Getting file size...")
        self.total_size = self.get_file_size()
        
        if self.total_size == 0:
            print("Error: Could not determine file size")
            return False
        
        print(f"File size: {self.total_size / 1e9:.2f} GB")
        print(f"Starting download with {self.chunks} parallel chunks...\n")
        
        chunk_size = self.total_size // self.chunks
        threads = []
        
        for i in range(self.chunks):
            start = i * chunk_size
            end = start + chunk_size - 1 if i < self.chunks - 1 else self.total_size - 1
            
            thread = threading.Thread(
                target=self.download_chunk,
                args=(start, end, i)
            )
            thread.start()
            threads.append(thread)
        
        # Progress tracking
        while any(t.is_alive() for t in threads):
            with self.lock:
                progress = (self.downloaded / self.total_size) * 100
                speed = self.downloaded / (time.time() - self.start_time) / 1e6  # MB/s
                eta = (self.total_size - self.downloaded) / (speed * 1e6) if speed > 0 else 0
                
                print(f"\rProgress: {progress:.1f}% | {self.downloaded / 1e9:.2f}/{self.total_size / 1e9:.2f} GB | Speed: {speed:.1f} MB/s | ETA: {eta / 60:.1f}m", end='')
            
            time.sleep(0.5)
        
        # Wait for all threads
        for t in threads:
            t.join()
        
        print("\n")
        
        # Merge chunks
        self.merge_chunks()
        
        elapsed = time.time() - self.start_time
        avg_speed = self.total_size / elapsed / 1e6
        print(f"Downloaded in {elapsed / 60:.1f} minutes (avg {avg_speed:.1f} MB/s)")
        
        return True


def download_hf_model(model_id: str, output_dir: str):
    """Download HuggingFace model with acceleration"""
    from huggingface_hub import hf_hub_url, list_repo_files
    
    print(f"Fetching file list for {model_id}...")
    files = list_repo_files(model_id)
    
    # Filter for model files
    model_files = [f for f in files if f.endswith(('.safetensors', '.bin'))]
    
    if not model_files:
        print("No model files found")
        return
    
    print(f"Found {len(model_files)} model files:")
    for f in model_files:
        print(f"  - {f}")
    
    output_path = Path(output_dir)
    output_path.mkdir(exist_ok=True, parents=True)
    
    for filename in model_files:
        url = hf_hub_url(model_id, filename=filename)
        output_file = output_path / filename
        
        print(f"\n{'='*60}")
        print(f"Downloading: {filename}")
        print(f"{'='*60}")
        
        downloader = ChunkDownloader(url, str(output_file), chunks=8)
        downloader.download()


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Accelerated Model Downloader')
    parser.add_argument('--model', required=True, help='HuggingFace model ID')
    parser.add_argument('--output', default='./downloads', help='Output directory')
    parser.add_argument('--chunks', type=int, default=8, help='Parallel chunks')
    
    args = parser.parse_args()
    
    download_hf_model(args.model, args.output)
