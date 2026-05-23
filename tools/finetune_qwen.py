#!/usr/bin/env python3
"""
Fine-tuning Qwen3-4B con Unsloth (local, recomendado) o TRL estándar (servidor Docker).

Modo Unsloth  — local, RTX 5060 Ti 16 GB, sin cuantización (--no-quantize):
  pip install unsloth transformers peft trl datasets accelerate
  python tools/finetune_qwen.py --no-quantize

Modo TRL      — servidor, GTX 1060 6 GB, QLoRA 4-bit (dentro del contenedor finetune):
  docker compose run --rm finetune python tools/finetune_qwen.py

Más pasos / más rank (con ≥12 GB VRAM):
  python tools/finetune_qwen.py --no-quantize --rank 16 --steps 150
"""
import argparse
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description="Fine-tuning LoRA/QLoRA para MiPizarra")
    parser.add_argument("--dataset",      default="data/dataset/train.jsonl", help="Dataset JSONL")
    parser.add_argument("--model",        default="Qwen/Qwen3-4B",            help="Modelo base HuggingFace")
    parser.add_argument("--output",       default="outputs/mipizarra-v1",      help="Carpeta de salida")
    parser.add_argument("--steps",        type=int, default=100,
                        help="Pasos de entrenamiento (100 para ~100-200 ejemplos; ver tabla en ENTRENAMIENTO_MODELO.md)")
    parser.add_argument("--rank",         type=int, default=8,
                        help="Rango LoRA (8 con dataset pequeño; 16 con ≥500 ejemplos y ≥12 GB VRAM)")
    parser.add_argument("--seq-len",      type=int, default=2048, help="Longitud máxima de secuencia")
    parser.add_argument("--solo-atencion", action="store_true",
                        help="Solo LoRA en q/k/v/o (ahorra VRAM, menos capacidad)")
    parser.add_argument("--no-quantize", action="store_true",
                        help="LoRA puro en fp16/bf16 sin cuantización 4-bit. "
                             "Recomendado con ≥12 GB VRAM. No requiere bitsandbytes.")
    args = parser.parse_args()

    import torch
    if torch.cuda.is_available():
        gpu_name = torch.cuda.get_device_name(0)
        vram_gb  = torch.cuda.get_device_properties(0).total_memory / 1024**3
        use_bf16 = torch.cuda.is_bf16_supported()
        print(f"PyTorch: {torch.__version__}")
        print(f"GPU:  {gpu_name} ({vram_gb:.1f} GB VRAM) | bf16: {'sí' if use_bf16 else 'no (fp16)'}")
        if vram_gb >= 12 and not args.no_quantize:
            print(f"  ℹ  {vram_gb:.0f} GB VRAM detectados — considera --no-quantize.\n")
    else:
        gpu_name, vram_gb, use_bf16 = "CPU", 0.0, False
        print("⚠  CUDA no disponible — el entrenamiento en CPU es extremadamente lento.")

    target_modules = (
        ["q_proj", "k_proj", "v_proj", "o_proj"]
        if args.solo_atencion
        else ["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"]
    )

    # ── Intentar Unsloth (prioritario para GPU local) ─────────────────────────
    HAS_UNSLOTH = False
    try:
        from unsloth import FastLanguageModel
        HAS_UNSLOTH = True
        print("✓ Unsloth disponible — modo optimizado (2× más rápido, −70% VRAM)\n")
    except ImportError:
        print("ℹ Unsloth no instalado — usando TRL estándar")
        print("  Para instalarlo: pip install unsloth\n")

    # ── Importar TRL y datasets (usados en ambas ramas) ──────────────────────
    try:
        from trl import SFTTrainer, SFTConfig
    except ImportError:
        from trl import SFTTrainer
        from transformers import TrainingArguments as SFTConfig
    from datasets import Dataset

    # ── Cargar modelo ─────────────────────────────────────────────────────────
    modo_str = ("Unsloth + " if HAS_UNSLOTH else "") + \
               ("LoRA bf16" if (args.no_quantize and use_bf16) else
                "LoRA fp16" if args.no_quantize else "QLoRA 4-bit")
    print(f"Cargando modelo: {args.model}")
    print(f"Modo: {modo_str}")
    print("(Primera ejecución: descarga ~3 GB, puede tardar varios minutos)\n")

    if HAS_UNSLOTH:
        # Unsloth tiene sus propios pesos optimizados en unsloth/Qwen3-4B;
        # si el usuario pasa otro --model, se respeta tal cual.
        unsloth_name = "unsloth/Qwen3-4B" if args.model == "Qwen/Qwen3-4B" else args.model
        model, tokenizer = FastLanguageModel.from_pretrained(
            model_name=unsloth_name,
            max_seq_length=args.seq_len,
            dtype=None,                        # auto-detect: bf16 en Ampere+/Blackwell, fp16 en Pascal
            load_in_4bit=not args.no_quantize, # True = QLoRA, False = LoRA puro
        )
        model = FastLanguageModel.get_peft_model(
            model,
            r=args.rank,
            target_modules=target_modules,
            lora_alpha=args.rank * 2,
            lora_dropout=0.05,
            bias="none",
            use_gradient_checkpointing="unsloth",  # versión optimizada de Unsloth
            random_state=42,
        )
        optim = "adamw_8bit"
        batch  = 2   # Unsloth gestiona mejor la memoria, puede subir el batch
        grad_acc = 4  # batch efectivo = 8
    else:
        # ── Rama estándar TRL + PEFT ──────────────────────────────────────────
        try:
            from transformers import AutoModelForCausalLM, AutoTokenizer
            from peft import LoraConfig, get_peft_model, TaskType, prepare_model_for_kbit_training
        except ImportError as e:
            print(f"\n✗ Dependencia no encontrada: {e}")
            print("  pip install transformers peft trl datasets accelerate")
            return

        if args.no_quantize:
            dtype = torch.bfloat16 if use_bf16 else torch.float16
            model = AutoModelForCausalLM.from_pretrained(
                args.model, torch_dtype=dtype, device_map="auto",
            )
            model.enable_input_require_grads()
            optim = "adamw_torch_fused"
        else:
            try:
                from transformers import BitsAndBytesConfig
            except ImportError:
                print("⚠  bitsandbytes no disponible — activando --no-quantize.")
                args.no_quantize = True
                dtype = torch.bfloat16 if use_bf16 else torch.float16
                model = AutoModelForCausalLM.from_pretrained(
                    args.model, torch_dtype=dtype, device_map="auto",
                )
                model.enable_input_require_grads()
                optim = "adamw_torch_fused"
            else:
                bnb_config = BitsAndBytesConfig(
                    load_in_4bit=True,
                    bnb_4bit_quant_type="nf4",
                    bnb_4bit_compute_dtype=torch.bfloat16 if use_bf16 else torch.float16,
                    bnb_4bit_use_double_quant=True,
                )
                model = AutoModelForCausalLM.from_pretrained(
                    args.model, quantization_config=bnb_config, device_map="auto",
                )
                model = prepare_model_for_kbit_training(model, use_gradient_checkpointing=True)
                optim = "paged_adamw_8bit"

        tokenizer = AutoTokenizer.from_pretrained(args.model)
        if tokenizer.pad_token is None:
            tokenizer.pad_token = tokenizer.eos_token

        lora_config = LoraConfig(
            r=args.rank,
            target_modules=target_modules,
            lora_alpha=args.rank * 2,
            lora_dropout=0.05,
            bias="none",
            task_type=TaskType.CAUSAL_LM,
        )
        model = get_peft_model(model, lora_config)
        batch    = 1
        grad_acc = 8  # batch efectivo = 8

    model.print_trainable_parameters()

    # ── Cargar y preparar dataset ─────────────────────────────────────────────
    print(f"\nCargando dataset: {args.dataset}")
    raw = []
    with open(args.dataset, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                raw.append(json.loads(line))
    print(f"Ejemplos cargados: {len(raw)}")

    def formatear(ejemplo):
        convs = ejemplo["conversations"]
        # Qwen3: enable_thinking=False evita tokens <think> en fine-tuning
        try:
            texto = tokenizer.apply_chat_template(
                convs, tokenize=False, add_generation_prompt=False,
                enable_thinking=False,
            )
        except TypeError:
            texto = tokenizer.apply_chat_template(
                convs, tokenize=False, add_generation_prompt=False,
            )
        return {"text": texto}

    dataset = Dataset.from_list(raw)
    dataset = dataset.map(formatear, remove_columns=dataset.column_names)

    longitudes = [len(tokenizer.encode(e["text"])) for e in dataset]
    print(f"Tokens — min: {min(longitudes)}, max: {max(longitudes)}, media: {sum(longitudes)//len(longitudes)}")

    n_antes = len(dataset)
    dataset = dataset.filter(lambda e: len(tokenizer.encode(e["text"])) <= args.seq_len)
    descartados = n_antes - len(dataset)
    if descartados:
        print(f"⚠  {descartados} ejemplos descartados por superar seq_len={args.seq_len}")
        print(f"   Quedan {len(dataset)} ejemplos para entrenar")

    # ── Configuración del entrenamiento ───────────────────────────────────────
    output_path = Path(args.output)
    output_path.mkdir(parents=True, exist_ok=True)

    train_args = SFTConfig(
        per_device_train_batch_size=batch,
        gradient_accumulation_steps=grad_acc,
        num_train_epochs=3,
        max_steps=args.steps,
        warmup_steps=10,
        learning_rate=2e-4,
        fp16=not use_bf16,
        bf16=use_bf16,
        logging_steps=10,
        save_steps=50,
        save_total_limit=2,
        output_dir=str(output_path),
        optim=optim,
        weight_decay=0.01,
        lr_scheduler_type="cosine",
        seed=42,
        report_to="none",
        gradient_checkpointing=not HAS_UNSLOTH,  # Unsloth lo gestiona internamente
    )

    if hasattr(train_args, "dataset_text_field"):
        train_args.dataset_text_field = "text"
        train_args.max_seq_length = args.seq_len
        extra_kwargs = {}
    else:
        extra_kwargs = {"dataset_text_field": "text", "max_seq_length": args.seq_len}

    sft_kwargs = dict(model=model, train_dataset=dataset)

    try:
        trainer = SFTTrainer(
            args=train_args, processing_class=tokenizer, **sft_kwargs, **extra_kwargs
        )
    except TypeError:
        trainer = SFTTrainer(
            args=train_args, tokenizer=tokenizer, **sft_kwargs, **extra_kwargs
        )

    # ── Entrenar ──────────────────────────────────────────────────────────────
    est_factor = 2 if HAS_UNSLOTH else (3 if args.no_quantize else 8)
    est_min = args.steps * est_factor // 60
    print(f"\n{'='*55}")
    print(f"Iniciando fine-tuning:")
    print(f"  Modo:       {modo_str}")
    print(f"  Pasos:      {args.steps}")
    print(f"  Batch eff:  {batch * grad_acc} ({batch} × grad_acc {grad_acc})")
    print(f"  LoRA rank:  {args.rank} (alpha {args.rank * 2})")
    print(f"  Optimizer:  {optim}")
    print(f"  GPU:        {gpu_name}")
    print(f"  Estimado:   ~{max(1, est_min)} min")
    print(f"  Salida:     {output_path}")
    print(f"{'='*55}\n")

    trainer_stats = trainer.train()

    # ── Guardar adaptadores LoRA ──────────────────────────────────────────────
    lora_path = output_path / "lora_adapters"
    model.save_pretrained(str(lora_path))
    tokenizer.save_pretrained(str(lora_path))

    print(f"\n{'='*55}")
    print(f"✅ Fine-tuning completado!")
    print(f"   Pérdida final:    {trainer_stats.training_loss:.4f}")
    print(f"   Adaptadores LoRA: {lora_path}")
    if args.no_quantize:
        print(f"\nSi entrenaste en local, copia lora_adapters/ al servidor:")
        print(f"  scp -r {lora_path} usuario@192.168.1.72:~/docker/mipizarra/{lora_path}")
    print(f"\nPróximo paso — exportar a Ollama (dentro del contenedor finetune en el servidor):")
    print(f"  python tools/exportar_a_ollama.py --lora {lora_path} --output {output_path}/gguf")


if __name__ == "__main__":
    main()
