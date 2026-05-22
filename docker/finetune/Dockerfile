FROM nvidia/cuda:11.8.0-devel-ubuntu22.04

RUN apt-get update && apt-get install -y \
    python3-pip python3-dev git cmake build-essential && \
    rm -rf /var/lib/apt/lists/* && \
    ln -s /usr/bin/python3 /usr/bin/python

# PyTorch 2.5.1 con CUDA 11.8 (compatible con GTX 1060 sm_61)
RUN pip install --no-cache-dir \
    "torch==2.5.1+cu118" \
    --index-url https://download.pytorch.org/whl/cu118

# Pila HuggingFace estándar
# bitsandbytes pineado a 0.42.0: última versión estable en GPUs Pascal (sm_61, GTX 10xx).
# Versiones >= 0.43 fallan en compute capability 6.1.
RUN pip install --no-cache-dir \
    "bitsandbytes==0.42.0" \
    peft trl datasets transformers accelerate pypdf beautifulsoup4 requests

# llama.cpp: conversión HF→GGUF y cuantización Q4_K_M (CPU only)
RUN pip install --no-cache-dir gguf sentencepiece
RUN git clone --depth=1 https://github.com/ggerganov/llama.cpp /opt/llama.cpp && \
    pip install --no-cache-dir -r /opt/llama.cpp/requirements.txt && \
    cd /opt/llama.cpp && \
    cmake -B build -DGGML_CUDA=OFF -DGGML_METAL=OFF && \
    cmake --build build --target llama-quantize -j$(nproc)

ENV HF_HOME=/workspace/.cache/huggingface
WORKDIR /workspace
CMD ["bash"]
