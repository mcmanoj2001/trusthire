# Sample Output

`pipeline_results.json` is a real, unedited output from `python -m src.run_pipeline`, checked in so it can be inspected without an API key. It covers both open requirements:

- **Senior Backend Engineer** (`JOB_001`, 15 candidates) — reflects both bug fixes described in the main README: of the 5 candidates deliberately built to be fraudulent, 4 were flagged high risk and excluded from ranking (`CAND_002`, `CAND_004`, `CAND_010`, `CAND_013`), and 1 (`CAND_007`) was flagged medium risk (kept in the ranking with a visible warning, not a miss). Fraud verdicts have generally been stable across re-runs, but the model isn't deterministic and the high/medium split on any one candidate can shift slightly run to run. The other 10 candidates are correctly ranked, including both bias-awareness test cases scoring full loyalty despite job changes/gaps with stated legitimate reasons.
- **Data Platform Engineer** (`JOB_002`, 8 candidates) — a second role added to exercise the pipeline against a different requirement set; 1 candidate correctly flagged for overlapping employment dates, the rest ranked, including its own bias-awareness test cases (a job-hopper with stated legitimate reasons, and a recent layoff).

This is a snapshot, not live data — running the pipeline again may produce slightly different scores/wording, and occasionally a slightly different high/medium fraud split, since the model isn't deterministic. Live output goes to `../output/` (gitignored).
