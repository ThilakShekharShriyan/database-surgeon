"""SFT then DPO LoRA with Unsloth + TRL on a rented GPU (Vast.ai).

Runs on the GPU box, not on this Mac. Inputs are the files written by
`python -m surgeon.eval train-split` and `train-data` (copied by launch.sh):
  sft.jsonl  {"messages": [...]}           chat records, answer = verified rewrite
  dpo.jsonl  {"prompt", "chosen", "rejected"} rejected = rewrite that changed rows
Output: ./out/sft and ./out/dpo LoRA adapters for vLLM --enable-lora.
"""

import argparse
import json

from datasets import Dataset
from trl import DPOConfig, DPOTrainer, SFTConfig, SFTTrainer
from unsloth import FastLanguageModel


def load(path):
    with open(path) as handle:
        return [json.loads(line) for line in handle if line.strip()]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="unsloth/Qwen2.5-Coder-7B-Instruct")
    parser.add_argument("--sft", default="sft.jsonl")
    parser.add_argument("--dpo", default="dpo.jsonl")
    parser.add_argument("--epochs", type=float, default=1)
    parser.add_argument("--rank", type=int, default=16)
    args = parser.parse_args()

    model, tokenizer = FastLanguageModel.from_pretrained(args.base, max_seq_length=4096, load_in_4bit=True)
    model = FastLanguageModel.get_peft_model(model, r=args.rank, lora_alpha=2 * args.rank, lora_dropout=0,
                                             target_modules=["q_proj", "k_proj", "v_proj", "o_proj",
                                                             "gate_proj", "up_proj", "down_proj"])
    sft = Dataset.from_list([{"messages": r["messages"]} for r in load(args.sft)])
    SFTTrainer(model=model, processing_class=tokenizer, train_dataset=sft,
               args=SFTConfig(output_dir="out/sft", num_train_epochs=args.epochs, per_device_train_batch_size=4,
                              gradient_accumulation_steps=4, learning_rate=1e-4, logging_steps=5,
                              assistant_only_loss=True, max_length=4096, save_strategy="no")).train()
    model.save_pretrained("out/sft")
    tokenizer.save_pretrained("out/sft")

    pairs = load(args.dpo)
    if pairs:
        rows = [{"prompt": tokenizer.apply_chat_template(p["prompt"], tokenize=False, add_generation_prompt=True),
                 "chosen": p["chosen"], "rejected": p["rejected"]} for p in pairs]
        DPOTrainer(model=model, ref_model=None, processing_class=tokenizer, train_dataset=Dataset.from_list(rows),
                   args=DPOConfig(output_dir="out/dpo", num_train_epochs=1, per_device_train_batch_size=2,
                                  gradient_accumulation_steps=4, learning_rate=5e-6, beta=0.1,
                                  logging_steps=5, save_strategy="no")).train()
        model.save_pretrained("out/dpo")
        tokenizer.save_pretrained("out/dpo")


if __name__ == "__main__":
    main()
