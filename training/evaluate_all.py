from transformers import WhisperProcessor, WhisperForConditionalGeneration, Seq2SeqTrainingArguments, Seq2SeqTrainer
from datasets import load_from_disk
import argparse
from whisper_utils import DataCollatorSpeechSeq2SeqWithPadding, compute_metrics
import json

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('-c', '--checkpoint', required=True)
    args = parser.parse_args()
    
    model = WhisperForConditionalGeneration.from_pretrained(args.checkpoint)

    processor = WhisperProcessor.from_pretrained(
        "openai/whisper-small", language="Arabic", task="transcribe"
    )
    
    model.config.forced_decoder_ids = None
    model.config.suppress_tokens = []
    model.generation_config.language = "ar"
    model.config.max_length = 512
    
    data_collator = DataCollatorSpeechSeq2SeqWithPadding(processor=processor)


    training_args = Seq2SeqTrainingArguments(
        output_dir=f"./evaluation",
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
        save_steps=1000,
        eval_steps=1000,
        logging_steps=25,
        report_to=["tensorboard"],
        load_best_model_at_end=True,
        metric_for_best_model="wer",
        greater_is_better=False,
    )
    all_results = {}
    model_name = str(args.checkpoint).split("/")[0]
    for d in ["egyptian", "gulf", "iraqi", "levantine", "maghrebi"]:
        test_set = load_from_disk(f'{d}_test/')
        trainer = Seq2SeqTrainer(
            args=training_args,
            model=model,
            eval_dataset=test_set,
            data_collator=data_collator,
            compute_metrics=compute_metrics,
            tokenizer=processor.feature_extractor,
        )
        results = trainer.evaluate(language="ar")
        all_results[d] = results.copy()
        with open(f"results_{model_name}.json", 'w') as f:
            json.dump(all_results, f)
    test_set = load_from_disk(f'common_voice_arabic_preprocessed/')["test"]
    trainer = Seq2SeqTrainer(
        args=training_args,
        model=model,
        eval_dataset=test_set,
        data_collator=data_collator,
        compute_metrics=compute_metrics,
        tokenizer=processor.feature_extractor,
    )
    results = trainer.evaluate(language="ar")
    all_results["MSA"] = results.copy()
    with open(f"results_{model_name}.json", 'w') as f:
        json.dump(all_results, f)