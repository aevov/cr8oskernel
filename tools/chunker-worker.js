/**
 * Web Worker for SafeTensors Chunking
 * Runs off main thread to prevent UI freezing
 */

self.onmessage = async function (e) {
    const { type, data } = e.data;

    if (type === 'CHUNK_FILE') {
        await chunkSafeTensors(data.file, data.chunkSizeMB);
    }
};

async function chunkSafeTensors(file, chunkSizeMB) {
    try {
        postProgress('Reading header...', 5);

        // Read header
        const headerBlob = file.slice(0, Math.min(100 * 1024 * 1024, file.size));
        const headerBuffer = await headerBlob.arrayBuffer();
        const uint8Array = new Uint8Array(headerBuffer);

        const headerSize = Number(new DataView(headerBuffer, 0, 8).getBigUint64(0, true));
        const headerBytes = uint8Array.slice(8, 8 + headerSize);
        const headerStr = new TextDecoder().decode(headerBytes);
        const metadata = JSON.parse(headerStr);

        const tensorNames = Object.keys(metadata).filter(k => k !== '__metadata__');

        postProgress(`Found ${tensorNames.length} tensors`, 10, {
            tensors: tensorNames.length,
            totalParams: getTotalParams(metadata, tensorNames)
        });

        // Stream process tensors
        const chunkSizeBytes = chunkSizeMB * 1024 * 1024;
        let chunkIndex = 0;
        let currentChunk = [];
        let currentSize = 0;

        for (let i = 0; i < tensorNames.length; i++) {
            const name = tensorNames[i];
            const tensorMeta = metadata[name];

            // Skip unsupported dtypes
            if (tensorMeta.dtype !== 'F32' && tensorMeta.dtype !== 'BF16') {
                postLog(`Skipping ${name} (unsupported dtype: ${tensorMeta.dtype})`, 'warn');
                continue;
            }

            const absoluteOffset = 8 + headerSize + tensorMeta.data_offsets[0];
            const dataSize = tensorMeta.data_offsets[1] - tensorMeta.data_offsets[0];

            // Read tensor
            const tensorBlob = file.slice(absoluteOffset, absoluteOffset + dataSize);
            const tensorBuffer = await tensorBlob.arrayBuffer();
            const tensorData = new Uint8Array(tensorBuffer);

            // Convert to Float32
            let values;
            if (tensorMeta.dtype === 'F32') {
                values = new Float32Array(tensorData.buffer, tensorData.byteOffset, tensorData.byteLength / 4);
            } else {
                values = bfloat16ToFloat32(tensorData);
            }

            // Downsample if needed (>50M values)
            let valuesArray = Array.from(values);
            if (valuesArray.length > 50_000_000) {
                const stride = Math.ceil(valuesArray.length / 25_000_000);
                valuesArray = valuesArray.filter((_, idx) => idx % stride === 0);
                postLog(`Downsampled ${name} from ${values.length / 1e6}M to ${valuesArray.length / 1e6}M`, 'info');
            }

            const tensorObj = {
                name,
                shape: tensorMeta.shape,
                values: valuesArray
            };

            const estimatedSize = valuesArray.length * 10;

            // Check if we should save current chunk
            if (currentSize > 0 && currentSize + estimatedSize > chunkSizeBytes) {
                // Send chunk for download
                postChunk(chunkIndex, currentChunk);
                chunkIndex++;
                currentChunk = [];
                currentSize = 0;
            }

            currentChunk.push(tensorObj);
            currentSize += estimatedSize;

            // Update progress
            const progress = 10 + ((i + 1) / tensorNames.length) * 85;
            postProgress(`Processing ${i + 1}/${tensorNames.length}`, progress);
        }

        // Send last chunk
        if (currentChunk.length > 0) {
            postChunk(chunkIndex, currentChunk);
            chunkIndex++;
        }

        postProgress('Complete!', 100, { totalChunks: chunkIndex });

    } catch (error) {
        postError(error.message);
    }
}

function getTotalParams(metadata, tensorNames) {
    let total = 0;
    for (const name of tensorNames) {
        const shape = metadata[name].shape;
        total += shape.reduce((a, b) => a * b, 1);
    }
    return total;
}

function bfloat16ToFloat32(uint8Array) {
    const float32 = new Float32Array(uint8Array.length / 2);
    const dataView = new DataView(uint8Array.buffer, uint8Array.byteOffset);

    for (let i = 0; i < float32.length; i++) {
        const bf16 = dataView.getUint16(i * 2, true);
        const f32Bits = bf16 << 16;
        float32[i] = new DataView(new Uint32Array([f32Bits]).buffer).getFloat32(0, true);
    }

    return float32;
}

function postProgress(message, percent, data = {}) {
    self.postMessage({ type: 'PROGRESS', message, percent, data });
}

function postLog(message, level = 'info') {
    self.postMessage({ type: 'LOG', message, level });
}

function postChunk(index, tensors) {
    self.postMessage({ type: 'CHUNK', index, tensors });
}

function postError(message) {
    self.postMessage({ type: 'ERROR', message });
}
