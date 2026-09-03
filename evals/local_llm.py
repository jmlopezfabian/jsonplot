"""Does the briefing actually buy anything? Ask a local model.

Runs the same natural-language requests through an ollama model under three
conditions — no briefing, briefing, briefing plus one repair round — and
validates every contract that comes back with `jp.validate`. The point is not
the absolute score of a 7B model: it is the gap between the columns, and the
error codes that survive, which say what the document still fails to explain.

    ollama serve &
    uv run python evals/local_llm.py --model qwen2.5:7b-instruct
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.error
import urllib.request
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "examples"))

import jsonplot as jp                                       # noqa: E402
from jsonplot import agent                                  # noqa: E402
from sample_data import sales                               # noqa: E402

OLLAMA = "http://localhost:11434/api/chat"

#: Requests a user would actually type, spread over the contract's surface:
#: plain channels, aggregation, time bucketing, filtering, top-N, faceting,
#: distributions, and one that asks for something the framework cannot do.
TASKS: list[tuple[str, str]] = [
    ("bar_simple", "Total revenue by region."),
    ("bar_top_n", "The three regions with the most revenue, biggest bar first."),
    ("line_time", "Monthly revenue over time."),
    ("line_series", "Monthly revenue over time, one line per channel."),
    ("scatter", "Is there a relationship between price and units sold?"),
    ("hist", "How is customer satisfaction distributed?"),
    ("box", "Compare the spread of revenue across regions."),
    ("filtered", "Average satisfaction per channel, only in the North region."),
    ("facet", "Monthly revenue by region, one small chart per region."),
    ("horizontal", "Units sold by region, as horizontal bars, titled 'Units'."),
    ("stacked", "Monthly revenue stacked by channel."),
    ("impossible", "A 3D surface of revenue against price and units."),
]

#: Tasks the framework genuinely cannot serve. A rejected contract is the right
#: outcome here, so they are scored inverted: they measure whether the briefing
#: keeps the model from inventing a chart type rather than whether it complies.
EXPECTED_INVALID = {"impossible"}

SYSTEM = ("You produce visualization contracts. Reply with one JSON object and "
          "nothing else: no prose, no markdown fence, no explanation.")

#: The condition without the briefing: what a naive integration ships — the
#: schema, and the columns, and nothing that explains the vocabulary.
BARE = ("Produce a JSON chart specification for the DataFrame below. Use keys "
        "like viz_type, x_axis, y_axis, agg, title.\n\n")


def ollama(model: str, system: str, user: str, timeout: int = 180) -> str:
    payload = json.dumps({
        "model": model,
        "messages": [{"role": "system", "content": system},
                     {"role": "user", "content": user}],
        "stream": False,
        "format": "json",
        "options": {"temperature": 0},
    }).encode()
    req = urllib.request.Request(OLLAMA, payload,
                                 {"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read())["message"]["content"]


def as_json(text: str):
    """The model's answer as an object, fence and preamble tolerated."""
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    if fence:
        text = fence.group(1).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start == -1 or end <= start:
            return None
        try:
            return json.loads(text[start:end + 1])
        except json.JSONDecodeError:
            return None


def run_task(model: str, df, prompt: str, task: str, repair: bool):
    """One request. Returns (ok, errors, spec, seconds)."""
    started = time.perf_counter()
    raw = ollama(model, SYSTEM, f"{prompt}\nRequest: {task}\n")
    spec = as_json(raw)
    if spec is None:
        return False, [{"code": "NOT_JSON", "message": raw[:120]}], None, \
            time.perf_counter() - started

    errors = [e.to_dict() for e in jp.validate(spec, df)]
    if errors and repair:
        follow = (f"{prompt}\nRequest: {task}\n\n"
                  f"Your contract:\n{json.dumps(spec)}\n\n"
                  f"The validator rejected it:\n{json.dumps(errors, indent=2)}\n"
                  "Send the whole corrected contract.")
        fixed = as_json(ollama(model, SYSTEM, follow))
        if fixed is not None:
            spec, errors = fixed, [e.to_dict() for e in jp.validate(fixed, df)]
    return not errors, errors, spec, time.perf_counter() - started


CONDITIONS = {
    "bare": dict(repair=False),
    "briefing": dict(repair=False),
    "briefing+repair": dict(repair=True),
}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--model", default="qwen2.5:7b-instruct")
    ap.add_argument("--conditions", nargs="*", default=list(CONDITIONS))
    ap.add_argument("--tasks", nargs="*", help="run only these task ids")
    ap.add_argument("--out", help="write the per-task detail here as JSON")
    args = ap.parse_args()

    df = sales()
    tasks = [t for t in TASKS if not args.tasks or t[0] in args.tasks]
    prompts = {
        "bare": BARE + agent.columns(df),
        "briefing": agent.context(df),
        "briefing+repair": agent.context(df),
    }

    detail: list[dict] = []
    print(f"model {args.model} · {len(tasks)} tasks · "
          f"briefing {len(prompts['briefing'])} chars\n")
    for condition in args.conditions:
        codes: Counter[str] = Counter()
        ok_count = 0
        elapsed = 0.0
        print(f"── {condition}")
        for task_id, task in tasks:
            try:
                ok, errors, spec, secs = run_task(
                    args.model, df, prompts[condition], task,
                    **CONDITIONS[condition])
            except (urllib.error.URLError, TimeoutError) as exc:
                print(f"   ollama unreachable at {OLLAMA}: {exc}")
                return 2
            expected = task_id not in EXPECTED_INVALID
            scored = ok is expected
            ok_count += scored
            elapsed += secs
            for err in errors:
                codes[err["code"]] += 1
            mark = "ok " if scored else "FAIL"
            note = "" if not errors else "  " + "; ".join(
                f"{e['code']}@{e.get('path', '')}" for e in errors[:2])
            if not expected:
                note += "   (rejection is the expected outcome)"
            print(f"   {mark} {task_id:<12} {secs:5.1f}s{note}")
            detail.append({"condition": condition, "task": task_id, "ok": ok,
                           "expected_valid": expected, "scored": scored,
                           "errors": errors, "spec": spec})
        print(f"   → {ok_count}/{len(tasks)} valid  ({elapsed:.0f}s total)")
        if codes:
            print("     " + ", ".join(f"{c}×{n}" for c, n in codes.most_common(4)))
        print()

    if args.out:
        Path(args.out).write_text(json.dumps(detail, indent=2, default=str),
                                  encoding="utf-8")
        print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
