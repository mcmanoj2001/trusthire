"""TrustHire Intelligence - Dashboard (Streamlit)

Run:
    cd hiring-intelligence
    streamlit run src/dashboard.py

Three views, drill-down navigation (not one long scrolling page):
  Requirements (open roles) -> Candidate Ranking (for one role) -> Candidate Profile

Reads output/pipeline_results.json (produced by `python -m src.run_pipeline`).

Hiring pipeline tracking (output/pipeline_state.json): every candidate has a
category (Shortlisted / Flagged for Risk / Not Moving Forward) and a round
(AI Screening -> Technical Screening -> ...). Category defaults from the
fraud-detection agent's risk rating but is human-movable from any list view
or the profile page - moving/advancing appends a timestamped, comment-able
history entry. This is also what feeds the confidence-calibration feedback
loop described in the architecture doc (comparing stated confidence against
what a human actually decided, over time).
"""

import json
from datetime import datetime, timezone
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
OUTPUT_DIR = ROOT / "output"
RESULTS_PATH = OUTPUT_DIR / "pipeline_results.json"
PIPELINE_STATE_PATH = OUTPUT_DIR / "pipeline_state.json"

# ---- Status palette (fixed, reserved meaning - never reused for anything else) ----
STATUS = {
    "low": {"color": "#0ca30c", "icon": "✓", "label": "Low risk"},
    "medium": {"color": "#fab219", "icon": "⚠", "label": "Medium risk"},
    "high": {"color": "#d03b3b", "icon": "✕", "label": "High risk"},
}

# ---- Hiring pipeline: rounds and categories ----
ROUNDS = ["AI Screening", "Technical Screening"]

CATEGORIES = {
    "shortlisted": {"label": "Shortlisted", "color": "#3987e5"},
    # All three non-shortlisted categories default to red - a candidate that
    # isn't actively progressing should read as "stop" at a glance, not blend
    # into neutral gray.
    "flagged_for_risk": {"label": "Flagged for Risk", "color": "#d03b3b"},
    "not_suitable": {"label": "Not Suitable", "color": "#d03b3b"},
    "not_moving_forward": {"label": "Not Moving Forward", "color": "#d03b3b"},
}
CATEGORY_ORDER = ["shortlisted", "flagged_for_risk", "not_suitable", "not_moving_forward"]

