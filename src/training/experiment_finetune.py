from transformers import (
    WhisperProcessor,
    WhisperForConditionalGeneration,
    Seq2SeqTrainingArguments,
    Seq2SeqTrainer,
)
from datasets import load_from_disk, concatenate_datasets
import argparse
import torch
import os
from transformers import EarlyStoppingCallback

torch.multiprocessing.set_sharing_strategy("file_system")
from src.whisper_utils import (  # noqa: E402
    DataCollatorSpeechSeq2SeqWithPadding,
    compute_metrics,
    TimingCallback,
)

if __name__ == "__main__":
    root = ""
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-d",
        "--dialect",
        required=True,
        help="all, egyptian, gulf, iraqi, levantine, maghrebi",
    )
    args = parser.parse_args()
    early_stopping_callback = EarlyStoppingCallback(
        early_stopping_patience=3, early_stopping_threshold=0.001
    )

    if args.dialect == "all":
        dialect_dataset = load_from_disk(os.path.join(root, "egyptian_train/"))
        for d in ["gulf", "iraqi", "levantine", "maghrebi"]:
            train_d = load_from_disk(os.path.join(root, f"{d}_train/"))
            dialect_dataset = concatenate_datasets(
                [train_d, dialect_dataset]
            )
    else:
        dialect_dataset = load_from_disk(os.path.join(root, f"{args.dialect}_train/"))
    os.environ["TRANSFORMERS_CACHE"] = f"model_cache_{args.dialect}_finetune"
    os.environ["HF_HOME"] = f"hf_cache_{args.dialect}_finetune"

    print(f"Training on {args.dialect} dialect, loaded from {dialect_dataset}")
    processor = WhisperProcessor.from_pretrained(
        "openai/whisper-small", language="Arabic", task="transcribe"
    )

    data_collator = DataCollatorSpeechSeq2SeqWithPadding(processor=processor)

    training_args = Seq2SeqTrainingArguments(
        output_dir=f"whisper-small-finetune_{args.dialect}",
        per_device_train_batch_size=8,
        gradient_accumulation_steps=1,
        learning_rate=1e-5,
        warmup_steps=500,
        max_steps=5000,
        gradient_checkpointing=True,
        evaluation_strategy="steps",
        per_device_eval_batch_size=8,
        predict_with_generate=True,
        generation_max_length=225,
        save_steps=250,
        eval_steps=250,
        logging_steps=25,
        report_to=["tensorboard"],
        load_best_model_at_end=True,
        metric_for_best_model="wer",
        greater_is_better=False,
        save_total_limit=2,
    )
    for seed in [168]:
        print(f"Training with seed {seed}")        
        model = WhisperForConditionalGeneration.from_pretrained(
            "otozz/whisper-small-ar_tsize_1.0"
        )
        model.config.forced_decoder_ids = None
        model.config.suppress_tokens = []
        model.generation_config.language = "ar"
        model.config.max_length = 512
        train_test = dialect_dataset.train_test_split(test_size=0.2, seed=seed)
        trainer = Seq2SeqTrainer(
            args=training_args,
            model=model,
            train_dataset=train_test["train"],
            eval_dataset=train_test["test"],
            data_collator=data_collator,
            compute_metrics=compute_metrics,
            tokenizer=processor.feature_extractor,
            callbacks=[early_stopping_callback, TimingCallback(args.dialect, "finetune", seed)],
        )
        training_args.output_dir = f"whisper-small-finetune_{args.dialect}_seed{seed}"
        print(f"Output directory: {training_args.output_dir}")
        for i in range(10):
            try:
                trainer.train()
                break
            except Exception as e:
                print(f"Attempt {i + 1} failed with error: {e}")
                continue
        print("----------------------------")
