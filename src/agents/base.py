"""Base call helper shared by every insight agent.

Enforces two of the design principles from the architecture doc even in this
scoped-down build:
  - Guardrail: Output validation - a malformed/incomplete response never
    reaches the caller; it's retried or raised, never silently passed through.
  - Circuit-breaker-lite - a hard retry cap per candidate, so one ambiguous
    case can never spin forever or run away on cost.
"""

from pydantic import ValidationError
from ..config import client, PRICES, MAX_RETRIES_PER_AGENT_CALL


class AgentCallFailed(Exception):
    def __init__(self, candidate_id: str, attempts: int, last_error: str):
        self.candidate_id = candidate_id
        self.attempts = attempts
        self.last_error = last_error
        super().__init__(f"[{candidate_id}] failed after {attempts} attempts: {last_error}")


def _estimate_cost(model: str, tokens_in: int, tokens_out: int) -> float:
    price = PRICES.get(model, {"in": 0.0, "out": 0.0})
    return round((tokens_in / 1000) * price["in"] + (tokens_out / 1000) * price["out"], 6)


def call_agent(system_prompt: str, user_prompt: str, output_model, model: str, candidate_id: str):
    """Call the model, parse+validate against output_model, retry on failure, hard-stop after MAX_RETRIES_PER_AGENT_CALL."""
    last_error = None
    for attempt in range(1, MAX_RETRIES_PER_AGENT_CALL + 2):  # e.g. 2 retries => 3 total attempts
        try:
            completion = client.beta.chat.completions.parse(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                response_format=output_model,
                temperature=0.2,
            )
            parsed = completion.choices[0].message.parsed
            if parsed is None:
                raise ValueError("model refused or returned no parsed content")

            usage = completion.usage
            parsed.cost_of_insight.tokens_in = usage.prompt_tokens
            parsed.cost_of_insight.tokens_out = usage.completion_tokens
            parsed.cost_of_insight.model = model
            parsed.cost_of_insight.est_usd = _estimate_cost(model, usage.prompt_tokens, usage.completion_tokens)
            parsed.candidate_id = candidate_id
            return parsed

        except (ValidationError, ValueError) as e:
            last_error = str(e)
            print(f"  [retry {attempt}/{MAX_RETRIES_PER_AGENT_CALL + 1}] {candidate_id}: {last_error[:200]}")

    raise AgentCallFailed(candidate_id, MAX_RETRIES_PER_AGENT_CALL + 1, last_error or "unknown error")
