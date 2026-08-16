"""TrustHire Intelligence - Dashboard (Streamlit)

Run:
    cd hiring-intelligence
    streamlit run src/dashboard.py

Three views, drill-down navigation (not one long scrolling page):
  Requirements (open roles) -> Candidate Ranking (for one role) -> Candidate Profile

Reads output/pipeline_results.json (produced by `python -m src.run_pipeline`).
Accept/override clicks are logged to output/feedback_log.json - the raw
material for the confidence-calibration feedback loop described in the
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

# ---- Status palette (fixed, reserved meaning - never reused for anything else) ----
STATUS = {
    "low": {"color": "#0ca30c", "icon": "✓", "label": "Low risk"},
    "medium": {"color": "#fab219", "icon": "⚠", "label": "Medium risk"},
    "high": {"color": "#d03b3b", "icon": "✕", "label": "High risk"},
}
ACCENT = "#3987e5"       # sequential blue - fit score
ACCENT_TRACK = "#1c3a5e"  # darker step of the same ramp, recedes on dark surface
INK = "#ffffff"
INK_SECONDARY = "#c3c2b7"
INK_MUTED = "#898781"
SURFACE_2 = "#242422"
BORDER = "rgba(255,255,255,0.10)"

st.set_page_config(page_title="TrustHire Intelligence", layout="wide", initial_sidebar_state="collapsed")

st.markdown(f"""
<style>
#MainMenu {{visibility: hidden;}}
footer {{visibility: hidden;}}
.block-container {{ padding-top: 2rem; max-width: 1100px; }}
.status-badge {{
    display: inline-flex; align-items: center; gap: 5px;
    padding: 3px 10px; border-radius: 999px; font-size: 0.82rem; font-weight: 600;
    white-space: nowrap;
}}
.stat-tile {{
    border: 1px solid {BORDER}; border-radius: 10px; padding: 14px 18px;
    background: {SURFACE_2};
}}
.stat-tile .label {{ color: {INK_SECONDARY}; font-size: 0.82rem; margin-bottom: 4px; }}
.stat-tile .value {{ color: {INK}; font-size: 1.7rem; font-weight: 600; line-height: 1.1; }}
.meta-line {{ color: {INK_SECONDARY}; font-size: 0.88rem; }}
.section-label {{
    color: {INK_MUTED}; font-size: 0.78rem; text-transform: uppercase;
    letter-spacing: 0.04em; margin: 4px 0 10px 0;
}}
div[data-testid="stVerticalBlockBorderWrapper"] {{
    border-color: {BORDER} !important;
    border-radius: 12px !important;
}}
</style>
""", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

@st.cache_data
def load_data():
    jds = json.loads((DATA_DIR / "jd.json").read_text())
    candidates = json.loads((DATA_DIR / "candidates.json").read_text())
    if not RESULTS_PATH.exists():
        st.error(f"No results yet. Run `python -m src.run_pipeline` first.\nExpected: {RESULTS_PATH}")
        st.stop()
    results = json.loads(RESULTS_PATH.read_text())
    return jds, candidates, results


def log_feedback(candidate_id: str, decision: str, stated_confidence: float):
    log = []
    if FEEDBACK_LOG_PATH.exists():
        log = json.loads(FEEDBACK_LOG_PATH.read_text())
    log.append({
        "candidate_id": candidate_id,
        "decision": decision,
        "stated_confidence": stated_confidence,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })
    FEEDBACK_LOG_PATH.write_text(json.dumps(log, indent=2))


def load_feedback() -> dict:
    """Not cached - must reflect writes from this same session immediately."""
    if not FEEDBACK_LOG_PATH.exists():
        return {}
    log = json.loads(FEEDBACK_LOG_PATH.read_text())
    latest = {}
    for entry in log:  # log is append-only in chronological order; later entries win
        latest[entry["candidate_id"]] = entry
    return latest


# ---------------------------------------------------------------------------
# Small components
# ---------------------------------------------------------------------------

def status_badge(risk: str) -> str:
    s = STATUS.get(risk, {"color": INK_MUTED, "icon": "?", "label": risk})
    return (f'<span class="status-badge" style="background:{s["color"]}22;'
            f'color:{s["color"]};border:1px solid {s["color"]}66;">{s["icon"]} {s["label"]}</span>')


def fit_meter(score: int) -> str:
    pct = max(0, min(100, score))
    return f'''<div style="display:flex;align-items:center;gap:10px;">
      <div style="flex:1;height:8px;border-radius:4px;background:{ACCENT_TRACK};overflow:hidden;">
        <div style="width:{pct}%;height:100%;border-radius:4px;background:{ACCENT};"></div>
      </div>
      <span style="font-weight:600;color:{INK};min-width:32px;text-align:right;">{pct}</span>
    </div>'''


def stat_tile(label: str, value: str) -> str:
    return f'<div class="stat-tile"><div class="label">{label}</div><div class="value">{value}</div></div>'


# ---------------------------------------------------------------------------
# Navigation (session-state driven, not Streamlit's file-based multipage)
# ---------------------------------------------------------------------------

if "view" not in st.session_state:
    st.session_state.view = "requirements"
    st.session_state.job_id = None
    st.session_state.candidate_id = None


def go(view: str, **kwargs):
    st.session_state.view = view
    for k, v in kwargs.items():
        st.session_state[k] = v
    st.rerun()


jds, candidates, results = load_data()
jds_by_id = {j["job_id"]: j for j in jds}
candidates_by_id = {c["candidate_id"]: c for c in candidates}
feedback = load_feedback()


def reviewed_tag(candidate_id: str) -> str | None:
    fb = feedback.get(candidate_id)
    if not fb:
        return None
    color = "#0ca30c" if fb["decision"] == "accepted" else "#fab219"
    icon = "✅" if fb["decision"] == "accepted" else "↩️"
    label = "Accepted" if fb["decision"] == "accepted" else "Overridden"
    return f'<span class="status-badge" style="background:{color}22;color:{color};border:1px solid {color}66;">{icon} {label}</span>'


# ---------------------------------------------------------------------------
# View 1 - Requirements (open roles)
# ---------------------------------------------------------------------------

def view_requirements():
    st.title("TrustHire Intelligence")
    st.caption("Open requirements — select one to see its ranked candidates")
    st.write("")

    for jd in jds:
        job_results = [r for r in results if r["job_id"] == jd["job_id"]]
        flagged = [r for r in job_results if r["fraud_risk"] == "high"]
        rankable = [r for r in job_results if r["fraud_risk"] != "high"]
        avg_fit = round(sum(r["fit_score"] for r in rankable) / len(rankable)) if rankable else 0

        with st.container(border=True):
            cols = st.columns([3, 1, 1, 1, 1.2])
            with cols[0]:
                st.markdown(f"### {jd['title']}")
                st.markdown(f'<div class="meta-line">{jd["company"]} &middot; {jd["location"]} '
                            f'&middot; posted {jd["posted_date"]}</div>', unsafe_allow_html=True)
            with cols[1]:
                st.markdown(stat_tile("Candidates", str(len(job_results))), unsafe_allow_html=True)
            with cols[2]:
                st.markdown(stat_tile("Shortlist", str(len(rankable))), unsafe_allow_html=True)
            with cols[3]:
                st.markdown(stat_tile("Avg fit", str(avg_fit)), unsafe_allow_html=True)
            with cols[4]:
                st.markdown(stat_tile("Flagged", str(len(flagged))), unsafe_allow_html=True)
            st.write("")
            if st.button("View Candidates →", key=f"open_{jd['job_id']}", type="primary"):
                go("candidates", job_id=jd["job_id"])


# ---------------------------------------------------------------------------
# View 2 - Candidate ranking (for one requirement)
# ---------------------------------------------------------------------------

def view_candidates():
    jd = jds_by_id[st.session_state.job_id]
    job_results = [r for r in results if r["job_id"] == jd["job_id"]]
    flagged = [r for r in job_results if r["fraud_risk"] == "high"]
    rankable = sorted([r for r in job_results if r["fraud_risk"] != "high"],
                       key=lambda r: r["fit_score"], reverse=True)
    total_cost = sum(r["total_cost_usd"] for r in job_results)

    if st.button("← All Requirements"):
        go("requirements")

    st.title(jd["title"])
    st.caption(f'{jd["company"]} &middot; {len(job_results)} candidates scored')

    c1, c2, c3, c4 = st.columns(4)
    c1.markdown(stat_tile("Total cost", f"${total_cost:.4f}"), unsafe_allow_html=True)
    c2.markdown(stat_tile("Avg cost / candidate",
                f"${(total_cost / len(job_results)):.4f}" if job_results else "$0"), unsafe_allow_html=True)
    c3.markdown(stat_tile("Flagged for review", str(len(flagged))), unsafe_allow_html=True)
    c4.markdown(stat_tile("Ranked shortlist", str(len(rankable))), unsafe_allow_html=True)
    st.write("")

    st.markdown('<div class="section-label">Ranked shortlist &mdash; by fit score</div>', unsafe_allow_html=True)
    for i, r in enumerate(rankable, 1):
        with st.container(border=True):
            cols = st.columns([2.4, 2.4, 1.1, 1.1, 1.3])
            with cols[0]:
                st.markdown(f"**{i}. {r['name']}**")
                st.caption(r["source_channel"])
            with cols[1]:
                st.markdown(fit_meter(r["fit_score"]), unsafe_allow_html=True)
                st.caption("fit score")
            with cols[2]:
                st.markdown(f"**{r['leadership_score']:.2f}**")
                st.caption("leadership")
            with cols[3]:
                st.markdown(f"**{r['loyalty_score']:.2f}**")
                st.caption("loyalty")
            with cols[4]:
                if r["fraud_risk"] == "medium":
                    st.markdown(status_badge("medium"), unsafe_allow_html=True)
                tag = reviewed_tag(r["candidate_id"])
                if tag:
                    st.markdown(tag, unsafe_allow_html=True)
                if st.button("View Profile →", key=f"prof_{r['candidate_id']}"):
                    go("profile", candidate_id=r["candidate_id"])

    if flagged:
        st.write("")
        st.markdown(f'<div class="section-label">\U0001F6A8 Flagged for manual review ({len(flagged)}) '
                    f'&mdash; excluded from ranking above</div>', unsafe_allow_html=True)
        for r in flagged:
            with st.container(border=True):
                cols = st.columns([2.6, 1.7, 1.7, 1.5])
                with cols[0]:
                    st.markdown(f"**{r['name']}**")
                    st.caption(r["source_channel"])
                with cols[1]:
                    st.markdown(status_badge("high"), unsafe_allow_html=True)
                with cols[2]:
                    tag = reviewed_tag(r["candidate_id"])
                    if tag:
                        st.markdown(tag, unsafe_allow_html=True)
                with cols[3]:
                    if st.button("View Profile →", key=f"prof_{r['candidate_id']}"):
                        go("profile", candidate_id=r["candidate_id"])


# ---------------------------------------------------------------------------
# View 3 - Candidate profile
# ---------------------------------------------------------------------------

def view_profile():
    r = next(x for x in results if x["candidate_id"] == st.session_state.candidate_id)
    jd = jds_by_id[r["job_id"]]

    if st.button("← Back to Candidates"):
        go("candidates", job_id=r["job_id"])

    st.title(r["name"])
    st.caption(f'Applying for {jd["title"]} at {jd["company"]} &middot; via {r["source_channel"]}')
    st.markdown(status_badge(r["fraud_risk"]), unsafe_allow_html=True)
    st.write("")

    col_a, col_b = st.columns([2, 1])

    with col_a:
        st.markdown('<div class="section-label">Fit assessment</div>', unsafe_allow_html=True)
        st.markdown(fit_meter(r["fit_score"]), unsafe_allow_html=True)
        st.write(r["raw"]["fit"]["recommendation"])

        if r["requirements_met"]:
            st.markdown("**Requirements met**")
            for req in r["requirements_met"]:
                st.markdown(f"- ✅ {req}")
        if r["requirements_missing"]:
            st.markdown("**Requirements missing**")
            for req in r["requirements_missing"]:
                st.markdown(f"- ❌ {req}")

        st.write("")
        st.markdown('<div class="section-label">Behavioral trait evidence</div>', unsafe_allow_html=True)
        for e in r["raw"]["traits"]["evidence"]:
            st.markdown(f"- {e}")
        if r["trait_caveats"]:
            st.caption("Caveats: " + " / ".join(r["trait_caveats"]))

        if r["fraud_risk"] != "low":
            st.write("")
            st.markdown('<div class="section-label">Fraud detection</div>', unsafe_allow_html=True)
            st.write(r["fraud_recommendation"])
            for f in r["fraud_flags"]:
                st.markdown(f"- {f}")
            st.caption(f'Confidence: {r["raw"]["fraud"]["confidence_score"]:.0%} &middot; '
                       f'Alternative: {r["raw"]["fraud"]["alternative"]}')

    with col_b:
        st.markdown(stat_tile("Fit confidence", f'{r["raw"]["fit"]["confidence_score"]:.0%}'),
                    unsafe_allow_html=True)
        st.write("")
        st.markdown(stat_tile("Leadership", f'{r["leadership_score"]:.2f}'), unsafe_allow_html=True)
        st.write("")
        st.markdown(stat_tile("Loyalty", f'{r["loyalty_score"]:.2f}'), unsafe_allow_html=True)
        st.write("")
        st.markdown(stat_tile("Cost of insight (3 agents)", f'${r["total_cost_usd"]:.4f}'),
                    unsafe_allow_html=True)
        st.write("")
        st.markdown("**Recruiter decision**")

        existing = feedback.get(r["candidate_id"])
        if existing:
            ts = datetime.fromisoformat(existing["timestamp"]).strftime("%b %d, %I:%M %p UTC")
            if existing["decision"] == "accepted":
                st.success(f"✅ Accepted — logged {ts}")
            else:
                st.warning(f"↩️ Overridden — logged {ts}")
            st.caption("Click either button below to change this decision.")
        else:
            st.caption("Not yet reviewed.")

        bc1, bc2 = st.columns(2)
        if bc1.button("✅ Accept", key=f"accept_{r['candidate_id']}"):
            log_feedback(r["candidate_id"], "accepted", r["raw"]["fit"]["confidence_score"])
            st.rerun()
        if bc2.button("↩️ Override", key=f"override_{r['candidate_id']}"):
            log_feedback(r["candidate_id"], "overridden", r["raw"]["fit"]["confidence_score"])
            st.rerun()


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

if st.session_state.view == "requirements":
    view_requirements()
elif st.session_state.view == "candidates":
    view_candidates()
elif st.session_state.view == "profile":
    view_profile()
