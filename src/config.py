import os
from pathlib import Path
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
OUTPUT_DIR = ROOT / "output"
OUTPUT_DIR.mkdir(exist_ok=True)

LARGE_MODEL = os.environ.get("LARGE_MODEL", "gpt-4o")
SMALL_MODEL = os.environ.get("SMALL_MODEL", "gpt-4o-mini")

# Explicit date anchor for every agent's timeline/tenure math. Models have no reliable
# notion of "today" on their own (they default to something near their training cutoff),
# so any agent reasoning about dates MUST be told the current date - never left to infer it.
REFERENCE_DATE = os.environ.get("REFERENCE_DATE", "2026-07-25")

# Rough per-1K-token prices (USD) for cost_of_insight estimates. Adjust to your actual account pricing.
PRICES = {
    LARGE_MODEL: {"in": 0.0025, "out": 0.010},
    SMALL_MODEL: {"in": 0.00015, "out": 0.0006},
}

client = OpenAI()

MAX_RETRIES_PER_AGENT_CALL = 2  # circuit-breaker-lite: never let one candidate spin forever
