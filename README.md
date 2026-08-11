# TrustHire Intelligence

AI-powered hiring intelligence for a consulting firm drowning in exaggerated resumes. Given a job description and a batch of candidate resumes, three specialized agents independently flag fraud, score fit, and infer behavioral traits — every output carrying evidence and a confidence score, not just a number.

This is the working MVP for a larger designed system (full architecture, diagrams, and technology rationale live one level up in `../../architecture/` and `../../presentations/`). This README documents what's actually built and what's intentionally deferred — see [Scope](#scope) below.

## What it does

Given `data/jd.json` (one job description) and `data/candidates.json` (a batch of resumes):

1. **Resume Authenticity & Fraud Detection** — flags timeline inconsistencies, tenure/skill implausibility, title inflation, and keyword-stuffed/templated resumes. Explicitly instructed *not* to penalize legitimate, stated reasons for job changes or gaps (layoffs, restructuring, acquisitions).
2. **JD-Fit & Suitability Scoring** — scores each candidate against the specific job's must-haves and nice-to-haves, citing which requirements are met/missing and why.
3. **Behavioral Trait Intelligence** — infers leadership and loyalty as evidence-based proxies, with the same bias-awareness guardrail: no penalty for job changes with a stated legitimate reason.

An orchestrator runs all three per candidate, gates out high-fraud-risk candidates from the main ranking, and produces a ranked shortlist. A Streamlit dashboard surfaces the results with full evidence, plus Accept/Override buttons that log recruiter decisions — the raw input for a confidence-calibration feedback loop (see architecture doc, Section 4.16).

## Setup

```bash
cd hiring-intelligence
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # then paste in your OpenAI API key
```

`.env` is gitignored — your key never leaves your machine via this repo.

## Run it

```bash
# Score all candidates and print a ranked shortlist to the console
python -m src.run_pipeline

# View it in the dashboard
streamlit run src/dashboard.py
```

`run_pipeline.py` saves full results to `output/pipeline_results.json`. The dashboard reads from that file, so run the pipeline at least once before launching it.

## Project structure

```
hiring-intelligence/
├── data/
│   ├── jd.json              # the role being hired for
│   └── candidates.json      # 15 sample resumes (5 deliberately fraudulent)
├── src/
│   ├── contract.py          # shared 5-field output schema every agent returns
│   ├── config.py            # model tiering, pricing, reference date
│   ├── agents/
│   │   ├── base.py          # shared call/retry/validation logic
│   │   ├── fraud_detection.py
│   │   ├── jd_fit.py
│   │   └── behavioral_traits.py
│   ├── run_pipeline.py      # orchestrator: runs all 3 agents, ranks, saves
│   └── dashboard.py         # Streamlit UI
└── output/                  # generated results (gitignored)
```

## The shared output contract

Every agent returns the same five fields, enforced by a Pydantic schema (`src/contract.py`):

| Field | What it is |
|---|---|
| `recommendation` | Specific, actionable — not a generic observation |
| `evidence` | The concrete resume text that supports the recommendation |
| `confidence_score` | 0–1, calibrated per-candidate, not defaulted |
| `cost_of_insight` | Tokens in/out, model used, estimated USD cost |
| `alternative` | A cheaper/faster option and its trade-off |

An insight without evidence or confidence is a guess in a nicer font — this contract is the whole point.

## Two real bugs found and fixed during development

Worth documenting because both were caught by treating agent output skeptically instead of trusting a clean run:

1. **No date anchor.** The model had no way to know "today's date," so it defaulted to something near its training cutoff and flagged 6 genuine candidates' "Present" tenure as mathematically impossible. Fixed by passing an explicit reference date into every prompt that does date math.
2. **Weak keyword-stuffing signal.** Two deliberately templated/buzzword-only resumes were confidently (95%) cleared as "Advance normally" — a clean timeline talked the model out of the content signal. Fixed by making the absence of any concrete metric or named system across an entire resume sufficient for at least medium risk on its own.

A related arithmetic gap also showed up in JD-fit scoring — "N+ years experience" wasn't being summed across multiple roles, undercounting a legitimate candidate's total tenure. Fixed the same way: made the arithmetic an explicit instruction instead of an assumption.

## Sample data

`data/candidates.json` has 15 candidates, deliberately mixed:
- **5 fraudulent**, covering distinct fraud patterns: title inflation, overlapping employment, keyword-stuffed templates (two candidates share near-identical text, submitted via the same staffing agency), and tenure/skill implausibility.
- **10 genuine**, including two built specifically to test the bias-awareness guardrail: one candidate who changed jobs three times in four years for stated legitimate reasons (layoffs, funding falling through), and one recently laid off in a company-wide reduction. Neither is penalized on loyalty in practice — verified, not assumed.

## Cost

~$0.20 per full run (15 candidates × 3 agents, `gpt-4o`). Model tier is configurable via `.env` (`LARGE_MODEL`/`SMALL_MODEL`) — the two lighter-weight agents in the full design (source-channel stats, pipeline health, not yet built) are scoped to run on a small model per the cost-tiering principle in the architecture doc.

## Scope

**Built:** the 3 core insight agents above, the shared contract, fraud-gated ranking, and the dashboard.

**Deferred** (designed, documented, not implemented in this MVP — see the architecture doc for the full design): voice/text/document-upload intake, JD generation & publishing, the public resume-upload portal, the Source Channel Quality and Pipeline Health agents, the Evaluation/Routing/Optimization agents as separate components, Circuit Breaker enforcement (a retry cap is implemented per-agent-call; full cost-ceiling enforcement is not), n8n orchestration (this MVP orchestrates directly in Python).

This is a deliberate scope cut to get a working, demoable system built in the time available — not an oversight. The full architecture remains the intended design.
