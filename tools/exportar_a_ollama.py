#!/usr/bin/env python3
"""
Fusiona adaptadores LoRA con el modelo base, convierte a GGUF Q4_K_M y crea el modelo en Ollama.

El GGUF se guarda en ./ollama/ (visible en el contenedor Ollama como /root/.ollama/).
Debe ejecutarse en el contenedor finetune:
  docker compose run --rm finetune python tools/exportar_a_ollama.py \
    --lora outputs/mipizarra-v1/lora_adapters
"""
import argparse
import json
import subprocess
import sys
import requests
from pathlib import Path


MODELFILE_TEMPLATE = """\
FROM {gguf_path}

SYSTEM \"\"\"Eres MiPizarra, un asistente experto en entrenamiento de baloncesto. \
Diseñas sesiones de entrenamiento estructuradas y prácticas. \
Usas terminología técnica española (codo TL, cabecera, baseline, poste alto/bajo). \
Siempre propones ejercicios con posiciones concretas.\"\"\"

# Muestreo
PARAMETER temperature 0.4
PARAMETER top_p 0.9
PARAMETER min_p 0.05
PARAMETER top_k 40
PARAMETER repeat_penalty 1.15

# Memoria / hardware (GTX 1060 6GB)
PARAMETER num_ctx 4096
PARAMETER num_gpu 99
PARAMETER num_thread 4
PARAMETER num_batch 256

PARAMETER stop "<|im_end|>"
PARAMETER stop "<|endoftext|>"
"""

LLAMA_CPP      = Path("/opt/llama.cpp")
CONVERT_SCRIPT = LLAMA_CPP / "convert_hf_to_gguf.py"
QUANTIZE_BIN   = LLAMA_CPP / "build/bin/llama-quantize"


def main():
    parser = argparse.ArgumentParser(description="Exporta LoRA a Ollama via GGUF")
    parser.add_argument("--lora",   required=True,
                        help="Carpeta con adaptadores LoRA")
    parser.add_argument("--base",   default="Qwen/Qwen3-4B",
                        help="Modelo base HuggingFace")
    parser.add_argument("--nombre", default="mipizarra",
                        help="Nombre del modelo en Ollama")
    parser.add_argument("--quant",  default="Q4_K_M",
                        help="Tipo de cuantización: Q4_K_M, Q5_K_M, Q8_0")
    parser.add_argument("--ollama", default="http://ollama:11434",
                        help="URL del servicio Ollama")
    args = parser.parse_args()

    lora_path  = Path(args.lora)
    # ./ollama/ en el host → /root/.ollama/ dentro del contenedor Ollama
    ollama_dir = Path("/workspace/ollama")
    merged_dir = ollama_dir / "merged"
    gguf_f16   = ollama_dir / f"{args.nombre}.f16.gguf"
    gguf_final = ollama_dir / f"{args.nombre}.{args.quant.lower()}.gguf"
    ollama_dir.mkdir(parents=True, exist_ok=True)

    if not lora_path.exists():
        print(f"✗ No se encontraron adaptadores en: {lora_path}")
        sys.exit(1)
    if not QUANTIZE_BIN.exists():
        print("✗ llama-quantize no encontrado. Rebuild el contenedor finetune.")
        sys.exit(1)

    # ── Paso 1: Fusionar LoRA con el modelo base (CPU) ───────────────────────
    print("Paso 1: Fusionando LoRA con el modelo base (en CPU)...")
    print("  Esto puede tardar ~5 min y necesita ~6 GB de RAM\n")

    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer
    from peft import PeftModel

    tokenizer = AutoTokenizer.from_pretrained(args.base)
    model = AutoModelForCausalLM.from_pretrained(
        args.base,
    	torch_dtype=torch.float16,
    	device_map="cpu",
    	low_cpu_mem_usage=True,   # ← añade esta línea
    )

    model = PeftModel.from_pretrained(model, str(lora_path))
    model = model.merge_and_unload()
    model.save_pretrained(str(merged_dir), safe_serialization=True)
    tokenizer.save_pretrained(str(merged_dir))
    print(f"  ✓ Modelo fusionado en {merged_dir}\n")

    # ── Paso 2: Convertir a GGUF f16 ─────────────────────────────────────────
    print("Paso 2: Convirtiendo a GGUF (f16)...")
    result = subprocess.run([
        sys.executable, str(CONVERT_SCRIPT),
        str(merged_dir),
        "--outtype", "f16",
        "--outfile", str(gguf_f16),
    ])
    if result.returncode != 0:
        print("✗ Error en la conversión a GGUF")
        sys.exit(1)
    size_gb = gguf_f16.stat().st_size / 1024**3
    print(f"  ✓ GGUF f16: {gguf_f16.name} ({size_gb:.2f} GB)\n")

    # ── Paso 3: Cuantizar a Q4_K_M ───────────────────────────────────────────
    print(f"Paso 3: Cuantizando a {args.quant}...")
    result = subprocess.run([
        str(QUANTIZE_BIN), str(gguf_f16), str(gguf_final), args.quant
    ])
    if result.returncode != 0:
        print("✗ Error en la cuantización")
        sys.exit(1)
    gguf_f16.unlink(missing_ok=True)
    size_gb = gguf_final.stat().st_size / 1024**3
    print(f"  ✓ GGUF {args.quant}: {gguf_final.name} ({size_gb:.2f} GB)\n")

    # ── Paso 4: Crear modelo en Ollama ────────────────────────────────────────
    # El GGUF está en ./ollama/ → dentro del contenedor Ollama es /root/.ollama/
    gguf_en_ollama = f"/root/.ollama/{gguf_final.name}"
    modelfile_content = MODELFILE_TEMPLATE.format(gguf_path=gguf_en_ollama)

    print(f"Paso 4: Creando modelo '{args.nombre}' en Ollama...")
    try:
        r = requests.post(
            f"{args.ollama}/api/create",
            json={"name": args.nombre, "modelfile": modelfile_content},
            stream=True,
            timeout=600,
        )
        r.raise_for_status()
        for line in r.iter_lines():
            if line:
                data = json.loads(line)
                status = data.get("status", "")
                if status:
                    print(f"  {status}", end="\r")
        print(f"\n  ✓ Modelo '{args.nombre}' disponible en Ollama\n")
        ollama_ok = True
    except Exception as e:
        ollama_ok = False
        print(f"  ⚠ No se pudo conectar a Ollama: {e}")
        print(f"\nEjecuta esto manualmente desde el host:")
        print(f"  docker exec mipizarra-ollama ollama create {args.nombre} << 'EOF'")
        print(modelfile_content)
        print("EOF\n")

    print("=" * 50)
    print(f"✅ Exportación completa")
    print(f"   Modelo: {args.nombre}")
    print(f"   GGUF:   {gguf_final}")
    if ollama_ok:
        print(f"\nActiva el modelo en la app (docker-compose.yml):")
        print(f"  OLLAMA_MODEL={args.nombre}")
        print(f"  docker compose up -d api")
        print(f"\nPara probarlo:")
        print(f"  docker exec -it mipizarra-ollama ollama run {args.nombre}")


if __name__ == "__main__":
    main()
