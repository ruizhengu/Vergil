from typing import Optional, List, Literal, Dict
from pydantic import BaseModel, Field


class IntentClassificationResponse(BaseModel):
    """Structured response from the intent classification node."""

    intent: Literal["generic_erc20", "generic_erc721", "generic_erc1155", "custom", "conversational"] = Field(
        description="Classified intent of the user's request"
    )
    reasoning: str = Field(
        description="Explanation of why this intent was chosen"
    )
    extracted_params: Optional[Dict[str, str]] = Field(
        default=None,
        description="Parameters extracted from the user message (name, symbol, supply, features, etc.)"
    )
    confidence: float = Field(
        ge=0.0, le=1.0,
        description="Confidence level in the classification (0-1)"
    )


class ContractGenerationResult(BaseModel):
    """Final output from the generate contract agent."""

    status: Literal["completed", "failed", "needs_input"] = Field(
        description="Overall status of the contract generation"
    )
    solidity_code: Optional[str] = Field(
        default=None,
        description="Generated Solidity source code"
    )
    contract_type: Optional[str] = Field(
        default=None,
        description="Type of contract: erc20, erc721, or custom"
    )
    contract_name: Optional[str] = Field(
        default=None,
        description="Name of the generated contract"
    )
    summary: str = Field(
        description="Human-readable summary of what was generated or what went wrong"
    )
    next_actions: Optional[List[str]] = Field(
        default=None,
        description="Suggested next actions (compile, verify, deploy)"
    )
    follow_up_questions: Optional[List[str]] = Field(
        default=None,
        description="Questions to ask the user if status is needs_input"
    )
