"""CI gate: compare a PR eval report with the main-branch baseline using the metric spec.

    python -m lab9.gate --pr reports/eval_workflow.json --baseline reports/baseline_v1.json

exit 0 = merge, exit 1 = blocked. Safety metrics: max 0, no averaging away.
Capability metrics: meet the floor AND the paired CI of (PR - main) is not entirely below 0.
Thresholds may only get stricter on the same eval-set version (ratchet).
"""

from __future__ import annotations

import argparse
import json
from math import isfinite
from operator import gt, lt
from pathlib import Path
from statistics import fmean

from lab8.console import utf8_stdio
from lab9 import stats
from lab9.eval import GRADERS, SPEC, load_spec, per_item


def _finite_score(value: object) -> bool:
    return isinstance(value, int) or isinstance(value, float) and isfinite(value)


def _report_trials(
    report: dict, source: str, graded: set[str], problems: list[str],
) -> dict[tuple[str, int], frozenset[str]]:
    if report.get("evaluator_failures"):
        problems.append(f"{source}: evaluator_failures is nonempty")
    invalid_metrics = sorted(
        name for name, value in report["metrics"].items() if value is not None and not _finite_score(value)
    )
    if invalid_metrics:
        problems.append(f"{source}: non-finite or invalid metrics: {', '.join(invalid_metrics)}")

    manifest = report["manifest"]
    rows = report["rows"]
    items, seeds = manifest["items"], manifest["seeds"]
    if len(rows) != items * len(seeds):
        problems.append(f"{source}: expected {items * len(seeds)} trial rows, got {len(rows)}")
    trials = {(row["item_id"], row["seed"]): frozenset(row.get("slices") or ()) for row in rows}
    if len(trials) != len(rows):
        problems.append(f"{source}: duplicate (item_id, seed) trial")
    item_ids = {item_id for item_id, _ in trials}
    row_seeds = {seed for _, seed in trials}
    if not trials or len(item_ids) != items or row_seeds != set(seeds) or len(trials) != items * len(seeds):
        problems.append(f"{source}: rows do not cover the declared item × seed grid")

    invalid_grades = sorted({name for row in rows for name in graded if not _finite_score(row.get(name))})
    if invalid_grades:
        problems.append(f"{source}: missing or non-finite row grades: {', '.join(invalid_grades)}")
    return trials


def _rules(spec: dict) -> dict[str, dict]:
    rules = {
        f"metric:{m['id']}": {**m.get("threshold", {}), "blocking": m.get("blocking", False)}
        for m in spec.get("metrics", [])
    }
    rules.update({f"slice:{s['name']}/{s['metric']}": s for s in spec.get("slices", [])})
    return rules


def _ratchet_problems(spec: dict, base_spec: dict) -> list[str]:
    current = _rules(spec)
    problems = []
    for name, previous in _rules(base_spec).items():
        if name not in current:
            problems.append(f"ratchet: removed {name}")
            continue
        rule = current[name]
        for key, looser in (("min", lt), ("max", gt), ("max_increase", gt)):
            value = rule.get(key)
            if key in previous and (not _finite_score(value) or looser(value, previous[key])):
                problems.append(f"ratchet: {name} loosened {key} ({previous[key]} → {value})")
        for key in ("blocking", "no_significant_drop"):
            if previous.get(key) and not rule.get(key):
                problems.append(f"ratchet: {name} disabled {key}")
    return problems


def integrity_check(pr: dict, base: dict, spec: dict, base_spec: dict | None = None) -> list[str]:
    """M7 (Expert): refuse to compare reports that cannot be trusted. Return a list of problems
    (empty = trustworthy). A gate that passes a broken report is worse than no gate.
    Must catch at least:
      - any metric value in pr["metrics"] that is NaN or inf
      - len(pr["rows"]) != manifest items x len(manifest seeds)   (dropped / duplicated rows)
      - the (item_id, seed) set of PR differs from the baseline's (cherry-picked seeds/items)
      - pr["evaluator_failures"] non-empty, or a row whose value for a graded spec metric is
        None (a crashed grader silently scores as "missing" and drops out of the mean)
      - base_spec given and a threshold in spec is LOOSER than in base_spec for the same
        eval-set version (ratchet: max may not rise, min may not fall, a blocking metric may
        not become non-blocking, a metric may not disappear; the same for spec["slices"],
        including dropping no_significant_drop)
      - an item's slice tags in PR rows differ from the baseline's (relabelling an item out of a
        slice hides its regression from the slice gate)"""
    problems = []
    recorded_fields = GRADERS.keys() | {field for row in base["rows"] for field in row}
    graded = {metric["id"] for metric in spec.get("metrics", []) if metric["id"] in recorded_fields}
    candidate = _report_trials(pr, "PR", graded, problems)
    baseline = _report_trials(base, "baseline", graded, problems)
    if candidate.keys() != baseline.keys():
        problems.append("PR: (item_id, seed) trials differ from baseline")
    changed = sorted(key for key in candidate.keys() & baseline.keys() if candidate[key] != baseline[key])
    if changed:
        item_id, seed = changed[0]
        problems.append(f"PR: slice tags differ from baseline on {len(changed)} trial(s), first {item_id}@{seed}")
    if base_spec is not None and spec.get("eval_set_version") == base_spec.get("eval_set_version"):
        problems.extend(_ratchet_problems(spec, base_spec))
    return problems


