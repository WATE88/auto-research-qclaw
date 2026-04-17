#!/usr/bin/env python3
import json, os, sys
from pathlib import Path
from collections import Counter, defaultdict

os.environ["PYTHONIOENCODING"] = "utf-8"
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

FINDINGS_DIR = Path(__file__).parent / "findings"
topics = ["bitsandbytes", "QLoRA", "fine-tuning_4bit", "memory_efficient", "peft"]

all_items = []
for f in sorted(FINDINGS_DIR.glob("*.json")):
    if any(t.lower() in f.name.lower() for t in topics):
        data = json.load(open(f, encoding="utf-8"))
        all_items.extend(data.get("findings", []))

seen = set()
unique = []
for item in all_items:
    key = item.get("title", "")
    if key not in seen:
        seen.add(key)
        unique.append(item)

unique.sort(key=lambda x: x.get("stars", 0), reverse=True)

print(f"Total unique: {len(unique)}")
print()
for i, item in enumerate(unique[:25], 1):
    stars = item.get("stars", 0)
    title = item.get("title", "")
    desc = (item.get("description") or "").encode("ascii", "replace").decode()[:65]
    print(f"{i:2}. {title} ({stars:,})")
    print(f"    {desc}")
