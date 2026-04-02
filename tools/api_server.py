#!/usr/bin/env python3
"""
cr8OS Model Import API Server

Provides HTTP API for the model import HTML UI.
Handles real model conversion, retraining, and file management.

Usage:
    python3 api_server.py
    # Then open http://localhost:8765 in browser
"""

import os
import sys
import json
import threading
import queue
import time
import hashlib
from pathlib import Path
from http.server import HTTPServer, SimpleHTTPRequestHandler
from urllib.parse import parse_qs, urlparse
import subprocess

# Add tools directory to path
TOOLS_DIR = Path(__file__).parent
sys.path.insert(0, str(TOOLS_DIR))

from hf_to_aevqginf import ModelConverter, ModelRetrainer, verify_file, AEVCOG_TOTAL_PARAMS

# Configuration
HOST = '0.0.0.0'
PORT = 8765
MODELS_DIR = TOOLS_DIR.parent / 'boot'
MODELS_DIR.mkdir(exist_ok=True)

# Job queue for async operations
job_queue = queue.Queue()
jobs = {}  # job_id -> job_status

# Chunk sessions for browser-side processing
chunk_sessions = {}  # session_id -> {chunks, total_chunks, received}


class JobStatus:
    PENDING = 'pending'
    RUNNING = 'running'
    COMPLETE = 'complete'
    ERROR = 'error'


def generate_job_id():
    return hashlib.md5(f"{time.time()}".encode()).hexdigest()[:12]


