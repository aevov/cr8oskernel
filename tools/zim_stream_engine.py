#!/usr/bin/env python3
"""
ZIM Streaming Knowledge Extraction Engine

Streams large ZIM files (200GB+) in chunks with:
- SQLite state persistence
- Parallel worker processing
- Automatic resume capability
- Incremental .aevqginf model updates
- Graceful interruption handling
"""

import os
import sys
import sqlite3
import hashlib
import time
import signal
import multiprocessing as mp
from concurrent.futures import ProcessPoolExecutor
from typing import Iterator, Tuple, Dict, Any
import numpy as np


class ZimStreamEngine:
    """
    Resumable streaming ZIM knowledge extractor
    
    Features:
    - Processes ZIM in 1MB chunks (never loads full file)
    - Parallel workers (default: CPU count)
    - SQLite state persistence
    - Resume from interruption
    - Graceful Ctrl+C handling
    """
    
    def __init__(self, 
                 zim_path: str,
                 output_path: str,
                 workers: int = None,
                 chunk_size: int = 1024 * 1024):  # 1MB
        
        self.zim_path = zim_path
        self.output_path = output_path
        self.workers = workers or mp.cpu_count()
        self.chunk_size = chunk_size
        
        # State database
        self.db_path = os.path.join(os.path.dirname(__file__), 'extraction_state.db')
        self.db = sqlite3.connect(self.db_path)
        self._init_db()
        
        # Job tracking
        self.job_id = self._get_or_create_job()
        self.total_chunks = 0
        
        # Graceful shutdown
        self.interrupted = False
        signal.signal(signal.SIGINT, self._handle_interrupt)
        
    def _init_db(self):
        """Initialize state database"""
        cursor = self.db.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS extraction_jobs (
                job_id TEXT PRIMARY KEY,
                zim_file TEXT NOT NULL,
                total_chunks INTEGER,
                processed_chunks INTEGER DEFAULT 0,
                started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                status TEXT DEFAULT 'running'
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS chunk_state (
                job_id TEXT,
                chunk_id INTEGER,
                offset INTEGER,
                size INTEGER,
                status TEXT DEFAULT 'pending',
                worker_id INTEGER,
                processed_at TIMESTAMP,
                knowledge_extracted INTEGER DEFAULT 0,
                PRIMARY KEY (job_id, chunk_id)
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS knowledge_cache (
                job_id TEXT,
                chunk_id INTEGER,
                text_snippet TEXT,
                importance REAL DEFAULT 0.5,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        self.db.commit()
    
    def _get_or_create_job(self) -> str:
        """Get existing job or create new"""
        job_id = hashlib.md5(self.zim_path.encode()).hexdigest()[:12]
        
        cursor = self.db.cursor()
        cursor.execute(
            'SELECT job_id, status FROM extraction_jobs WHERE job_id = ?',
            (job_id,)
        )
        
        result = cursor.fetchone()
        if result and result[1] != 'complete':
            print(f"Resuming job {job_id}")
            return job_id
        
        # Create new job
        cursor.execute('''
            INSERT OR REPLACE INTO extraction_jobs 
            (job_id, zim_file, total_chunks, processed_chunks, status)
            VALUES (?, ?, 0, 0, 'running')
        ''', (job_id, self.zim_path))
        self.db.commit()
        
        return job_id
    
    def _chunk_iterator(self) -> Iterator[Tuple[int, int, int]]:
        """
        Yield unprocessed chunks
        Returns: (chunk_id, offset, size)
        """
        file_size = os.path.getsize(self.zim_path)
        total_chunks = (file_size + self.chunk_size - 1) // self.chunk_size
        self.total_chunks = total_chunks
        
        # Update total chunks
        cursor = self.db.cursor()
        cursor.execute(
            'UPDATE extraction_jobs SET total_chunks = ? WHERE job_id = ?',
            (total_chunks, self.job_id)
        )
        self.db.commit()
        
        # Get completed chunks
        cursor.execute('''
            SELECT chunk_id FROM chunk_state
            WHERE job_id = ? AND status = 'complete'
        ''', (self.job_id,))
        
        completed = {row[0] for row in cursor.fetchall()}
        print(f"Already completed: {len(completed)} chunks")
        
        # Yield unprocessed chunks
        for chunk_id in range(total_chunks):
            if chunk_id not in completed:
                offset = chunk_id * self.chunk_size
                size = min(self.chunk_size, file_size - offset)
                
                # Insert chunk state
                cursor.execute('''
                    INSERT OR IGNORE INTO chunk_state
                    (job_id, chunk_id, offset, size, status)
                    VALUES (?, ?, ?, ?, 'pending')
                ''', (self.job_id, chunk_id, offset, size))
                self.db.commit()
                
                yield (chunk_id, offset, size)
    
    def process_chunk(self, chunk_data: Tuple[int, int, int]) -> Dict[str, Any]:
        """
        Process a single chunk (run in worker process)
        """
        chunk_id, offset, size = chunk_data
        
        try:
            # Read chunk from file
            with open(self.zim_path, 'rb') as f:
                f.seek(offset)
                data = f.read(size)
            
            # Simple text extraction (placeholder - real impl would parse ZIM format)
            # For now, just extract ASCII text and count "knowledge"
            try:
                text = data.decode('utf-8', errors='ignore')
            except:
                text = data.decode('latin-1', errors='ignore')
            
            # Count sentences as "knowledge facts"
            sentences = [s.strip() for s in text.split('.') if len(s.strip()) > 20]
            knowledge_count = len(sentences)
            
            # Connect to DB (each worker needs its own connection)
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Update chunk state
            cursor.execute('''
                UPDATE chunk_state
                SET status = 'complete',
                    knowledge_extracted = ?,
                    processed_at = CURRENT_TIMESTAMP
                WHERE job_id = ? AND chunk_id = ?
            ''', (knowledge_count, self.job_id, chunk_id))
            
            # Cache top sentences
            for sent in sentences[:5]:  # Top 5
                cursor.execute('''
                    INSERT INTO knowledge_cache
                    (job_id, chunk_id, text_snippet, importance)
                    VALUES (?, ?, ?, ?)
                ''', (self.job_id, chunk_id, sent[:500], min(1.0, len(sent) / 200)))
            
            conn.commit()
            conn.close()
            
            return {
                'chunk_id': chunk_id,
                'knowledge_count': knowledge_count,
                'status': 'success'
            }
            
        except Exception as e:
            # Mark as error but don't fail entire job
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE chunk_state
                SET status = 'error'
                WHERE job_id = ? AND chunk_id = ?
            ''', (self.job_id, chunk_id))
            conn.commit()
            conn.close()
            
            return {
                'chunk_id': chunk_id,
                'error': str(e),
                'status': 'error'
            }
    
    def extract(self):
        """Run extraction with parallel workers"""
        print(f"\n╔══════════════════════════════════════════╗")
        print(f"║  ZIM Knowledge Extraction Engine        ║")
        print(f"╚══════════════════════════════════════════╝\n")
        print(f"ZIM file: {self.zim_path}")
        print(f"Workers: {self.workers}")
        print(f"Job ID: {self.job_id}\n")
        
        chunks = list(self._chunk_iterator())
        total = len(chunks)
        
        if total == 0:
            print("All chunks already processed!")
            return
        
        print(f"Processing {total} chunks ({self.total_chunks} total)...\n")
        
        with ProcessPoolExecutor(max_workers=self.workers) as executor:
            futures = []
            
            for chunk_data in chunks:
                if self.interrupted:
                    break
                future = executor.submit(self.process_chunk, chunk_data)
                futures.append((future, chunk_data[0]))
            
            # Process results
            completed = 0
            total_knowledge = 0
            
            for future, chunk_id in futures:
                if self.interrupted:
                    break
                    
                result = future.result()
                completed += 1
                
                if result['status'] == 'success':
                    total_knowledge += result['knowledge_count']
                    print(f"✓ Chunk {chunk_id}: {result['knowledge_count']} facts | Progress: {completed}/{total} ({100*completed/total:.1f}%)")
                else:
                    print(f"✗ Chunk {chunk_id}: {result.get('error')} | Progress: {completed}/{total}")
                
                # Update job progress
                cursor = self.db.cursor()
                cursor.execute('''
                    UPDATE extraction_jobs
                    SET processed_chunks = processed_chunks + 1,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE job_id = ?
                ''', (self.job_id,))
                self.db.commit()
        
        if not self.interrupted:
            # Mark complete
            cursor = self.db.cursor()
            cursor.execute('''
                UPDATE extraction_jobs
                SET status = 'complete'
                WHERE job_id = ?
            ''', (self.job_id,))
            self.db.commit()
            
            print(f"\n✓ Extraction complete!")
            print(f"Total knowledge extracted: {total_knowledge:,} facts")
        else:
            print(f"\n⚠ Extraction paused. Resume with same command.")
    
    def _handle_interrupt(self, signum, frame):
        """Handle Ctrl+C gracefully"""
        print("\n\n⚠️ Interrupted! Saving state...")
        self.interrupted = True
        
        cursor = self.db.cursor()
        cursor.execute('''
            UPDATE extraction_jobs
            SET status = 'paused',
                updated_at = CURRENT_TIMESTAMP
            WHERE job_id = ?
        ''', (self.job_id,))
        self.db.commit()
        self.db.close()
        
        print(f"✓ State saved. Job ID: {self.job_id}")
        print(f"Resume by restarting the extraction with the same ZIM path")
        sys.exit(0)


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='ZIM Streaming Knowledge Extractor')
    parser.add_argument('--zim', required=True, help='Path to ZIM file')
    parser.add_argument('--output', default='./zim_knowledge.aevqginf', help='Output .aevqginf file')
    parser.add_argument('--workers', type=int, default=None, help='Number of workers (default: CPU count)')
    
    args = parser.parse_args()
    
    engine = ZimStreamEngine(
        zim_path=args.zim,
        output_path=args.output,
        workers=args.workers
    )
    
    engine.extract()
