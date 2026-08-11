"""TrustHire Intelligence - Dashboard (Streamlit)

Run:
    cd hiring-intelligence
    streamlit run src/dashboard.py

Reads output/pipeline_results.json (produced by `python -m src.run_pipeline`).
Accept/override clicks are logged to output/feedback_log.json - the raw
material for the Confidence Calibration Feedback Loop described in the
architecture doc (comparing stated confidence against what a human actually
decided, over time).
"""

import json
from datetime import datetime, timezone
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
OUTPUT_DIR = ROOT / "output"
RESULTS_PATH = OUTPUT_DIR / "pipeline_results.json"
FEEDBACK_LOG_PATH = OUTPUT_DIR / "feedback_log.json"

st.set_page_config(page_title="TrustHire Intelligence", layout="wide")


def load_results():
    if not RESULTS_PATH.exists():
        st.error(f"No results yet. Run `python -m src.run_pipeline` first.\nExpected: {RESULTS_PATH}")
        st.stop()
    return json.loads(RESULTS_PATH.read_text())


def load_jd():
    return json.loads((DATA_DIR / "jd.json").read_text())


def log_feedback(candidate_id: str, decision: str, stated_confidence: float):
    log = []
    if FEEDBACK_LOG_PATH.exists():
        log = json.loads(FEEDBACK_LOG_PATH.read_text())
    log.append({
        "candidate_id": candidate_id,
        "decision": decision,  # "accepted" | "overridden"
        "stated_confidence": stated_confidence,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })
    FEEDBACK_LOG_PATH.write_text(json.dumps(log, indent=2))


results = load_results()
jd = load_jd()

st.title("TrustHire Intelligence")
st.caption(f"{jd['title']} — {jd['company']}  ·  {len(results)} candidates scored")

# ---- Cost / latency panel ----
total_cost = sum(r["total_cost_usd"] for r in results)
avg_cost = total_cost / len(results) if results else 0
flagged = [r for r in results if r["fraud_risk"] == "high"]
medium_risk = [r for r in results if r["fraud_risk"] == "medium"]
rankable = [r for r in results if r["fraud_risk"] != "high"]
rankable_sorted = sorted(rankable, key=lambda r: r["fit_score"], reverse=True)

c1, c2, c3, c4 = st.columns(4)
c1.metric("Total cost", f"${total_cost:.4f}")
c2.metric("Avg cost / candidate", f"${avg_cost:.4f}")
c3.metric("Flagged for review", len(flagged))
c4.metric("Ranked shortlist", len(rankable))

st.divider()

# ---- Ranked shortlist ----
st.subheader("Ranked Shortlist")

if not FEEDBACK_LOG_PATH.exists():
    FEEDBACK_LOG_PATH.write_text("[]")

for i, r in enumerate(rankable_sorted, 1):
    risk_badge = " \U0001F7E1 medium fraud risk - reviewed but flagged" if r["fraud_risk"] == "medium" else ""
    with st.expander(f"**{i}. {r['name']}**  —  fit {r['fit_score']}/100  ·  "
                      f"leadership {r['leadership_score']:.2f}  ·  loyalty {r['loyalty_score']:.2f}"
                      f"{risk_badge}", expanded=(i <= 3)):
        col_a, col_b = st.columns([2, 1])

        with col_a:
            st.markdown(f"**Source:** {r['source_channel']}")
            st.markdown(f"**Fit recommendation:** {r['raw']['fit']['recommendation']}")
            if r["requirements_met"]:
                st.markdown("**Requirements met:**")
                for req in r["requirements_met"]:
                    st.markdown(f"- ✅ {req}")
            if r["requirements_missing"]:
                st.markdown("**Requirements missing:**")
                for req in r["requirements_missing"]:
                    st.markdown(f"- ❌ {req}")

            st.markdown("**Behavioral trait evidence:**")
            for e in r["raw"]["traits"]["evidence"]:
                st.markdown(f"- {e}")
            if r["trait_caveats"]:
                st.caption("Caveats: " + " / ".join(r["trait_caveats"]))

            if r["fraud_risk"] == "medium":
                st.warning(f"Fraud flags: {'; '.join(r['fraud_flags'])}")

        with col_b:
            st.metric("Fit confidence", f"{r['raw']['fit']['confidence_score']:.0%}")
            st.metric("Cost of insight (all 3 agents)", f"${r['total_cost_usd']:.4f}")
            st.markdown("**Recruiter decision:**")
            bc1, bc2 = st.columns(2)
            if bc1.button("✅ Accept", key=f"accept_{r['candidate_id']}"):
                log_feedback(r["candidate_id"], "accepted", r["raw"]["fit"]["confidence_score"])
                st.toast(f"Logged: accepted {r['name']}")
            if bc2.button("↩️ Override", key=f"override_{r['candidate_id']}"):
                log_feedback(r["candidate_id"], "overridden", r["raw"]["fit"]["confidence_score"])
                st.toast(f"Logged: overrode {r['name']}")

st.divider()

# ---- Flagged for manual review ----
if flagged:
    st.subheader(f"\U0001F6A9 Flagged for Manual Review ({len(flagged)})")
    st.caption("Excluded from the ranking above - high fraud risk, needs a human before advancing.")
    for r in flagged:
        with st.expander(f"**{r['name']}** ({r['candidate_id']}) — {r['source_channel']}"):
            st.markdown(f"**Recommendation:** {r['fraud_recommendation']}")
            st.markdown("**Fraud flags:**")
            for f in r["fraud_flags"]:
                st.markdown(f"- {f}")
            st.markdown("**Evidence:**")
            for e in r["raw"]["fraud"]["evidence"]:
                st.markdown(f"- {e}")
            st.caption(f"Confidence: {r['raw']['fraud']['confidence_score']:.0%}  ·  "
                       f"Alternative: {r['raw']['fraud']['alternative']}")

st.caption("Every recommendation above carries evidence + a confidence score — "
           "never just a number. Accept/override clicks feed the confidence-calibration loop.")
