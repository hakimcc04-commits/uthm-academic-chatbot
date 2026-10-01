import os
import sys
import pandas as pd
import json
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

BASE_DIR = Path(__file__).resolve().parent
dataset_path = BASE_DIR / "academic_chatbot_dataset.csv"
output_jsonl = BASE_DIR / "uthm_instruction_dataset.jsonl"
output_csv = BASE_DIR / "uthm_instruction_dataset.csv"

def format_dataset():
    if not dataset_path.exists():
        print(f"Error: {dataset_path} not found.")
        return

    df = pd.read_csv(dataset_path)
    records = []

    system_prompt = "Anda adalah Pembantu AI Akademik Rasmi UTHM. Jawab soalan pengguna dengan tepat berdasarkan fakta UTHM."

    for idx, row in df.iterrows():
        question = str(row.get("question", "")).strip()
        response_bm = str(row.get("response_bm", "")).strip()
        response_en = str(row.get("response_en", "")).strip()
        intent = str(row.get("intent", "")).strip()

        if question and response_bm:
            records.append({
                "instruction": system_prompt,
                "input": question,
                "output": response_bm,
                "intent": intent,
                "language": "bm"
            })
        if question and response_en:
            records.append({
                "instruction": system_prompt,
                "input": question,
                "output": response_en,
                "intent": intent,
                "language": "en"
            })

    # Save to JSONL
    with open(output_jsonl, "w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    # Save to CSV
    df_out = pd.DataFrame(records)
    df_out.to_csv(output_csv, index=False, encoding="utf-8")

    print(f"✅ Formatted dataset successfully! Total instruction pairs created: {len(records)}")

if __name__ == "__main__":
    format_dataset()
