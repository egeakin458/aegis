#!/usr/bin/env python3
"""
Benchmark runner for Aegis evaluation.

Usage:
    python evaluation/run_benchmark.py evaluation/benchmarks/benchmark_01_todo.json
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path

BASE_URL = "http://localhost:8000"


def post_json(path: str, body: dict) -> dict:
    data = json.dumps(body).encode()
    req = urllib.request.Request(
        f"{BASE_URL}{path}",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())


def stream_events(run_id: str):
    """Generator that yields PipelineEvent dicts from the SSE stream."""
    url = f"{BASE_URL}/api/pipeline/{run_id}/events"
    req = urllib.request.Request(url, headers={"Accept": "text/event-stream"})
    with urllib.request.urlopen(req, timeout=600) as resp:
        for raw_line in resp:
            line = raw_line.decode("utf-8").rstrip("\n")
            if line.startswith("data:"):
                payload = line[5:].strip()
                if payload:
                    try:
                        yield json.loads(payload)
                    except json.JSONDecodeError:
                        pass


def get_output(run_id: str) -> dict:
    url = f"{BASE_URL}/api/pipeline/{run_id}/output"
    with urllib.request.urlopen(url, timeout=30) as resp:
        return json.loads(resp.read())


PHASE_ICONS = {
    "pipeline_started": "🚀",
    "agent_start": "▶",
    "agent_complete": "✓",
    "clarification_needed": "❓",
    "clarification_received": "✅",
    "config_finalized": "📋",
    "revision_requested": "🔄",
    "revision_started": "🔄",
    "file_generated": "📄",
    "progress_update": "·",
    "pipeline_complete": "🎉",
    "pipeline_failed": "❌",
    "error": "❌",
    "validation_failed": "⚠",
}


def evaluate(benchmark: dict, manifest: dict, events: list[dict]) -> dict:
    """Score the run against benchmark expected_features and unit_tests."""
    files = manifest.get("files", [])
    file_paths = [f["path"] for f in files]
    file_contents = {f["path"]: f.get("content", "") for f in files}
    all_content = "\n".join(file_contents.values()).lower()

    results = {"expected_features": [], "unit_tests": [], "files_generated": len(files)}

    for feature in benchmark.get("expected_features", []):
        keywords = [w.lower() for w in feature.replace(",", " ").split() if len(w) > 3]
        hit = sum(1 for kw in keywords if kw in all_content)
        passed = hit >= max(1, len(keywords) // 2)
        results["expected_features"].append({
            "feature": feature,
            "passed": passed,
            "keyword_hits": f"{hit}/{len(keywords)}",
        })

    for test in benchmark.get("unit_tests", []):
        keywords = [w.lower() for w in test.replace(",", " ").replace(":", " ").split() if len(w) > 3]
        hit = sum(1 for kw in keywords if kw in all_content)
        passed = hit >= max(1, len(keywords) // 2)
        results["unit_tests"].append({
            "test": test,
            "passed": passed,
            "keyword_hits": f"{hit}/{len(keywords)}",
        })

    feature_score = sum(1 for r in results["expected_features"] if r["passed"])
    test_score = sum(1 for r in results["unit_tests"] if r["passed"])
    results["feature_score"] = f"{feature_score}/{len(results['expected_features'])}"
    results["test_score"] = f"{test_score}/{len(results['unit_tests'])}"
    results["overall"] = (feature_score + test_score) / max(
        1, len(results["expected_features"]) + len(results["unit_tests"])
    )

    return results


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("benchmark", help="Path to benchmark JSON file")
    parser.add_argument("--answers", default=None,
                        help="JSON string of clarification answers {question_id: answer}")
    args = parser.parse_args()

    benchmark = json.loads(Path(args.benchmark).read_text())
    print(f"\n{'='*60}")
    print(f"  BENCHMARK: {benchmark['name']}")
    print(f"  Complexity: {benchmark['complexity']}")
    print(f"{'='*60}\n")

    # --- Start the pipeline ---
    if "customer_config_v2" in benchmark:
        config = benchmark["customer_config_v2"]
        config_type = "CustomerConfigV2 (DDC)"
    else:
        config = benchmark["customer_config"]
        # Patch required fields that might be missing from older benchmark files
        config.setdefault("design", {})
        config.setdefault("technical", {})
        config.setdefault("meta", {})
        config_type = "CustomerConfig (legacy)"

    print(f"Submitting {config_type} to pipeline...")
    try:
        resp = post_json("/api/pipeline/start", config)
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        print(f"❌  Backend rejected payload ({e.code}): {body}")
        sys.exit(1)
    except urllib.error.URLError as e:
        print(f"❌  Cannot reach backend at {BASE_URL}: {e}")
        sys.exit(1)

    run_id = resp["run_id"]
    print(f"Run ID: {run_id}\n")

    # --- Stream events ---
    events: list[dict] = []
    start_time = time.time()
    clarification_questions: list[dict] = []

    print("Streaming pipeline events:\n")
    try:
        for event in stream_events(run_id):
            events.append(event)
            et = event.get("event_type", "")
            icon = PHASE_ICONS.get(et, " ")
            agent = event.get("agent", "system")[:3].upper()
            msg = event.get("message", "")
            print(f"  {icon}  [{agent}] {msg}")

            if et == "clarification_needed":
                questions = event.get("data", {}).get("questions", [])
                clarification_questions.extend(questions)
                print("\n  ── Clarification needed ──")
                for q in questions:
                    print(f"     Q [{q['id']}]: {q['question']}")

                if args.answers:
                    answers = json.loads(args.answers)
                else:
                    answers = {}
                    print("\n  Auto-answering clarification questions...")
                    for q in questions:
                        answers[q["id"]] = q.get("suggestions", ["Keep it simple"])[0] if q.get("suggestions") else "Keep it simple"
                        print(f"     A [{q['id']}]: {answers[q['id']]}")

                print()
                post_json(f"/api/pipeline/{run_id}/clarification", answers)

            if et in ("pipeline_complete", "pipeline_failed"):
                break

    except Exception as e:
        print(f"\n❌  Stream error: {e}")
        sys.exit(1)

    elapsed = time.time() - start_time
    print(f"\n{'─'*60}")
    print(f"Pipeline finished in {elapsed:.1f}s\n")

    # Check final status
    last_event_type = events[-1].get("event_type") if events else "unknown"
    if last_event_type == "pipeline_failed":
        print("❌  Pipeline FAILED. Cannot evaluate output.")
        sys.exit(1)

    # --- Fetch output ---
    print("Fetching output manifest...")
    try:
        manifest = get_output(run_id)
    except urllib.error.HTTPError as e:
        print(f"❌  Failed to fetch output: {e}")
        sys.exit(1)

    files = manifest.get("files", [])
    print(f"Generated {len(files)} files:\n")
    for f in files:
        print(f"  📄  {f['path']}  [{f.get('language', '')}]")

    # --- Evaluate ---
    print(f"\n{'─'*60}")
    print("EVALUATION RESULTS\n")
    results = evaluate(benchmark, manifest, events)

    print("Expected Features:")
    for r in results["expected_features"]:
        icon = "✓" if r["passed"] else "✗"
        print(f"  {icon}  {r['feature']}  ({r['keyword_hits']} keywords)")

    print("\nUnit Tests:")
    for r in results["unit_tests"]:
        icon = "✓" if r["passed"] else "✗"
        print(f"  {icon}  {r['test']}  ({r['keyword_hits']} keywords)")

    overall_pct = results["overall"] * 100
    print(f"\n{'─'*60}")
    print(f"  Features:  {results['feature_score']}")
    print(f"  Tests:     {results['test_score']}")
    print(f"  Files:     {results['files_generated']}")
    print(f"  Score:     {overall_pct:.0f}%")
    print(f"  Duration:  {elapsed:.1f}s")
    print(f"{'='*60}\n")

    # Save results
    out_path = Path("evaluation") / f"result_{run_id[:8]}.json"
    out_path.write_text(json.dumps({
        "benchmark": benchmark["task_id"],
        "run_id": run_id,
        "elapsed_s": round(elapsed, 1),
        "files_generated": results["files_generated"],
        "feature_score": results["feature_score"],
        "test_score": results["test_score"],
        "overall_pct": round(overall_pct, 1),
        "details": results,
    }, indent=2))
    print(f"Results saved to {out_path}\n")


if __name__ == "__main__":
    main()