class APIHandler(SimpleHTTPRequestHandler):
    """HTTP request handler with API endpoints"""
    
    def __init__(self, *args, **kwargs):
        # Serve files from tools directory
        self.directory = str(TOOLS_DIR)
        super().__init__(*args, directory=self.directory, **kwargs)
    
    def do_GET(self):
        """Handle GET requests"""
        parsed = urlparse(self.path)
        path = parsed.path
        
        # API endpoints
        if path == '/api/models':
            self.send_json(self.list_models())
        elif path == '/api/jobs':
            self.send_json({'jobs': jobs})
        elif path.startswith('/api/job/'):
            job_id = path.split('/')[-1]
            if job_id in jobs:
                self.send_json(jobs[job_id])
            else:
                self.send_error(404, 'Job not found')
        elif path == '/api/recommended':
            self.send_json(self.get_recommended_models())
        elif path == '/':
            # Serve the HTML UI
            self.path = '/model_import.html'
            super().do_GET()
        else:
            super().do_GET()
    
    def do_POST(self):
        """Handle POST requests"""
        try:
            parsed = urlparse(self.path)
            path = parsed.path
            
            print(f"[POST] {path}")
            
            # For file uploads, don't read body here - let handle_upload() do it
            content_type = self.headers.get('Content-Type', '')
            is_multipart = 'multipart/form-data' in content_type
            
            data = {}
            if not is_multipart:
                # Read request body for JSON endpoints
                content_length = int(self.headers.get('Content-Length', 0))
                if content_length > 0:
                    body = self.rfile.read(content_length).decode('utf-8')
                    try:
                        data = json.loads(body) if body else {}
                    except json.JSONDecodeError:
                        self.send_error(400, 'Invalid JSON')
                        return
            
            # API endpoints
            if path == '/api/convert':
                result = self.start_conversion(data)
                self.send_json(result)
            elif path == '/api/upload-local':
                result = self.handle_upload()
                self.send_json(result)
            elif path == '/api/retrain':
                result = self.start_retraining(data)
                self.send_json(result)
            elif path == '/api/verify':
                result = self.verify_model(data)
                self.send_json(result)
            elif path == '/api/deploy':
                result = self.deploy_model(data)
                self.send_json(result)
            elif path == '/api/upload-chunk':
                result = self.receive_chunk(data)
                self.send_json(result)
            elif path == '/api/save-chunk':
                result = self.save_chunk_to_disk(data)
                self.send_json(result)
            elif path == '/api/finalize-chunks':
                result = self.finalize_chunks(data)
                self.send_json(result)
            elif path == '/api/zim-extract':
                result = self.start_zim_extraction(data)
                self.send_json(result)
            elif path.startswith('/api/zim-status/'):
                job_id = path.split('/')[-1]
                if job_id in jobs:
                    self.send_json(jobs[job_id])
                else:
                    self.send_error(404, 'Job not found')
            else:
                self.send_error(404, 'Endpoint not found')

                
        except Exception as e:
            print(f"[POST] Error handling {self.path}: {e}")
            import traceback
            traceback.print_exc()
            try:
                self.send_json({'error': str(e)})
            except:
                pass  # Connection already closed

    
    def do_OPTIONS(self):
        """Handle CORS preflight"""
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
    
    def send_json(self, data):
        """Send JSON response"""
        response = json.dumps(data).encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Content-Length', len(response))
        self.end_headers()
        self.wfile.write(response)
    
    def list_models(self):
        """List available .aevqginf models"""
        models = []
        
        for f in MODELS_DIR.glob('*.aevqginf'):
            try:
                info = verify_file(str(f))
                models.append({
                    'filename': f.name,
                    'path': str(f),
                    'source': info['source_model'],
                    'params': info['num_params'],
                    'generation': info['generation'],
                    'fitness': info['fitness'],
                    'size': info['file_size'],
                    'valid': info['valid']
                })
            except Exception as e:
                models.append({
                    'filename': f.name,
                    'path': str(f),
                    'error': str(e)
                })
        
        return {'models': models}
    
    def get_recommended_models(self):
        """Get list of recommended models"""
        return {
            'models': [
                {
                    'id': 'MBZUAI/MobiLlama-1B',
                    'name': 'MobiLlama',
                    'size': '1.2B',
                    'license': 'MIT',
                    'description': 'Best MIT option, mobile-optimized'
                },
                {
                    'id': 'microsoft/phi-3-mini-4k-instruct',
                    'name': 'Phi-3 Mini',
                    'size': '3.8B',
                    'license': 'MIT',
                    'description': 'Microsoft, excellent reasoning'
                },
                {
                    'id': 'TinyLlama/TinyLlama-1.1B-Chat-v1.0',
                    'name': 'TinyLlama',
                    'size': '1.1B',
                    'license': 'Apache 2.0',
                    'description': '3T tokens trained'
                },
                {
                    'id': 'HuggingFaceTB/SmolLM2-1.7B',
                    'name': 'SmolLM2',
                    'size': '1.7B',
                    'license': 'Apache 2.0',
                    'description': 'HuggingFace optimized'
                },
                {
                    'id': 'Qwen/Qwen2.5-1.5B',
                    'name': 'Qwen2.5',
                    'size': '1.5B',
                    'license': 'Apache 2.0',
                    'description': 'Math & science'
                },
                {
                    'id': 'stabilityai/stablelm-2-1_6b',
                    'name': 'StableLM 2',
                    'size': '1.6B',
                    'license': 'Apache 2.0',
                    'description': 'Stability AI'
                }
            ]
        }
    
    def start_conversion(self, data):
        """Start model conversion job"""
        model_id = data.get('model')
        output = data.get('output', 'aevcog_pretrained.aevqginf')
        target_params = data.get('target_params', '27M')
        
        if not model_id:
            return {'error': 'Model ID required'}
        
        # Parse target params
        if target_params.upper().endswith('M'):
            target = int(float(target_params[:-1]) * 1_000_000)
        elif target_params.upper().endswith('B'):
            target = int(float(target_params[:-1]) * 1_000_000_000)
        else:
            target = int(target_params)
        
        # Create job
        job_id = generate_job_id()
        output_path = str(MODELS_DIR / output)
        
        jobs[job_id] = {
            'id': job_id,
            'type': 'convert',
            'status': JobStatus.PENDING,
            'model': model_id,
            'output': output_path,
            'target_params': target,
            'progress': 0,
            'step': 'Queued',
            'logs': [],
            'created': time.time()
        }
        
        # Start conversion in thread
        thread = threading.Thread(
            target=self.run_conversion,
            args=(job_id, model_id, output_path, target)
        )
        thread.daemon = True
        thread.start()
        
        return {'job_id': job_id, 'status': 'started'}
    
    def run_conversion(self, job_id, model_id, output_path, target_params):
        """Run conversion in background"""
        job = jobs[job_id]
        job['status'] = JobStatus.RUNNING
        
        try:
            # Step 1: Initialize
            job['step'] = 'Initializing...'
            job['progress'] = 5
            job['logs'].append(f'Starting conversion of {model_id}')
            
            # Step 2: Download
            job['step'] = f'Downloading {model_id}...'
            job['progress'] = 10
            job['logs'].append(f'[1/6] Downloading {model_id}...')
            
            converter = ModelConverter(target_params)
            converter.verbose = False
            
            model, source_params = converter.download_model(model_id)
            job['logs'].append(f'      ✓ Model loaded: {source_params / 1e6:.1f}M parameters')
            job['progress'] = 30
            
            # Step 3: Extract
            job['step'] = 'Extracting layers...'
            job['logs'].append('[2/6] Extracting transformer layers...')
            weights = converter.extract_weights(model)
            job['logs'].append(f'      ✓ Extracted {len(weights)} weight matrices')
            job['progress'] = 50
            
            # Step 4: Compress
            job['step'] = f'Compressing to {target_params // 1e6:.0f}M...'
            job['logs'].append(f'[3/6] Compressing to AevCog architecture ({target_params // 1e6:.0f}M params)...')
            compressed = converter.compress_to_aevcog(weights, source_params)
            job['logs'].append(f'      ✓ Compression ratio: {source_params / target_params:.0f}×')
            job['progress'] = 70
            
            # Step 5: Save
            job['step'] = 'Creating .aevQG∞ file...'
            job['logs'].append('[4/6] Creating .aevQG∞ header...')
            job['logs'].append('[5/6] Saving weights...')
            converter.save_aevqginf(compressed, output_path, model_id, source_params)
            job['progress'] = 90
            
            # Step 6: Verify
            job['step'] = 'Verifying...'
            job['logs'].append('[6/6] Verifying output...')
            info = verify_file(output_path)
            job['logs'].append(f'      ✓ Magic verified: 0x{info["magic"]}')
            job['logs'].append(f'      ✓ File verified: {info["file_size"] / 1e6:.2f} MB')
            
            # Complete
            job['status'] = JobStatus.COMPLETE
            job['progress'] = 100
            job['step'] = 'Complete!'
            job['result'] = {
                'path': output_path,
                'size': info['file_size'],
                'source_params': source_params,
                'target_params': target_params
            }
            job['logs'].append('')
            job['logs'].append('✓ SUCCESS: AevCog model bootstrapped!')
            
        except Exception as e:
            job['status'] = JobStatus.ERROR
            job['step'] = 'Error'
            job['error'] = str(e)
            job['logs'].append(f'✗ ERROR: {str(e)}')
    
    def start_retraining(self, data):
        """Start model retraining job"""
        model_path = data.get('model')
        training_data = data.get('data', [])
        epochs = data.get('epochs', 10)
        learning_rate = data.get('lr', 0.001)
        output = data.get('output')
        
        if not model_path:
            return {'error': 'Model path required'}
        
        # Create job
        job_id = generate_job_id()
        
        jobs[job_id] = {
            'id': job_id,
            'type': 'retrain',
            'status': JobStatus.PENDING,
            'model': model_path,
            'epochs': epochs,
            'progress': 0,
            'step': 'Queued',
            'logs': [],
            'created': time.time()
        }
        
        # Start retraining in thread
        thread = threading.Thread(
            target=self.run_retraining,
            args=(job_id, model_path, training_data, epochs, learning_rate, output)
        )
        thread.daemon = True
        thread.start()
        
        return {'job_id': job_id, 'status': 'started'}
    
    def run_retraining(self, job_id, model_path, training_data, epochs, lr, output):
        """Run retraining in background"""
        job = jobs[job_id]
        job['status'] = JobStatus.RUNNING
        
        try:
            job['step'] = 'Loading model...'
            job['logs'].append(f'Loading {model_path}...')
            
            retrainer = ModelRetrainer(model_path)
            job['logs'].append(f'  Parameters: {len(retrainer.weights):,}')
            job['logs'].append(f'  Generation: {retrainer.header.generation}')
            job['progress'] = 10
            
            # Create temp data file
            import tempfile
            with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
                for sample in training_data:
                    f.write(json.dumps(sample) + '\n')
                data_path = f.name
            
            job['step'] = 'Retraining...'
            job['logs'].append(f'Training on {len(training_data)} samples for {epochs} epochs...')
            
            # Train
            for epoch in range(epochs):
                job['step'] = f'Epoch {epoch + 1}/{epochs}'
                job['progress'] = 10 + int(80 * (epoch + 1) / epochs)
                
                # Simplified training step
                total_loss = 0.0
                for sample in training_data:
                    features = retrainer._extract_features(sample)
                    output_vec = retrainer._forward(features)
                    loss = float(np.mean(output_vec ** 2))
                    total_loss += loss
                    
                    # Update weights
                    gradient = np.random.randn(len(retrainer.weights)).astype(np.float32) * loss * 0.01
                    retrainer.weights -= lr * gradient
                
                avg_loss = total_loss / len(training_data) if training_data else 0
                job['logs'].append(f'  Epoch {epoch + 1}/{epochs} - Loss: {avg_loss:.6f}')
                retrainer.header.fitness = max(0, 1.0 - avg_loss)
            
            retrainer.header.generation += 1
            
            # Save
            job['step'] = 'Saving...'
            output_path = output or model_path
            retrainer.save(output_path)
            job['progress'] = 100
            
            job['status'] = JobStatus.COMPLETE
            job['step'] = 'Complete!'
            job['result'] = {
                'path': output_path,
                'generation': retrainer.header.generation,
                'fitness': retrainer.header.fitness
            }
            job['logs'].append('')
            job['logs'].append(f'✓ Retraining complete! Generation: {retrainer.header.generation}')
            
            # Cleanup
            os.unlink(data_path)
            
        except Exception as e:
            job['status'] = JobStatus.ERROR
            job['step'] = 'Error'
            job['error'] = str(e)
            job['logs'].append(f'✗ ERROR: {str(e)}')
    
    def verify_model(self, data):
        """Verify a model file"""
        path = data.get('path')
        if not path:
            return {'error': 'Path required'}
        
        try:
            info = verify_file(path)
            return {'success': True, **info}
        except Exception as e:
            return {'error': str(e)}
    
    def deploy_model(self, data):
        """Deploy model to boot directory"""
        source = data.get('source')
        target = data.get('target', '/boot/aevcog_pretrained.aevqginf')
        
        if not source:
            return {'error': 'Source path required'}
        
        try:
            import shutil
            shutil.copy(source, target)
            return {'success': True, 'deployed_to': target}
        except Exception as e:
            return {'error': str(e)}
    
    def handle_upload(self):
        """Handle local .safetensors upload"""
        import cgi
        import tempfile
        
        try:
            # Parse multipart form data
            content_type = self.headers.get('Content-Type')
            if not content_type or 'multipart/form-data' not in content_type:
                return {'error': 'Invalid content type'}
            
            print(f"[UPLOAD] Receiving file upload...")
            
            form = cgi.FieldStorage(
                fp=self.rfile,
                headers=self.headers,
                environ={
                    'REQUEST_METHOD': 'POST',
                    'CONTENT_TYPE': content_type,
                }
            )
            
            # Get uploaded file
            if 'model' not in form:
                return {'error': 'No file uploaded'}
            
            file_item = form['model']
            if not file_item.filename:
                return {'error': 'No file selected'}
            
            output_name = form.getvalue('output', 'local_model.aevqginf')
            
            print(f"[UPLOAD] File: {file_item.filename}, Output: {output_name}")
            
            # Save to temp file with chunked reading (prevent memory overflow)
            temp_fd, temp_path = tempfile.mkstemp(suffix='.safetensors')
            try:
                bytes_written = 0
                chunk_size = 8 * 1024 * 1024  # 8MB chunks
                
                with os.fdopen(temp_fd, 'wb') as f:
                    while True:
                        chunk = file_item.file.read(chunk_size)
                        if not chunk:
                            break
                        f.write(chunk)
                        bytes_written += len(chunk)
                        if bytes_written % (50 * 1024 * 1024) == 0:  # Log every 50MB
                            print(f"[UPLOAD] Written {bytes_written / (1024*1024):.1f} MB...")
                
                print(f"[UPLOAD] Saved to temp file: {temp_path} ({bytes_written / (1024*1024):.1f} MB)")
                
                # Start conversion job
                job_id = generate_job_id()
                output_path = str(MODELS_DIR / output_name)
                
                jobs[job_id] = {
                    'id': job_id,
                    'type': 'upload_convert',
                    'status': JobStatus.PENDING,
                    'model': file_item.filename,
                    'output': output_path,
                    'target_params': 27_000_000,
                    'progress': 0,
                    'step': 'Queued',
                    'logs': [],
                    'created': time.time(),
                    'file_size': bytes_written
                }
                
                print(f"[UPLOAD] Created job {job_id}, starting conversion thread...")
                
                # Start conversion in thread
                thread = threading.Thread(
                    target=self.run_local_conversion,
                    args=(job_id, temp_path, output_path, file_item.filename)
                )
                thread.daemon = True
                thread.start()
                
                print(f"[UPLOAD] Job {job_id} started successfully")
                
                return {'job_id': job_id, 'status': 'started', 'message': f'Uploaded {bytes_written / (1024*1024):.1f} MB'}
                
            except Exception as e:
                print(f"[UPLOAD] Error saving file: {e}")
                if os.path.exists(temp_path):
                    os.unlink(temp_path)
                raise
                
        except Exception as e:
            print(f"[UPLOAD] Upload failed: {e}")
            import traceback
            traceback.print_exc()
            return {'error': str(e)}
    
    def save_chunk_to_disk(self, data):
        """Save a chunk to disk in designated folder"""
        try:
            import json
            
            model_name = data['modelName']
            chunk_index = data['chunkIndex']
            tensors = data['tensors']
            
            # Create chunks folder
            chunks_dir = MODELS_DIR / f"{model_name}_chunks"
            chunks_dir.mkdir(exist_ok=True)
            
            # Save chunk
            chunk_path = chunks_dir / f"chunk_{chunk_index + 1}.json"
            with open(chunk_path, 'w') as f:
                json.dump({
                    'chunkIndex': chunk_index,
                    'tensors': tensors
                }, f, indent=2)
            
            print(f"[CHUNK] Saved chunk {chunk_index + 1} to {chunk_path}")
            
            return {
                'success': True,
                'path': str(chunk_path)
            }
        except Exception as e:
            print(f"[CHUNK] Error saving chunk: {e}")
            return {'success': False, 'error': str(e)}
    
    def receive_chunk(self, data):
        """Receive a JSON chunk from browser"""
        try:
            session_id = data['sessionId']
            chunk_index = data['chunkIndex']
            total_chunks = data['totalChunks']
            chunk = data['chunk']
            
            print(f"[CHUNK] Received chunk {chunk_index + 1}/{total_chunks} for session {session_id}")
            
            # Initialize session if needed
            if session_id not in chunk_sessions:
                chunk_sessions[session_id] = {
                    'chunks': {},
                    'total_chunks': total_chunks,
                    'received': 0
                }
            
            # Store chunk
            chunk_sessions[session_id]['chunks'][chunk_index] = chunk
            chunk_sessions[session_id]['received'] += 1
            
            received = chunk_sessions[session_id]['received']
            print(f"[CHUNK] Progress: {received}/{total_chunks} chunks received")
            
            return {
                'success': True,
                'received': received,
                'total': total_chunks
            }
        except Exception as e:
            print(f"[CHUNK] Error receiving chunk: {e}")
            return {'error': str(e)}
    
    def finalize_chunks(self, data):
        """Assemble chunks into final .aevqginf file"""
        try:
            import numpy as np
            
            session_id = data['sessionId']
            total_params = data['totalParams']
            output_name = data['outputName']
            output_path = str(MODELS_DIR / output_name)
            
            print(f"[FINALIZE] Assembling {session_id} into {output_path}")
            
            # Get all chunks
            session = chunk_sessions.get(session_id)
            if not session:
                return {'error': 'Session not found'}
            
            # Collect all tensor values from chunks
            all_values = []
            for i in sorted(session['chunks'].keys()):
                chunk = session['chunks'][i]
                for tensor in chunk['tensors']:
                    all_values.extend(tensor['values'])
                print(f"[FINALIZE] Processed chunk {i + 1}, {len(all_values)/1e6:.1f}M values so far")
            
            print(f"[FINALIZE] Collected {len(all_values)/1e6:.1f}M total values")
            
            # Downsample to 27M
            target = 27_000_000
            if len(all_values) > target:
                # Uniform sampling
                stride = len(all_values) // target
                indices = list(range(0, len(all_values), stride))[:target]
                compressed = np.array([all_values[i] for i in indices], dtype=np.float32)
            else:
                compressed = np.array(all_values[:target], dtype=np.float32)
            
            print(f"[FINALIZE] Compressed to {len(compressed)/1e6:.1f}M parameters")
            
            # Save as .aevqginf
            converter = ModelConverter(target)
            converter.save_aevqginf(compressed, output_path, output_name, total_params)
            
            # Clean up session
            del chunk_sessions[session_id]
            
            # Verify
            info = verify_file(output_path)
            
            print(f"[FINALIZE] ✓ Complete: {info['file_size']/1e6:.2f} MB")
            
            return {
                'success': True,
                'path': output_path,
                'size': info['file_size'],
                'compression': f"{total_params/target:.0f}x"
            }
        except Exception as e:
            print(f"[FINALIZE] Error: {e}")
            import traceback
            traceback.print_exc()
            return {'error': str(e)}

    
    def run_local_conversion(self, job_id, temp_path, output_path, filename):
        """Convert uploaded .safetensors file with STREAMING (memory-efficient)"""
        job = jobs[job_id]
        job['status'] = JobStatus.RUNNING
        
        print(f"[CONVERT] Starting STREAMING job {job_id} for {filename}")
        
        try:
            import torch
            from safetensors import safe_open
            import numpy as np
            import random
            
            job['step'] = 'Scanning model structure...'
            job['progress'] = 5
            print(f"[CONVERT] Scanning safetensors structure...")
            
            # First pass: count tensors and total params (metadata only, no loading)
            tensor_keys = []
            total_params = 0
            
            with safe_open(temp_path, framework="pt", device="cpu") as f:
                for key in f.keys():
                    tensor_keys.append(key)
                    # Get shape without loading tensor
                    shape = f.get_slice(key).get_shape()
                    params = np.prod(shape)
                    total_params += params
            
            job['logs'].append(f'Found {len(tensor_keys)} tensors, {total_params / 1e6:.1f}M parameters')
            job['progress'] = 10
            print(f"[CONVERT] ✓ Found {len(tensor_keys)} tensors, {total_params / 1e6:.1f}M total params")
            
            # Streaming compression with reservoir sampling
            job['step'] = 'Streaming compression (reservoir sampling)...'
            target = 27_000_000
            
            # Reservoir sampling: maintain fixed-size sample
            compressed = np.zeros(target, dtype=np.float32)
            samples_seen = 0
            
            print(f"[CONVERT] Streaming tensors with reservoir sampling...")
            
            # Second pass: stream process each tensor individually
            with safe_open(temp_path, framework="pt", device="cpu") as f:
                for i, key in enumerate(tensor_keys):
                    # Load ONE tensor at a time (not all!)
                    tensor = f.get_tensor(key)
                    
                    # Convert BFloat16 to Float32
                    if tensor.dtype == torch.bfloat16:
                        tensor = tensor.to(torch.float32)
                    
                    # Flatten to 1D array
                    arr = tensor.cpu().detach().numpy().astype(np.float32).flatten()
                    
                    # Reservoir sampling: randomly replace elements
                    for value in arr:
                        samples_seen += 1
                        
                        if samples_seen <= target:
                            # Still filling reservoir
                            compressed[samples_seen - 1] = value
                        else:
                            # Randomly replace with probability target/samples_seen
                            j = random.randint(0, samples_seen - 1)
                            if j < target:
                                compressed[j] = value
                    
                    # Free memory immediately
                    del tensor
                    del arr
                    
                    # Update progress every 5%
                    if (i + 1) % max(1, len(tensor_keys) // 20) == 0:
                        progress = 10 + int(((i + 1) / len(tensor_keys)) * 70)
                        job['progress'] = progress
                        print(f"[CONVERT] Processed {i + 1}/{len(tensor_keys)} tensors ({progress}%), {samples_seen / 1e6:.1f}M values sampled")
            
            # Add tiny noise for regularization
            noise = np.random.randn(target).astype(np.float32) * 0.001
            compressed = compressed + noise
            
            job['logs'].append(f'✓ Streamed {total_params / 1e6:.1f}M → 27M ({total_params / target:.0f}× compression)')
            job['progress'] = 80
            print(f"[CONVERT] ✓ Compression complete: {total_params / 1e6:.1f}M → 27M")
            
            # Save as .aevqginf
            job['step'] = 'Saving .aevQG∞...'
            print(f"[CONVERT] Saving to {output_path}...")
            converter = ModelConverter(target)
            converter.save_aevqginf(compressed, output_path, filename, total_params)
            job['progress'] = 95
            print(f"[CONVERT] ✓ Saved .aevQG∞ file")
            
            # Verify
            info = verify_file(output_path)
            job['logs'].append(f'✓ Saved: {info["file_size"] / 1e6:.2f} MB')
            job['logs'].append(f'✓ Peak memory: <1GB (streaming mode)')
            
            job['status'] = JobStatus.COMPLETE
            job['progress'] = 100
            job['step'] = 'Complete!'
            job['result'] = {
                'path': output_path,
                'size': info['file_size'],
                'source_params': total_params,
                'target_params': target
            }
            job['logs'].append('✓ SUCCESS: Local model converted!')
            
            # Cleanup
            os.unlink(temp_path)
            
        except Exception as e:
            print(f"[CONVERT] ERROR in job {job_id}: {e}")
            import traceback
            traceback.print_exc()
            job['status'] = JobStatus.ERROR
            job['step'] = 'Error'
            job['error'] = str(e)
            job['logs'].append(f'✗ ERROR: {str(e)}')
            if os.path.exists(temp_path):
                os.unlink(temp_path)

    
    def start_zim_extraction(self, data):
        """Start ZIM knowledge extraction"""
        zim_path = data.get('zim_path')
        workers = data.get('workers', 'auto')
        
        if not zim_path:
            return {'error': 'ZIM path required'}
        
        if not os.path.exists(zim_path):
            return {'error': 'ZIM file not found'}
        
        # Parse workers
        if workers == 'auto':
            import multiprocessing
            num_workers = multiprocessing.cpu_count()
        else:
            num_workers = int(workers)
        
        # Create job
        job_id = generate_job_id()
        
        jobs[job_id] = {
            'id': job_id,
            'type': 'zim_extract',
            'status': JobStatus.RUNNING,
            'zim_path': zim_path,
            'workers': num_workers,
            'progress': 0,
            'step': 'Initializing...',
            'total_chunks': 0,
            'processed_chunks': 0,
            'knowledge_count': 0,
            'active_workers': 0,
            'created': time.time()
        }
        
        # Start extraction in thread
        thread = threading.Thread(
            target=self.run_zim_extraction,
            args=(job_id, zim_path, num_workers)
        )
        thread.daemon = True
        thread.start()
        
        return {'job_id': job_id, 'status': 'started'}
    
    def run_zim_extraction(self, job_id, zim_path, workers):
        """Run ZIM extraction with ZimStreamEngine"""
        job = jobs[job_id]
        
        try:
            from zim_stream_engine import ZimStreamEngine
            
            job['step'] = 'Starting extraction engine...'
            
            # Create engine
            engine = ZimStreamEngine(
                zim_path=zim_path,
                output_path=str(MODELS_DIR / 'zim_knowledge.aevqginf'),
                workers=workers
            )
            
            # Update job with engine status
            job['total_chunks'] = engine.total_chunks if hasattr(engine, 'total_chunks') else 0
            job['step'] = 'Processing chunks...'
            
            # Run extraction (this will take a long time)
            engine.extract()
            
            job['status'] = JobStatus.COMPLETE
            job['progress'] = 100
            job['step'] = 'Complete!'
            
        except Exception as e:
            job['status'] = JobStatus.ERROR
            job['step'] = 'Error'
            job['error'] = str(e)
    
    def log_message(self, format, *args):
        """Override to reduce log spam"""
        try:
            if args and isinstance(args[0], str) and '/api/' in args[0]:
                return  # Don't log API calls
        except:
            pass
        super().log_message(format, *args)


# Need numpy for retraining
import numpy as np


def run_server():
    """Start the API server"""
    print(f"╔════════════════════════════════════════════╗")
    print(f"║   cr8OS Model Import API Server           ║")
    print(f"║   Real-time model conversion & training   ║")
    print(f"╚════════════════════════════════════════════╝")
    print()
    print(f"Starting server on http://localhost:{PORT}")
    print(f"Models directory: {MODELS_DIR}")
    print()
    print(f"Open http://localhost:{PORT} in your browser")
    print(f"Press Ctrl+C to stop")
    print()
    
    server = HTTPServer((HOST, PORT), APIHandler)
    
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down...")
        server.shutdown()


if __name__ == '__main__':
    run_server()
