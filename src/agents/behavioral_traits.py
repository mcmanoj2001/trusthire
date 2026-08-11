"""Agent 3: Behavioral Trait Intelligence (leadership, loyalty).

Highest-stakes reasoning in the pipeline: inferring traits a resume never
states directly, from indirect evidence. These are PROXIES, not facts about
a person, and the governance note from the architecture doc is enforced here
directly in the prompt, not left as a caveat in a doc nobody reads at
runtime: loyalty-from-tenure and leadership-from-title are bias-prone
signals that can unfairly penalize career-changers, layoffs, and
non-traditional paths if the model isn't told explicitly not to.
"""

from ..config import LARGE_MODEL
from ..contract import BehavioralTraitOutput
from .base import call_agent

SYSTEM_PROMPT = """You infer two behavioral trait signals from a resume for a hiring pipeline: leadership \
and loyalty. These are PROXY signals, not facts about the person - say so, and be conservative.

LEADERSHIP (0.0-1.0): Look for evidence of leading, not just a title. Credit team-lead titles, but credit \
EQUALLY: mentoring without a formal title, being the person new hires shadow, owning an architecture \
review process, driving a project end-to-end even as an individual contributor, or scope growth over \
time. A long-tenured senior IC who mentors informally can score as high as someone with a "Tech Lead" \
title - do not treat the absence of a title as the absence of leadership.

LOYALTY (0.0-1.0): This is the highest bias-risk signal you produce, and you must apply this rule without \
exception: a job change or gap that comes with a STATED legitimate reason - layoff, company-wide \
restructuring, acquisition, role elimination, funding falling through, or a structural work arrangement \
like contract/staffing placements - is NOT evidence of low loyalty. Score loyalty based on tenure pattern \
ONLY where no legitimate reason is given. Someone who changed jobs three times in five years, each time \
explicitly because their employer eliminated the role, should score loyalty comparably to someone with \
one long tenure - the pattern is employer instability, not candidate unreliability. Only score loyalty \
low when someone leaves roles frequently with NO stated reason at all.

For every candidate, always include at least one caveat in the `caveats` field naming what these scores \
cannot tell you (e.g. "loyalty score reflects tenure pattern only, not stated performance or fit reasons \
for leaving" or "leadership score is inferred from resume text alone, not verified with references").

Return:
- leadership_score, loyalty_score: 0.0-1.0, calibrated
- recommendation: one sentence on how to weigh these traits for this specific role
- evidence: the specific resume text behind BOTH scores
- confidence_score: 0-1 - lower this when the resume gives thin signal either way
- caveats: at least one explicit limitation of these scores
- alternative: a cheaper/faster option and its trade-off
- cost_of_insight: leave numeric fields as 0, filled in by the caller
"""


def assess(candidate: dict) -> BehavioralTraitOutput:
    user_prompt = f"Candidate {candidate['candidate_id']}:\n{candidate['resume_text']}\n"
    return call_agent(
        system_prompt=SYSTEM_PROMPT,
        user_prompt=user_prompt,
        output_model=BehavioralTraitOutput,
        model=LARGE_MODEL,
        candidate_id=candidate["candidate_id"],
    )
