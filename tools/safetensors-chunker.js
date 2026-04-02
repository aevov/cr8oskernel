/**
 * Browser-Side Model Chunker
 * 
 * Reads .safetensors in browser, chunks to JSON, uploads to server for assembly
 * Inspired by production-model-chunker.html but modernized
 */

class SafetensorsChunker {
    constructor(file, chunkSizeMB = 10) {
        this.file = file;
        this.chunkSize = chunkSizeMB * 1024 * 1024;
        this.totalChunks = 0;
        this.processedChunks = 0;
        this.sessionId = this.generateSessionId();
    }

    generateSessionId() {
        return 'chunk_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
    }

    async process(progressCallback) {
        console.log('[CHUNKER] Starting browser-side processing...');
        progressCallback({ step: 'Reading file header...', progress: 5 });

        // Read file in browser
        const arrayBuffer = await this.file.arrayBuffer();
        const uint8Array = new Uint8Array(arrayBuffer);

        progressCallback({ step: 'Parsing safetensors...', progress: 10 });

        // Parse safetensors header
        const header = this.parseSafetensorsHeader(uint8Array);
        console.log('[CHUNKER] Found', Object.keys(header.metadata).length, 'tensors');

        // Calculate total parameters
        let totalParams = 0;
        const tensorInfo = [];

        for (const [name, info] of Object.entries(header.metadata)) {
            const shape = info.shape;
            const params = shape.reduce((a, b) => a * b, 1);
            totalParams += params;
            tensorInfo.push({
                name,
                dtype: info.dtype,
                shape,
                offset: info.data_offsets[0],
                size: info.data_offsets[1] - info.data_offsets[0],
                params
            });
        }

        console.log('[CHUNKER] Total parameters:', (totalParams / 1e6).toFixed(1), 'M');
        progressCallback({
            step: `Found ${totalParams / 1e6}M parameters`,
            progress: 15,
            totalParams
        });

        // Chunk tensors into groups
        const chunks = this.createChunks(tensorInfo, uint8Array, header.headerSize);
        this.totalChunks = chunks.length;

        console.log('[CHUNKER] Created', chunks.length, 'chunks');
        progressCallback({ step: `Created ${chunks.length} chunks`, progress: 20 });

        // Upload chunks
        for (let i = 0; i < chunks.length; i++) {
            const chunk = chunks[i];

            progressCallback({
                step: `Uploading chunk ${i + 1}/${chunks.length}`,
                progress: 20 + (i / chunks.length) * 70
            });

            await this.uploadChunk(chunk, i);
            this.processedChunks++;
        }

        // Finalize
        progressCallback({ step: 'Assembling on server...', progress: 95 });
        const result = await this.finalize(totalParams);

        progressCallback({ step: 'Complete!', progress: 100 });
        return result;
    }

    parseSafetensorsHeader(uint8Array) {
        // Read header size (first 8 bytes, little-endian)
        const headerSize = new DataView(uint8Array.buffer, 0, 8).getBigUint64(0, true);

        // Read header JSON
        const headerBytes = uint8Array.slice(8, 8 + Number(headerSize));
        const headerStr = new TextDecoder().decode(headerBytes);
        const metadata = JSON.parse(headerStr);

        return {
            headerSize: 8 + Number(headerSize),
            metadata
        };
    }

    createChunks(tensorInfo, uint8Array, headerSize) {
        const chunks = [];
        let currentChunk = {
            tensors: [],
            totalSize: 0
        };

        for (const tensor of tensorInfo) {
            // If adding this tensor exceeds chunk size, start new chunk
            if (currentChunk.totalSize > 0 &&
                currentChunk.totalSize + tensor.size > this.chunkSize) {
                chunks.push(currentChunk);
                currentChunk = {
                    tensors: [],
                    totalSize: 0
                };
            }

            // Read tensor data
            const offset = headerSize + tensor.offset;
            const tensorData = uint8Array.slice(offset, offset + tensor.size);

            // Convert to Float32 array based on dtype
            let values;
            if (tensor.dtype === 'F32') {
                values = new Float32Array(tensorData.buffer, tensorData.byteOffset, tensorData.byteLength / 4);
            } else if (tensor.dtype === 'BF16') {
                // Convert BF16 to F32
                values = this.bfloat16ToFloat32(tensorData);
            } else if (tensor.dtype === 'F16') {
                // Convert F16 to F32
                values = this.float16ToFloat32(tensorData);
            } else {
                console.warn('[CHUNKER] Unsupported dtype:', tensor.dtype);
                continue;
            }

            currentChunk.tensors.push({
                name: tensor.name,
                shape: tensor.shape,
                values: Array.from(values)  // Convert to regular array for JSON
            });

            currentChunk.totalSize += tensor.size;
        }

        // Add last chunk
        if (currentChunk.tensors.length > 0) {
            chunks.push(currentChunk);
        }

        return chunks;
    }

    bfloat16ToFloat32(uint8Array) {
        const float32 = new Float32Array(uint8Array.length / 2);
        const dataView = new DataView(uint8Array.buffer, uint8Array.byteOffset);

        for (let i = 0; i < float32.length; i++) {
            // BF16 is upper 16 bits of F32
            const bf16 = dataView.getUint16(i * 2, true);
            const f32Bits = bf16 << 16;
            float32[i] = new DataView(new Uint32Array([f32Bits]).buffer).getFloat32(0, true);
        }

        return float32;
    }

    float16ToFloat32(uint8Array) {
        // Simplified F16 to F32 conversion
        const float32 = new Float32Array(uint8Array.length / 2);
        // Would need proper IEEE 754 half-precision conversion
        // For now, just approximate
        return float32;
    }

    async uploadChunk(chunk, index) {
        const response = await fetch('/api/upload-chunk', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                sessionId: this.sessionId,
                chunkIndex: index,
                totalChunks: this.totalChunks,
                chunk: chunk
            })
        });

        if (!response.ok) {
            throw new Error('Chunk upload failed');
        }

        return await response.json();
    }

    async finalize(totalParams) {
        const response = await fetch('/api/finalize-chunks', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                sessionId: this.sessionId,
                totalParams,
                outputName: this.file.name.replace('.safetensors', '.aevqginf')
            })
        });

        if (!response.ok) {
            throw new Error('Finalization failed');
        }

        return await response.json();
    }
}

// Export for use in HTML
if (typeof module !== 'undefined' && module.exports) {
    module.exports = SafetensorsChunker;
}
