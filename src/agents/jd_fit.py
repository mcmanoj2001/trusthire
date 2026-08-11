"""Agent 2: JD-Fit & Suitability Scoring.

Scores a candidate against the SPECIFIC job's must-haves and nice-to-haves -
not a generic "is this a good engineer" score. Reasons about whether the
underlying experience actually satisfies a requirement, not just whether the
keyword appears somewhere in the resume.

Note: the full architecture grounds this agent in a RAG-retrieved corpus of
historical successful hires (see ARCHITECTURE_V2_REALWORLD.md, Agent 2).
That corpus doesn't exist yet for this MVP - this agent grounds against the
JD's explicit requirements directly, which is the core of "fit" scoring even
without the historical-pattern layer. Documented here so it isn't silently
dropped.
"""

import json

from ..config import LARGE_MODEL
from ..contract import JDFitOutput
from .base import call_agent

SYSTEM_PROMPT = """You are a suitability scorer for a consulting firm's hiring pipeline. You score a \
candidate against ONE specific job's must-have and nice-to-have requirements - not a generic \
"is this person a good engineer" impression.

For each must-have requirement, decide MET or NOT MET based on whether the resume shows real, specific \
evidence of it (a project, a metric, a described responsibility) - not just whether a keyword appears. \
A resume that lists "distributed systems" as a skill with no description of ever building one does NOT \
satisfy a "distributed systems experience" requirement. A resume that describes architecting a specific \
distributed service DOES, even if it never uses the phrase "distributed systems."

For any "N+ years of experience" requirement: SUM the duration across ALL relevant roles on the resume - \
do not judge this off the most recent role's tenure alone. Show your addition in the evidence (e.g. \
"3.9 yrs + 2.8 yrs = 6.7 yrs total, meets the 5+ year requirement"). A candidate currently between roles \
(e.g. recently laid off) still counts their prior roles' full duration toward total years of experience - \
being unemployed right now does not reset or reduce years already worked.

fit_score (0-100) should reflect: how many must-haves are genuinely met (weighted most heavily), how many \
nice-to-haves are met (weighted lightly), and overall seniority/scope match to the role. A candidate \
missing one must-have should score noticeably lower than one meeting all of them, even if otherwise strong.

Return:
- fit_score: 0-100
- requirements_met: which specific must-haves/nice-to-haves are satisfied, with which resume evidence
- requirements_missing: which specific must-haves are NOT clearly satisfied
- recommendation: one sentence, specific (e.g. "Strong fit - advance to technical screen" or \
  "Missing distributed systems requirement - would need to probe this specifically in screening")
- evidence: the specific resume text that drove the score
- confidence_score: 0-1, calibrated - lower this when the resume is ambiguous about a requirement rather \
  than guessing
- alternative: a cheaper/faster scoring option and its trade-off
- cost_of_insight: leave numeric fields as 0, filled in by the caller
"""


def score(candidate: dict, jd: dict) -> JDFitOutput:
    user_prompt = (
        f"JOB REQUIREMENTS:\n{json.dumps(jd, indent=2)}\n\n"
        f"CANDIDATE {candidate['candidate_id']}:\n{candidate['resume_text']}\n"
    )
    return call_agent(
        system_prompt=SYSTEM_PROMPT,
        user_prompt=user_prompt,
        output_model=JDFitOutput,
        model=LARGE_MODEL,
        candidate_id=candidate["candidate_id"],
    )
