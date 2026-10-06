"""Append one run's billed cost to work/ocr/sample-ledger.tsv (from the run's calls.jsonl)."""
import json, sys, time, os
run_dir, note = sys.argv[1], (sys.argv[2] if len(sys.argv) > 2 else "")
rows = [json.loads(l) for l in open(os.path.join(run_dir, "calls.jsonl"))]
s = lambda k: sum(r.get(k) or 0 for r in rows)
parts = os.path.normpath(run_dir).split(os.sep)
line = "\t".join(map(str, [time.strftime("%Y-%m-%dT%H:%M"), parts[-3][:8], parts[-1], len(rows),
    s("input_tokens"), s("output_tokens"), s("thoughts_tokens"), round(s("cost_usd"), 4), note]))
path = os.path.join(os.path.dirname(__file__), "..", "sample-ledger.tsv")
new = not os.path.exists(path)
with open(path, "a") as f:
    if new: f.write("when\tmap\trun\tcalls\tin_tok\tout_tok\tthink_tok\tcost_usd\tnote\n")
    f.write(line + "\n")
print(line)
