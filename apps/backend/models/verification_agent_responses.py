from typing import Optional, List, Literal
from pydantic import BaseModel, Field


class VerificationResult(BaseModel):
    """Result of contract verification analysis."""

    pass_verification: bool = Field(
        description="Whether the generated contract passes verification checks"
    )
    risk_level: Literal["low", "medium", "high"] = Field(
        description="Overall risk level of the contract"
    )
    issues: List[str] = Field(
        default_factory=list,
        description="List of issues found during verification"
    )
    summary: str = Field(
        description="Summary of the verification analysis"
    )
    original_code: Optional[str] = Field(
        default=None,
        description="The original Solidity code that was verified (pass-through)"
    )
