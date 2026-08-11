"""Shared output contract every insight agent must return.

An insight without evidence or confidence is a guess in a nicer font.
"""

from pydantic import BaseModel, Field


class CostOfInsight(BaseModel):
    tokens_in: int
    tokens_out: int
    model: str
    est_usd: float


class AgentOutput(BaseModel):
    candidate_id: str
    recommendation: str = Field(..., description="Specific, actionable — not a generic observation")
    evidence: list[str] = Field(..., description="Concrete data points from the input that support the recommendation")
    confidence_score: float = Field(..., ge=0.0, le=1.0)
    cost_of_insight: CostOfInsight
    alternative: str = Field(..., description="A cheaper/faster option, with a trade-off note")


class FraudDetectionOutput(AgentOutput):
    fraud_risk: str = Field(..., description="one of: low, medium, high")
    fraud_flags: list[str] = Field(default_factory=list)


class JDFitOutput(AgentOutput):
    fit_score: int = Field(..., ge=0, le=100)
    requirements_met: list[str] = Field(default_factory=list)
    requirements_missing: list[str] = Field(default_factory=list)


class BehavioralTraitOutput(AgentOutput):
    leadership_score: float = Field(..., ge=0.0, le=1.0)
    loyalty_score: float = Field(..., ge=0.0, le=1.0)
    caveats: list[str] = Field(
        default_factory=list,
        description="Explicit limits on what this proxy score can and can't tell you",
    )
