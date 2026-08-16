# Sample Output

`pipeline_results.json` is a real, unedited output from `python -m src.run_pipeline`, checked in so it can be inspected without an API key. It reflects both bug fixes described in the main README — 5 candidates correctly flagged as fraudulent (`CAND_002`, `CAND_004`, `CAND_007`, `CAND_010`, `CAND_013`), the other 10 correctly ranked, including both bias-awareness test cases scoring full loyalty despite job changes/gaps with stated legitimate reasons.

This is a snapshot, not live data — running the pipeline again may produce slightly different scores/wording since the model isn't deterministic, though the fraud verdicts have been stable across every re-run during development. Live output goes to `../output/` (gitignored).
