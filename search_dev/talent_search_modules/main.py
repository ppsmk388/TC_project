"""
Main entry point for Talent Search System
Provides the primary talent_search function and CLI interface
"""

import json
import argparse
from typing import Dict, Any, Optional
import config
import utils
import schemas
import graph

# Import specific items from modules
from config import SAVE_DIR, VERBOSE
from utils import now_ts, setup_tee_logging, ensure_directory
from schemas import ResearchState, QuerySpec
from graph import build_graph, _ensure_state

# ============================ MAIN TALENT SEARCH FUNCTION ============================

def talent_search(question: str, ts: Optional[str] = None) -> Dict[str, Any]:
    """Main talent search function"""
    ts = ts or now_ts()
    ensure_directory(SAVE_DIR)
    log_path = setup_tee_logging(SAVE_DIR, ts)

    print(f"[start] {question}")
    print(f"[cfg] Save directory: {SAVE_DIR}")
    print(f"[cfg] Verbose: {VERBOSE}")

    app = build_graph()
    init = ResearchState(query=question)
    final = app.invoke(init)
    st = _ensure_state(final)
    spec = QuerySpec.model_validate(st.query_spec)

    # Prepare output paths
    md_path = f"{SAVE_DIR}/{ts}_talent_report.md"
    json_path = f"{SAVE_DIR}/{ts}_candidates.json"
    plan_path = f"{SAVE_DIR}/{ts}_plan.json"
    qs_path = f"{SAVE_DIR}/{ts}_query_spec.json"
    sources_js = f"{SAVE_DIR}/{ts}_used_sources.json"
    serp_path = f"{SAVE_DIR}/{ts}_serp_dump.json"

    # Save all artifacts
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(st.report or "")

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(st.candidates, f, ensure_ascii=False, indent=2)

    with open(plan_path, "w", encoding="utf-8") as f:
        json.dump(st.plan, f, ensure_ascii=False, indent=2)

    with open(qs_path, "w", encoding="utf-8") as f:
        json.dump(spec.model_dump(), f, ensure_ascii=False, indent=2)

    with open(sources_js, "w", encoding="utf-8") as f:
        json.dump(list(st.sources.keys()), f, ensure_ascii=False, indent=2)

    with open(serp_path, "w", encoding="utf-8") as f:
        json.dump(st.serp, f, ensure_ascii=False, indent=2)

    # Print results
    print("\n========== REPORT ==========\n")
    print(st.report or "")
    print("\n========== CANDIDATES (JSON, first 3) ==========\n")
    print(json.dumps(st.candidates[:3], ensure_ascii=False, indent=2))
    print("\n========== META ==========\n")

    meta = {
        "rounds": st.round + 1,
        "selected_urls": st.selected_urls,
        "num_sources": len(st.sources),
        "need_more": st.need_more,
        "followups": st.followups,
        "saved": {
            "report_md": md_path,
            "candidates_json": json_path,
            "plan_json": plan_path,
            "query_spec_json": qs_path,
            "used_sources_json": sources_js,
            "serp_dump_json": serp_path,
            "run_log": f"{SAVE_DIR}/{ts}_run.log",
        }
    }
    print(json.dumps(meta, ensure_ascii=False, indent=2))

    return {
        "rounds": st.round + 1,
        "plan": st.plan,
        "query_spec": spec.model_dump(),
        "selected_urls": st.selected_urls,
        "num_sources": len(st.sources),
        "report": st.report or "",
        "candidates": st.candidates,
        "need_more": st.need_more,
        "followups": st.followups,
        "used_sources": list(st.sources.keys()),
        "saved_paths": meta["saved"],
    }

# ============================ CLI INTERFACE ============================

def main():
    """CLI entry point"""
    parser = argparse.ArgumentParser(
        description="Talent Search via SearXNG + vLLM + LangGraph"
    )
    parser.add_argument(
        "question",
        nargs="*",
        help="your talent-scouting query"
    )

    args = parser.parse_args()

    q = " ".join(args.question) if args.question else (
        "Find 10 current PhD/MSc candidates in social simulation / multi-agent simulation; "
        "prioritize first authors from ICLR/ICML/NeurIPS/ACL/EMNLP/NAACL/KDD/WWW 2025/2024."
    )

    ts = now_ts()
    out = talent_search(q, ts=ts)

    print(f"\nFiles saved (ts={ts}):")
    for k, v in out["saved_paths"].items():
        print(f"- {k}: {v}")

if __name__ == "__main__":
    main()
