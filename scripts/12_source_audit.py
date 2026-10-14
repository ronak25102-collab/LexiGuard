"""Post-hoc literal evidence audit; supplementary coverage is not factual accuracy."""

from pathlib import Path
import csv
import argparse
import json
import re
import statistics
import unicodedata

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "evaluation_results/live_validation"


def tokens(text):
    return re.findall(r"\w+", unicodedata.normalize("NFKC", text).casefold())


def grams(text, n=5):
    words = tokens(text)
    return {tuple(words[i:i+n]) for i in range(max(0, len(words)-n+1))}


def coverage(reference, evidence):
    expected = grams(reference)
    return len(expected & grams(evidence)) / len(expected) if expected else None


def main():
    global OUT
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUT)
    OUT = parser.parse_args().output.resolve()
    cases = json.loads((OUT / "questions.json").read_text("utf-8"))
    answers = json.loads((OUT / "answers.json").read_text("utf-8"))
    rows = []
    for case in cases:
        source = (ROOT / "data/parsed" / case["source_file"]).read_text("utf-8")
        for answer in answers:
            if answer["case_id"] != case["id"] or "error" in answer:
                continue
            contexts = answer["contexts"]
            rows.append({"case_id": case["id"], "category": case["category"],
                "source_file": case["source_file"], "variant": answer["variant"],
                "reference_in_source_5gram_recall": coverage(case["reference"], source),
                "reference_in_context_5gram_recall": coverage(case["reference"],
                                                        "\n".join(d["text"] for d in contexts)),
                "reference_in_answer_5gram_recall": coverage(case["reference"], answer["answer"]),
                "source_windows_exact": all(
                    d["source_text"][d["source_window_start"]:d["source_window_end"]] in d["text"]
                    for d in contexts),
                "scope_correct": all(d["contract_id"] == case["contract_id"] for d in contexts),
                "contexts": len(contexts), "context_chars": sum(len(d["text"]) for d in contexts),
                "rewrites": answer["rewrites"], "live_queries": len(answer["cloud_queries"])})
    summary = {"description": "Post-hoc case-macro recall of distinct normalized reference word 5-grams. Literal coverage, not semantic correctness. No judge involved; headers and parsed source formatting can lower recall.",
               "variants": {}}
    for variant in sorted({r["variant"] for r in rows}):
        selected = [r for r in rows if r["variant"] == variant]
        summary["variants"][variant] = {"n": len(selected),
            "reference_context_5gram_recall": statistics.mean(r["reference_in_context_5gram_recall"] for r in selected),
            "reference_answer_5gram_recall": statistics.mean(r["reference_in_answer_5gram_recall"] for r in selected),
            "reference_source_5gram_recall": statistics.mean(r["reference_in_source_5gram_recall"] for r in selected),
            "max_context_chars": max(r["context_chars"] for r in selected),
            "scope_failures": sum(not r["scope_correct"] for r in selected),
            "window_failures": sum(not r["source_windows_exact"] for r in selected),
            "live_queries": sum(r["live_queries"] for r in selected),
            "rewrites": sum(r["rewrites"] for r in selected)}
    (OUT / "source_audit.json").write_text(json.dumps({"summary": summary, "rows": rows}, indent=2), "utf-8")
    with (OUT / "source_audit.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(json.dumps(summary))


if __name__ == "__main__":
    main()