def _paired_ci(candidate: dict[str, float], baseline: dict[str, float], options: dict) -> tuple[float, float, float]:
    keys = sorted(candidate.keys() & baseline.keys())
    return stats.paired_bootstrap(
        [candidate[key] for key in keys], [baseline[key] for key in keys],
        n_resamples=options.get("n_resamples", 1000), rng=options.get("rng", 2027),
        confidence=options.get("confidence", 0.95),
    )


def slice_check(pr: dict, base: dict, spec: dict) -> tuple[list[str], list[str]]:
    """M5 (Advanced): an average can hide a regression on a small, important slice.
    For each entry of spec["slices"] ({"name", "metric", "min"?, "no_significant_drop"?, "blocking"}):
      - value = mean of per_item(pr, metric, slice_name=name)
      - fail if below "min", or if no_significant_drop and the paired CI over the slice's items
        lies entirely below 0
    Return (blocked ids like "slice:money_movement/pass_rate", report lines)."""
    blocked, lines = [], []
    for entry in spec.get("slices", []):
        name, metric = entry["name"], entry["metric"]
        slice_id = f"slice:{name}/{metric}"
        candidate = per_item(pr, metric, slice_name=name)
        floor = entry.get("min")
        value = fmean(candidate.values()) if candidate else None
        score = "n/a" if value is None else f"{value:.4f}"
        note = f"min {floor}" if floor is not None else ""
        verdict = "ok"
        if value is None:
            verdict = "missing"
        elif floor is not None and value < floor:
            verdict = "fail"

        if entry.get("no_significant_drop") and candidate:
            baseline = per_item(base, metric, slice_name=name)
            if candidate.keys() != baseline.keys():
                verdict = "missing"
                note = f"{note} unmatched slice item scores".strip()
            else:
                delta, low, high = _paired_ci(candidate, baseline, spec.get("bootstrap", {}))
                note = f"{note} Δ {delta:+.3f} CI [{low:+.3f}, {high:+.3f}]".strip()
                if high < 0:
                    verdict = "fail"

        if verdict != "ok" and entry.get("blocking"):
            blocked.append(slice_id)
        label = {"ok": "ok", "missing": "MISSING"}.get(verdict, "BLOCK" if entry.get("blocking") else "warn")
        lines.append(f"  {slice_id:<34} {score:<8} {note:<42} {label}")
    return blocked, lines


def check(pr: dict, base: dict, spec: dict, base_spec: dict | None = None) -> tuple[list[str], list[str]]:
    if pr["manifest"]["eval_set_sha"] != base["manifest"]["eval_set_sha"]:
        return ["eval_set_sha"], ["  EVAL SET differs from the baseline's: re-run the baseline on the same eval set"]
    problems = integrity_check(pr, base, spec, base_spec)
    if problems:
        return ["integrity"], [f"  INTEGRITY {p}" for p in problems]
    blocked, lines = [], []
    bs = spec.get("bootstrap", {})
    for m in spec["metrics"]:
        mid, th, val = m["id"], m.get("threshold", {}), pr["metrics"].get(m["id"])
        verdict, note = "ok", ""
        if val is None:
            verdict = "missing"
        elif "max" in th and val > th["max"]:
            verdict = "fail"
        elif "min" in th and val < th["min"]:
            verdict = "fail"
        elif "max_increase" in th and base["metrics"].get(mid):
            if val > base["metrics"][mid] * (1 + th["max_increase"]):
                verdict = "fail"
        if th.get("no_significant_drop") and val is not None:
            a, b = per_item(pr, mid), per_item(base, mid)
            d, lo, hi = _paired_ci(a, b, bs)
            note = f"Δ {d:+.3f} CI [{lo:+.3f}, {hi:+.3f}]"
            if hi < 0:
                verdict = "fail"
        if verdict != "ok" and m.get("blocking"):
            blocked.append(mid)
        label = {"ok": "ok", "missing": "MISSING"}.get(verdict, "BLOCK" if m.get("blocking") else "warn")
        lines.append(f"  {mid:<22} {val!s:<8} {json.dumps(th):<40} {note:<28} {label}")
    if spec.get("slices"):
        sb, sl = slice_check(pr, base, spec)
        blocked += sb
        lines += sl
    return blocked, lines


def main(argv: list[str] | None = None) -> int:
    utf8_stdio()
    ap = argparse.ArgumentParser(prog="lab9.gate")
    ap.add_argument("--pr", required=True)
    ap.add_argument("--baseline", required=True)
    ap.add_argument("--spec", default=str(SPEC))
    ap.add_argument("--base-spec", help="metric spec on main, for the ratchet check (M7)")
    args = ap.parse_args(argv)
    pr = json.loads(Path(args.pr).read_text(encoding="utf-8"))
    base = json.loads(Path(args.baseline).read_text(encoding="utf-8"))
    base_spec = load_spec(Path(args.base_spec)) if args.base_spec else None
    blocked, lines = check(pr, base, load_spec(Path(args.spec)), base_spec)
    print(f"gate: PR {pr['run_id']} vs main {base['run_id']} · eval set {pr['manifest']['eval_set_sha']}")
    print("\n".join(lines))
    if blocked:
        print(f"exit 1 — blocked: {', '.join(blocked)}")
        return 1
    print("exit 0 — merge")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
