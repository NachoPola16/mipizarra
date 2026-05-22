#!/usr/bin/env python3
"""
Fine-tuning de Qwen2.5-3B-Instruct con QLoRA para GTX 1060 (6GB VRAM).
Usa la pila HuggingFace estándar: transformers + peft + bitsandbytes + trl.

Uso:
  python tools/finetune_qwen.py
  python tools/finetune_qwen.py --dataset data/dataset/train.jsonl --steps 300 --output outputs/hoops-qwen-v2
"""
import argparse
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description="Fine-tuning QLoRA para MiPizarra")
    parser.add_argument("--dataset", default="data/dataset/train.jsonl", help="Dataset JSONL")
    parser.add_argument("--model",   default="Qwen/Qwen2.5-3B-Instruct",  help="Modelo base HuggingFace")
    parser.add_argument("--output",  default="outputs/mipizarra-v1",      help="Carpeta de salida")
    parser.add_argument("--steps",   type=int, default=100,
                        help="Pasos de entrenamiento. 100 (default) está calibrado para datasets de "
                             "~100-200 ejemplos. Sube a 200 solo si el dataset supera 300 ejemplos; "
                             "más allá de eso, mejor aumentar el dataset que los steps.")
    parser.add_argument("--rank",    type=int, default=8,                  help="Rango LoRA (8-32); 8 evita overfitting en datasets pequeños")
    parser.add_argument("--seq-len", type=int, default=2048,               help="Longitud máxima de secuencia")
    parser.add_argument("--solo-atencion", action="store_true",
                        help="Solo LoRA en atención (ahorra VRAM, menos capacidad)")
    args = parser.parse_args()

    print("Cargando dependencias...")
    try:
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
        from peft import LoraConfig, get_peft_model, TaskType, prepare_model_for_kbit_training
        try:
            from trl import SFTTrainer, SFTConfig
        except ImportError:
            from trl import SFTTrainer
            from transformers import TrainingArguments as SFTConfig
        from datasets import Dataset
    except ImportError as e:
        print(f"\n✗ Dependencia no encontrada: {e}")
        print("\nInstala las dependencias con:")
        print("  pip install bitsandbytes peft trl datasets transformers accelerate")
        return

    print(f"PyTorch: {torch.__version__}")
    print(f"CUDA disponible: {torch.cuda.is_available()}")
    if torch.cuda.is_available():
        print(f"GPU: {torch.cuda.get_device_name(0)}")
        print(f"VRAM: {torch.cuda.get_device_properties(0).total_memory / 1024**3:.1f} GB")

    # ── Cuantización 4-bit (QLoRA) ────────────────────────────────────────────
    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.float16,
        bnb_4bit_use_double_quant=True,
    )

    print(f"\nCargando modelo base: {args.model}")
    print("(Primera ejecución: descarga ~2GB, puede tardar varios minutos)\n")

    model = AutoModelForCausalLM.from_pretrained(
        args.model,
        quantization_config=bnb_config,
        device_map="auto",
    )
    tokenizer = AutoTokenizer.from_pretrained(args.model)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    # Preparar para entrenamiento 4-bit con gradient checkpointing
    model = prepare_model_for_kbit_training(model, use_gradient_checkpointing=True)

    # ── Aplicar LoRA ──────────────────────────────────────────────────────────
    print("Aplicando adaptadores LoRA...")
    target_modules = (
        ["q_proj", "k_proj", "v_proj", "o_proj"]
        if args.solo_atencion
        else ["q_proj", "k_proj", "v_proj", "o_proj",
              "gate_proj", "up_proj", "down_proj"]
    )
    lora_config = LoraConfig(
        r=args.rank,
        target_modules=target_modules,
        lora_alpha=args.rank * 2,   # alpha = 2r es el ratio recomendado actual
        lora_dropout=0.05,           # ligera regularización para datasets pequeños
        bias="none",
        task_type=TaskType.CAUSAL_LM,
    )
    model = get_peft_model(model, lora_config)
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
        texto = tokenizer.apply_chat_template(
            convs, tokenize=False, add_generation_prompt=False,
        )
        return {"text": texto}

    dataset = Dataset.from_list(raw)
    dataset = dataset.map(formatear, remove_columns=dataset.column_names)

    longitudes = [len(tokenizer.encode(e["text"])) for e in dataset]
    print(f"Tokens — min: {min(longitudes)}, max: {max(longitudes)}, media: {sum(longitudes)//len(longitudes)}")

    n_antes = len(dataset)
    dataset = dataset.filter(
        lambda e: len(tokenizer.encode(e["text"])) <= args.seq_len
    )
    descartados = n_antes - len(dataset)
    if descartados:
        print(f"⚠ {descartados} ejemplos descartados por superar seq_len={args.seq_len} (no truncados — preferible descartar)")
        print(f"  Quedan {len(dataset)} ejemplos para entrenar")

    # ── Configuración del entrenamiento ───────────────────────────────────────
    output_path = Path(args.output)
    output_path.mkdir(parents=True, exist_ok=True)

    sft_kwargs = dict(model=model, train_dataset=dataset)

    train_args = SFTConfig(
        per_device_train_batch_size=1,
        gradient_accumulation_steps=8,   # batch efectivo 8 (mejor convergencia)
        num_train_epochs=3,
        max_steps=args.steps,
        warmup_steps=10,
        learning_rate=2e-4,
        fp16=True,                       # GTX 1060 (Pascal sm_61) sí soporta fp16, no bf16
        bf16=False,
        logging_steps=10,
        save_steps=50,
        save_total_limit=2,
        output_dir=str(output_path),
        optim="paged_adamw_8bit",        # ahorra ~500 MB VRAM vs adamw_torch
        weight_decay=0.01,
        lr_scheduler_type="cosine",
        seed=42,
        report_to="none",
        gradient_checkpointing=True,
    )

    # SFTConfig (trl>=0.8) acepta dataset_text_field; TrainingArguments no
    if hasattr(train_args, "dataset_text_field"):
        train_args.dataset_text_field = "text"
        train_args.max_seq_length = args.seq_len
        extra_kwargs = {}
    else:
        extra_kwargs = {"dataset_text_field": "text", "max_seq_length": args.seq_len}

    # trl>=0.9 renombró tokenizer → processing_class
    try:
        trainer = SFTTrainer(
            args=train_args, processing_class=tokenizer, **sft_kwargs, **extra_kwargs
        )
    except TypeError:
        trainer = SFTTrainer(
            args=train_args, tokenizer=tokenizer, **sft_kwargs, **extra_kwargs
        )

    # ── Entrenar ──────────────────────────────────────────────────────────────
    print(f"\n{'='*50}")
    print(f"Iniciando fine-tuning:")
    print(f"  Pasos:      {args.steps}")
    print(f"  Batch eff:  8 (1 × grad_acc 8)")
    print(f"  LoRA rank:  {args.rank} (alpha {args.rank * 2})")
    print(f"  Target:     {'solo atención' if args.solo_atencion else 'atención + MLP'}")
    print(f"  Salida:     {output_path}")
    print(f"  Estimado:   ~{args.steps * 8 // 60} min en GTX 1060")
    print(f"{'='*50}\n")

    trainer_stats = trainer.train()

    # ── Guardar adaptadores LoRA ───────────────────────────────────────────────
    lora_path = output_path / "lora_adapters"
    model.save_pretrained(str(lora_path))
    tokenizer.save_pretrained(str(lora_path))

    print(f"\n{'='*50}")
    print(f"✅ Fine-tuning completado!")
    print(f"   Pérdida final:    {trainer_stats.training_loss:.4f}")
    print(f"   Adaptadores LoRA: {lora_path}")
    print(f"\nPróximo paso — exportar a Ollama:")
    print(f"  python tools/exportar_a_ollama.py --lora {lora_path} --output {output_path}/gguf")


if __name__ == "__main__":
    main()
