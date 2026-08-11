"""Runs all 3 insight agents over every candidate and produces a ranked shortlist.

Fraud-gating logic (mirrors the guardrail pattern from the architecture):
  - high fraud risk  -> pulled out of the ranking entirely, into manual review
  - medium fraud risk -> stays in the ranking but visibly flagged
  - low fraud risk    -> ranked normally by fit_score

Usage:
    cd hiring-intelligence
    python -m src.run_pipeline
"""

import json
import time

from .config import DATA_DIR, OUTPUT_DIR
from .agents.fraud_detection import analyze as check_fraud
from .agents.jd_fit import score as score_fit
from .agents.behavioral_traits import assess as assess_traits
from .agents.base import AgentCallFailed


def run_all_agents(candidate: dict, jd: dict) -> dict:
    fraud = check_fraud(candidate)
    fit = score_fit(candidate, jd)
    traits = assess_traits(candidate)

    total_cost = fraud.cost_of_insight.est_usd + fit.cost_of_insight.est_usd + traits.cost_of_insight.est_usd

    return {
        "candidate_id": candidate["candidate_id"],
        "name": candidate["name"],
        "source_channel": candidate.get("source_channel", "unknown"),
        "fraud_risk": fraud.fraud_risk,
        "fraud_flags": fraud.fraud_flags,
        "fraud_recommendation": fraud.recommendation,
        "fit_score": fit.fit_score,
        "requirements_met": fit.requirements_met,
        "requirements_missing": fit.requirements_missing,
        "leadership_score": traits.leadership_score,
        "loyalty_score": traits.loyalty_score,
        "trait_caveats": traits.caveats,
        "total_cost_usd": round(total_cost, 6),
        "raw": {
            "fraud": fraud.model_dump(),
            "fit": fit.model_dump(),
            "traits": traits.model_dump(),
        },
    }


def main():
    jd = json.loads((DATA_DIR / "jd.json").read_text())
    candidates = json.loads((DATA_DIR / "candidates.json").read_text())
    print(f"Role: {jd['title']} @ {jd['company']}")
    print(f"Scoring {len(candidates)} candidates against it...\n")

    results = []
    failures = []
    start = time.time()

    for c in candidates:
        print(f"{c['candidate_id']} ({c['name']})...")
        try:
            results.append(run_all_agents(c, jd))
        except AgentCallFailed as e:
            print(f"  ⚠️  ESCALATED TO HUMAN REVIEW: {e}")
            failures.append({"candidate_id": c["candidate_id"], "error": str(e)})

    elapsed = time.time() - start
    total_cost = sum(r["total_cost_usd"] for r in results)

    out_path = OUTPUT_DIR / "pipeline_results.json"
    out_path.write_text(json.dumps(results, indent=2))

    flagged_review = [r for r in results if r["fraud_risk"] == "high"]
    rankable = [r for r in results if r["fraud_risk"] != "high"]
    rankable.sort(key=lambda r: r["fit_score"], reverse=True)

    print(f"\n{'=' * 70}")
    print(f"Done in {elapsed:.1f}s  |  Total cost: ${total_cost:.4f}  |  "
          f"Escalated: {len(failures)}  |  Flagged for review: {len(flagged_review)}")
    print(f"{'=' * 70}\n")

    print("RANKED SHORTLIST")
    print("-" * 70)
    for i, r in enumerate(rankable, 1):
        flag = " [MEDIUM FRAUD RISK - reviewed but flagged]" if r["fraud_risk"] == "medium" else ""
        print(f"{i:2}. {r['name']:<22} fit={r['fit_score']:3}  "
              f"leadership={r['leadership_score']:.2f}  loyalty={r['loyalty_score']:.2f}{flag}")
        if r["requirements_missing"]:
            print(f"     missing: {r['requirements_missing']}")

    if flagged_review:
        print("\nFLAGGED FOR MANUAL REVIEW (high fraud risk - excluded from ranking)")
        print("-" * 70)
        for r in flagged_review:
            print(f"  - {r['name']} ({r['candidate_id']}): {r['fraud_flags']}")

    print(f"\nSaved: {out_path}")


if __name__ == "__main__":
    main()