ACCENT = "#3987e5"       # sequential blue - fit score
ACCENT_TRACK = "#1c3a5e"  # darker step of the same ramp, recedes on dark surface
TRACK_NEUTRAL = "#333331"  # meter track when the fill is RAG-colored, not always blue
INK = "#ffffff"
INK_SECONDARY = "#c3c2b7"
INK_MUTED = "#898781"
SURFACE_2 = "#242422"
BORDER = "rgba(255,255,255,0.10)"
HEADING_GRADIENT = "linear-gradient(90deg, #3987e5 0%, #7c5cff 55%, #d946ef 100%)"  # blue -> violet -> magenta

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
.round-badge {{
    display: inline-flex; align-items: center;
    padding: 3px 10px; border-radius: 999px; font-size: 0.78rem; font-weight: 600;
    background: {SURFACE_2}; border: 1px solid {BORDER}; color: {INK_SECONDARY};
    white-space: nowrap;
}}
.stat-tile {{
    border: 1px solid {BORDER}; border-radius: 10px; padding: 14px 18px;
    background: {SURFACE_2};
}}
.stat-tile .label {{ color: {INK_SECONDARY}; font-size: 0.82rem; margin-bottom: 4px; }}
.stat-tile .value {{ color: {INK}; font-size: 1.7rem; font-weight: 600; line-height: 1.1; }}
.cost-strip {{
    display: inline-flex; align-items: center; float: right;
    border: 1px solid {BORDER}; border-radius: 8px; padding: 7px 14px;
    background: transparent;
}}
.cost-strip-label {{ color: {INK_MUTED}; font-size: 0.68rem; text-transform: uppercase; letter-spacing: 0.03em; }}
.cost-strip-value {{ color: {INK_SECONDARY}; font-size: 0.95rem; font-weight: 600; }}
.meta-line {{ color: {INK_SECONDARY}; font-size: 0.88rem; }}
.section-label {{
    color: {INK_MUTED}; font-size: 0.78rem; text-transform: uppercase;
    letter-spacing: 0.04em; margin: 4px 0 10px 0;
}}
div[data-testid="stVerticalBlockBorderWrapper"] {{
    border-color: {BORDER} !important;
    border-radius: 12px !important;
}}
.gradient-heading {{
    background: {HEADING_GRADIENT};
    -webkit-background-clip: text; background-clip: text; -webkit-text-fill-color: transparent;
    display: inline-block; line-height: 1.2; margin: 0;
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


def save_jds(jds: list):
    (DATA_DIR / "jd.json").write_text(json.dumps(jds, indent=2))


def next_job_id(jds: list) -> str:
    nums = [int(j["job_id"].split("_")[1]) for j in jds if j["job_id"].startswith("JOB_")]
    return f"JOB_{(max(nums) + 1) if nums else 1:03d}"


def load_pipeline_state() -> dict:
    """Not cached - must reflect writes from this same session immediately."""
    if not PIPELINE_STATE_PATH.exists():
        return {}
    return json.loads(PIPELINE_STATE_PATH.read_text())


def save_pipeline_state(state: dict):
    PIPELINE_STATE_PATH.write_text(json.dumps(state, indent=2))


def missing_must_haves(r: dict, jd: dict) -> list[str]:
    """Cross-references the JD-fit agent's requirements_missing (which mixes
    must-haves and nice-to-haves despite its prompt) against the JD's actual
    must_haves list, so a missing nice-to-have never gets treated as a
    disqualifier. The agent reliably restates a must-have's exact text inside
    the missing-item string (sometimes with an appended clause), so substring
    containment is enough - no second LLM call needed."""
    musts = jd.get("must_haves", [])
    hits = []
    for item in r.get("requirements_missing", []):
        for mh in musts:
            if mh.strip().lower() in item.strip().lower():
                hits.append(mh)
                break
    return hits


def default_category(fraud_risk: str, not_suitable: bool = False) -> str:
    if fraud_risk == "high":
        return "flagged_for_risk"
    if not_suitable:
        return "not_suitable"
    return "shortlisted"


def get_candidate_state(state: dict, candidate_id: str, fraud_risk: str, not_suitable: bool = False) -> dict:
    entry = state.get(candidate_id)
    if entry:
        return entry
    return {"category": default_category(fraud_risk, not_suitable), "round_index": 0, "history": []}


def record_action(state: dict, candidate_id: str, fraud_risk: str, not_suitable: bool = False, *,
                   category: str | None = None, advance: bool = False, comment: str = ""):
    cur = get_candidate_state(state, candidate_id, fraud_risk, not_suitable)
    round_index = cur["round_index"]
    new_category = category if category is not None else cur["category"]

    if advance:
        round_index = min(round_index + 1, len(ROUNDS) - 1)
        action_label = f"Advanced to {ROUNDS[round_index]}"
    elif category is not None and category != cur["category"]:
        action_label = f"Moved to {CATEGORIES[category]['label']}"
    else:
        action_label = "Comment added"

    history = list(cur["history"])
    history.append({
        "round_index": round_index,
        "round_name": ROUNDS[round_index],
        "action": action_label,
        "comment": comment,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })
    state[candidate_id] = {"category": new_category, "round_index": round_index, "history": history}
    save_pipeline_state(state)


def requires_comment(r: dict, new_category: str) -> bool:
    """A comment is mandatory for a category move UNLESS the system itself
    already supplied a flagged reason for that destination - e.g. moving a
    high-fraud-risk candidate to Flagged for Risk just confirms the agent's
    own finding, so making a human retype it would be pure friction."""
    if new_category == "flagged_for_risk":
        return r["fraud_risk"] == "low"
    if new_category == "not_suitable":
        return not r.get("not_suitable", False)
    if new_category == "not_moving_forward":
        has_system_reason = r["fraud_risk"] == "high" or bool(r["requirements_missing"])
        return not has_system_reason
    if new_category == "shortlisted":
        system_favorable = r["fraud_risk"] == "low" and not r["requirements_missing"]
        return not system_favorable
    return True


# ---------------------------------------------------------------------------
# Small components
# ---------------------------------------------------------------------------

def rag_color(value: float, scale_max: float = 1.0) -> str:
    """Maps a 0..scale_max metric onto the fixed status palette so fit score,
    leadership, and loyalty all read red/amber/green at a glance instead of
    requiring the viewer to parse a raw number."""
    pct = (value / scale_max) if scale_max else 0
    if pct >= 0.7:
        return STATUS["low"]["color"]
    if pct >= 0.4:
        return STATUS["medium"]["color"]
    return STATUS["high"]["color"]


def gradient_heading(text: str, size: str = "2.25rem", weight: int = 800) -> str:
    return f'<div class="gradient-heading" style="font-size:{size};font-weight:{weight};">{text}</div>'


def status_badge(risk: str) -> str:
    s = STATUS.get(risk, {"color": INK_MUTED, "icon": "?", "label": risk})
    return (f'<span class="status-badge" style="background:{s["color"]}22;'
            f'color:{s["color"]};border:1px solid {s["color"]}66;">{s["icon"]} {s["label"]}</span>')


def category_badge(category: str) -> str:
    c = CATEGORIES.get(category, {"label": category, "color": INK_MUTED})
    return (f'<span class="status-badge" style="background:{c["color"]}22;'
            f'color:{c["color"]};border:1px solid {c["color"]}66;">{c["label"]}</span>')


def round_badge(round_index: int) -> str:
    return f'<span class="round-badge">Round {round_index + 1}: {ROUNDS[round_index]}</span>'


def fit_meter(score: int) -> str:
    pct = max(0, min(100, score))
    fill = rag_color(pct, 100)
    return f'''<div style="display:flex;align-items:center;gap:10px;">
      <div style="flex:1;height:8px;border-radius:4px;background:{TRACK_NEUTRAL};overflow:hidden;">
        <div style="width:{pct}%;height:100%;border-radius:4px;background:{fill};"></div>
      </div>
      <span style="font-weight:600;color:{fill};min-width:32px;text-align:right;">{pct}</span>
    </div>'''


def stat_tile(label: str, value: str, value_color: str | None = None) -> str:
    color_style = f' style="color:{value_color};"' if value_color else ""
    return (f'<div class="stat-tile"><div class="label">{label}</div>'
            f'<div class="value"{color_style}>{value}</div></div>')


def cost_strip(total: float, avg: float | None = None) -> str:
    """Deliberately smaller and quieter than stat_tile - cost is good-to-know
    operational context here, not one of the business decisions this dashboard
    is for. Never given the same visual weight as fit/leadership/loyalty/flags."""
    avg_html = ""
    if avg is not None:
        avg_html = (f'<div style="width:1px;align-self:stretch;background:{BORDER};margin:0 10px;"></div>'
                    f'<div><div class="cost-strip-label">avg / candidate</div>'
                    f'<div class="cost-strip-value">${avg:.4f}</div></div>')
    return (f'<div class="cost-strip"><div><div class="cost-strip-label">cost of analysis</div>'
            f'<div class="cost-strip-value">${total:.4f}</div></div>{avg_html}</div>')


def move_control(state: dict, r: dict, key_prefix: str):
    """Compact category-move dropdown usable from any list row. Applies
    immediately on change UNLESS the destination needs a comment the system
    hasn't already supplied a reason for - then it holds for an inline
    comment + confirm instead of silently moving the candidate."""
    cat_state = r["_cat_state"]
    candidate_id = r["candidate_id"]
    widget_key = f"{key_prefix}_{candidate_id}"
    pending_key = f"pending_move_{widget_key}"

    pending = st.session_state.get(pending_key)
    if pending:
        st.caption(f"Move to **{CATEGORIES[pending]['label']}** — comment required:")
        reason = st.text_input("Reason", key=f"{pending_key}_comment", label_visibility="collapsed",
                                placeholder="Why is this candidate moving?")
        c1, c2 = st.columns(2)
        with c1:
            if st.button("Confirm", key=f"{pending_key}_confirm"):
                if reason.strip():
                    record_action(state, candidate_id, r["fraud_risk"], r["not_suitable"],
                                  category=pending, comment=reason)
                    del st.session_state[pending_key]
                    st.rerun()
                else:
                    st.error("A comment is required for this move.")
        with c2:
            if st.button("Cancel", key=f"{pending_key}_cancel"):
                st.session_state[widget_key] = CATEGORIES[cat_state["category"]]["label"]
                del st.session_state[pending_key]
                st.rerun()
        return

    labels = [CATEGORIES[c]["label"] for c in CATEGORY_ORDER]
    cur_idx = CATEGORY_ORDER.index(cat_state["category"])
    choice = st.selectbox("Move to", labels, index=cur_idx,
                           key=widget_key, label_visibility="collapsed")
    new_cat = CATEGORY_ORDER[labels.index(choice)]
    if new_cat != cat_state["category"]:
        if requires_comment(r, new_cat):
            st.session_state[pending_key] = new_cat
            st.rerun()
        else:
            record_action(state, candidate_id, r["fraud_risk"], r["not_suitable"], category=new_cat)
            st.rerun()


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
for _r in results:
    _hits = missing_must_haves(_r, jds_by_id[_r["job_id"]])
    _r["missing_must_haves"] = _hits
    _r["not_suitable"] = bool(_hits)


# ---------------------------------------------------------------------------
# View 1 - Requirements (open roles)
# ---------------------------------------------------------------------------

def view_requirements():
    title_col, add_col = st.columns([4, 1.3])
    with title_col:
        st.markdown(gradient_heading("TrustHire Intelligence"), unsafe_allow_html=True)
        st.caption("Open requirements — select one to see its ranked candidates")
    with add_col:
        st.write("")
        st.write("")
        if st.button("+ Add Requirement", key="add_requirement_btn"):
            go("new_requirement")
    st.write("")

    state = load_pipeline_state()

    for jd in jds:
        job_results = [r for r in results if r["job_id"] == jd["job_id"]]
        cats = [get_candidate_state(state, r["candidate_id"], r["fraud_risk"], r["not_suitable"])["category"]
                for r in job_results]
        shortlisted_n = cats.count("shortlisted")
        flagged_n = cats.count("flagged_for_risk")
        shortlisted_scores = [r["fit_score"] for r, c in zip(job_results, cats) if c == "shortlisted"]
        avg_fit = round(sum(shortlisted_scores) / len(shortlisted_scores)) if shortlisted_scores else 0

        with st.container(border=True):
            cols = st.columns([3, 1, 1, 1, 1.2])
            with cols[0]:
                st.markdown(gradient_heading(jd["title"], size="1.5rem", weight=700), unsafe_allow_html=True)
                st.markdown(f'<div class="meta-line">{jd["company"]} &middot; {jd["location"]} '
                            f'&middot; posted {jd["posted_date"]}</div>', unsafe_allow_html=True)
            with cols[1]:
                st.markdown(stat_tile("Candidates", str(len(job_results))), unsafe_allow_html=True)
            with cols[2]:
                st.markdown(stat_tile("Shortlist", str(shortlisted_n)), unsafe_allow_html=True)
            with cols[3]:
                avg_color = rag_color(avg_fit, 100) if shortlisted_scores else None
                st.markdown(stat_tile("Avg fit", f"{avg_fit}%", avg_color), unsafe_allow_html=True)
            with cols[4]:
                st.markdown(stat_tile("Flagged", str(flagged_n)), unsafe_allow_html=True)
            st.write("")
            if st.button("View Candidates →", key=f"open_{jd['job_id']}", type="primary"):
                go("candidates", job_id=jd["job_id"])


# ---------------------------------------------------------------------------
# View 2 - Candidate ranking (for one requirement)
# ---------------------------------------------------------------------------

def candidate_row(r: dict, state: dict, key_prefix: str, rank: int | None = None):
    cat_state = r["_cat_state"]
    with st.container(border=True):
        cols = st.columns([2.1, 1.8, 0.9, 0.9, 1.9])
        with cols[0]:
            name_line = f"{rank}. {r['name']}" if rank else r["name"]
            st.markdown(f"**{name_line}**")
            st.caption(r["source_channel"])
        with cols[1]:
            st.markdown(fit_meter(r["fit_score"]), unsafe_allow_html=True)
            st.caption("fit score")
        with cols[2]:
            st.markdown(f'<span style="font-weight:600;color:{rag_color(r["leadership_score"], 1.0)};">'
                        f'{r["leadership_score"]:.2f}</span>', unsafe_allow_html=True)
            st.caption("leadership")
        with cols[3]:
            st.markdown(f'<span style="font-weight:600;color:{rag_color(r["loyalty_score"], 1.0)};">'
                        f'{r["loyalty_score"]:.2f}</span>', unsafe_allow_html=True)
            st.caption("loyalty")
        with cols[4]:
            if r["fraud_risk"] == "medium" and cat_state["category"] == "shortlisted":
                st.markdown(status_badge("medium"), unsafe_allow_html=True)
            st.markdown(round_badge(cat_state["round_index"]), unsafe_allow_html=True)

        cols2 = st.columns([2, 2.3, 1.5])
        with cols2[0]:
            move_control(state, r, key_prefix)
        with cols2[1]:
            if cat_state["category"] == "shortlisted" and cat_state["round_index"] < len(ROUNDS) - 1:
                next_round = ROUNDS[cat_state["round_index"] + 1]
                if st.button(f"Advance to {next_round} →", key=f"{key_prefix}_adv_{r['candidate_id']}"):
                    record_action(state, r["candidate_id"], r["fraud_risk"], r["not_suitable"], advance=True)
                    st.rerun()
        with cols2[2]:
            if st.button("View Profile →", key=f"{key_prefix}_prof_{r['candidate_id']}"):
                go("profile", candidate_id=r["candidate_id"])


def view_candidates():
    jd = jds_by_id[st.session_state.job_id]
    job_results = [r for r in results if r["job_id"] == jd["job_id"]]
    total_cost = sum(r["total_cost_usd"] for r in job_results)

    state = load_pipeline_state()
    for r in job_results:
        r["_cat_state"] = get_candidate_state(state, r["candidate_id"], r["fraud_risk"], r["not_suitable"])

    shortlisted = sorted([r for r in job_results if r["_cat_state"]["category"] == "shortlisted"],
                          key=lambda r: r["fit_score"], reverse=True)
    flagged = sorted([r for r in job_results if r["_cat_state"]["category"] == "flagged_for_risk"],
                      key=lambda r: r["fit_score"], reverse=True)
    not_suitable = sorted([r for r in job_results if r["_cat_state"]["category"] == "not_suitable"],
                           key=lambda r: r["fit_score"], reverse=True)
    not_moving = sorted([r for r in job_results if r["_cat_state"]["category"] == "not_moving_forward"],
                         key=lambda r: r["fit_score"], reverse=True)

    if st.button("← All Requirements"):
        go("requirements")

    title_col, cost_col = st.columns([3, 1])
    with title_col:
        st.markdown(gradient_heading(jd["title"]), unsafe_allow_html=True)
        st.caption(f'{jd["company"]} &middot; {len(job_results)} candidates scored')
    with cost_col:
        st.write("")
        avg_cost = (total_cost / len(job_results)) if job_results else 0
        st.markdown(cost_strip(total_cost, avg_cost), unsafe_allow_html=True)

    c1, c2, c3 = st.columns(3)
    c1.markdown(stat_tile("Ranked shortlist", str(len(shortlisted))), unsafe_allow_html=True)
    c2.markdown(stat_tile("Flagged for review", str(len(flagged))), unsafe_allow_html=True)
    c3.markdown(stat_tile("Not suitable", str(len(not_suitable))), unsafe_allow_html=True)
    st.write("")

    st.markdown('<div class="section-label">Ranked shortlist &mdash; by fit score</div>', unsafe_allow_html=True)
    if shortlisted:
        for i, r in enumerate(shortlisted, 1):
            candidate_row(r, state, "sl", rank=i)
    else:
        st.caption("No candidates currently shortlisted.")

    st.write("")
    st.markdown(f'<div class="section-label">\U0001F6A8 Flagged for Risk ({len(flagged)})</div>',
                unsafe_allow_html=True)
    if flagged:
        for r in flagged:
            candidate_row(r, state, "fl")
    else:
        st.caption("No candidates currently flagged.")

    if not_suitable:
        st.write("")
        with st.expander(f"🚫 Not Suitable Profiles ({len(not_suitable)}) — auto-filtered for missing a "
                          f"must-have requirement", expanded=True):
            for r in not_suitable:
                cat_state = r["_cat_state"]
                cols = st.columns([2.3, 3.2, 1.8, 1.3])
                with cols[0]:
                    st.markdown(f"**{r['name']}**")
                    st.caption(f'{r["source_channel"]} · fit {r["fit_score"]}')
                with cols[1]:
                    st.caption("Missing: " + "; ".join(r["missing_must_haves"]))
                with cols[2]:
                    move_control(state, r, "ns")
                with cols[3]:
                    if st.button("View Profile →", key=f"ns_prof_{r['candidate_id']}"):
                        go("profile", candidate_id=r["candidate_id"])

    if not_moving:
        st.write("")
        with st.expander(f"Not Moving Forward ({len(not_moving)}) — kept out of the active lists above"):
            for r in not_moving:
                cat_state = r["_cat_state"]
                cols = st.columns([2.3, 2.5, 2, 1.3])
                with cols[0]:
                    st.markdown(f"**{r['name']}**")
                    st.caption(r["source_channel"])
                with cols[1]:
                    if cat_state["history"]:
                        last = cat_state["history"][-1]
                        st.caption(f"{last['action']} · {last['round_name']}")
                with cols[2]:
                    move_control(state, r, "nmf")
                with cols[3]:
                    if st.button("View Profile →", key=f"nmf_prof_{r['candidate_id']}"):
                        go("profile", candidate_id=r["candidate_id"])


# ---------------------------------------------------------------------------
# View 3 - Candidate profile
# ---------------------------------------------------------------------------

def view_profile():
    r = next(x for x in results if x["candidate_id"] == st.session_state.candidate_id)
    jd = jds_by_id[r["job_id"]]
    state = load_pipeline_state()
    cat_state = get_candidate_state(state, r["candidate_id"], r["fraud_risk"], r["not_suitable"])

    if st.button("← Back to Candidates"):
        go("candidates", job_id=r["job_id"])

    st.title(r["name"])
    st.caption(f'Applying for {jd["title"]} at {jd["company"]} &middot; via {r["source_channel"]}')
    badge_cols = st.columns([1.3, 1.4, 1.6, 4])
    badge_cols[0].markdown(status_badge(r["fraud_risk"]), unsafe_allow_html=True)
    badge_cols[1].markdown(category_badge(cat_state["category"]), unsafe_allow_html=True)
    badge_cols[2].markdown(round_badge(cat_state["round_index"]), unsafe_allow_html=True)
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
        fit_conf = r["raw"]["fit"]["confidence_score"]
        st.markdown(stat_tile("Fit confidence", f'{fit_conf:.0%}', rag_color(fit_conf, 1.0)),
                    unsafe_allow_html=True)
        st.write("")
        st.markdown(stat_tile("Leadership", f'{r["leadership_score"]:.2f}',
                               rag_color(r["leadership_score"], 1.0)), unsafe_allow_html=True)
        st.write("")
        st.markdown(stat_tile("Loyalty", f'{r["loyalty_score"]:.2f}',
                               rag_color(r["loyalty_score"], 1.0)), unsafe_allow_html=True)
        st.write("")
        st.markdown(cost_strip(r["total_cost_usd"]), unsafe_allow_html=True)

    st.write("")
    st.write("")
    st.markdown('<div class="section-label">Hiring pipeline</div>', unsafe_allow_html=True)

    comment = st.text_input("Comment (optional — attached to whichever action you take below)",
                             key=f"comment_{r['candidate_id']}")

    actions = []
    if cat_state["category"] == "shortlisted" and cat_state["round_index"] < len(ROUNDS) - 1:
        next_round = ROUNDS[cat_state["round_index"] + 1]
        actions.append((f"Advance to {next_round} →", {"advance": True}))
    for cat in CATEGORY_ORDER:
        if cat != cat_state["category"]:
            actions.append((f"Move to {CATEGORIES[cat]['label']}", {"category": cat}))

    action_cols = st.columns(len(actions))
    for col, (label, kwargs) in zip(action_cols, actions):
        if col.button(label, key=f"pact_{r['candidate_id']}_{label}"):
            target_category = kwargs.get("category")
            if target_category and requires_comment(r, target_category) and not comment.strip():
                st.error(f"A comment is required to move this candidate to "
                         f"{CATEGORIES[target_category]['label']} — the system hasn't already "
                         f"flagged a reason for this move.")
            else:
                record_action(state, r["candidate_id"], r["fraud_risk"], r["not_suitable"],
                              comment=comment, **kwargs)
                st.rerun()

    st.write("")
    if cat_state["history"]:
        st.markdown("**History**")
        for h in reversed(cat_state["history"]):
            ts = datetime.fromisoformat(h["timestamp"]).strftime("%b %d, %I:%M %p UTC")
            line = f"- **{h['action']}** — {h['round_name']} &middot; {ts}"
            st.markdown(line, unsafe_allow_html=True)
            if h["comment"]:
                st.caption(h["comment"])
    else:
        st.caption(f"No pipeline actions yet — currently at Round 1: {ROUNDS[0]}.")


# ---------------------------------------------------------------------------
# View 4 - New requirement intake
# ---------------------------------------------------------------------------

def view_new_requirement():
    if st.button("← All Requirements"):
        go("requirements")

    st.markdown(gradient_heading("New Requirement", size="2rem", weight=800), unsafe_allow_html=True)
    st.caption("Define a role to start scoring candidates against it.")
    st.write("")

    text_tab, voice_tab = st.tabs(["📝 Text & attachment", "🎙️ Voice intake"])

    with text_tab:
        uploaded = st.file_uploader(
            "Attach a JD file (.txt or .md) — optional, pre-fills the description below",
            type=["txt", "md"], key="jd_attachment",
        )
        prefill_description = ""
        if uploaded is not None:
            prefill_description = uploaded.read().decode("utf-8", errors="ignore")

        with st.form("new_requirement_form"):
            title = st.text_input("Job title*", placeholder="e.g. Data Platform Engineer")
            col1, col2 = st.columns(2)
            with col1:
                company = st.text_input("Company", value="Meridian Consulting Group")
            with col2:
                location = st.text_input("Location", value="Remote (US)")
            description = st.text_area("Description", value=prefill_description, height=100,
                                        placeholder="A short summary of the role.")
            must_haves_raw = st.text_area(
                "Must-haves* (one per line)", height=110,
                placeholder="5+ years of experience\nStrong SQL\nHands-on pipeline ownership",
            )
            nice_to_haves_raw = st.text_area(
                "Nice-to-haves (one per line)", height=90,
                placeholder="Cloud data warehouse experience\nMentoring experience",
            )
            submitted = st.form_submit_button("Create Requirement", type="primary")

        if submitted:
            must_haves = [line.strip() for line in must_haves_raw.splitlines() if line.strip()]
            if not title.strip() or not must_haves:
                st.error("A job title and at least one must-have requirement are required.")
            else:
                jds_current = json.loads((DATA_DIR / "jd.json").read_text())
                new_jd = {
                    "job_id": next_job_id(jds_current),
                    "title": title.strip(),
                    "company": company.strip() or "Meridian Consulting Group",
                    "department": "",
                    "location": location.strip() or "Remote (US)",
                    "posted_date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                    "must_haves": must_haves,
                    "nice_to_haves": [line.strip() for line in nice_to_haves_raw.splitlines() if line.strip()],
                    "description": description.strip(),
                }
                jds_current.append(new_jd)
                save_jds(jds_current)
                load_data.clear()
                st.success(f'Created "{new_jd["title"]}" — add candidates and run the pipeline to start scoring it.')
                go("requirements")

    with voice_tab:
        st.caption("Speak the role's requirements instead of typing them out.")
        st.button("🎙️ Start voice intake", disabled=True, key="voice_intake_disabled")
        st.caption("Coming soon — a recruiter will be able to describe a role out loud and have it "
                   "transcribed and structured into requirements automatically.")


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

if st.session_state.view == "requirements":
    view_requirements()
elif st.session_state.view == "candidates":
    view_candidates()
elif st.session_state.view == "profile":
    view_profile()
elif st.session_state.view == "new_requirement":
    view_new_requirement()
