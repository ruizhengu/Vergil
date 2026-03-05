from typing import Any, Dict
from pydantic import ValidationError as PydanticValidationError

from models.agent_responses import FinancialAction, StructuredValidationError, build_validation_error


class FinancialActionValidationError(Exception):
    def __init__(self, payload: StructuredValidationError):
        self.payload = payload
        super().__init__(payload.message)


def validate_financial_action_payload(payload: Dict[str, Any]) -> FinancialAction:
    try:
        return FinancialAction.parse_obj(payload)
    except PydanticValidationError as exc:
        validation_error = build_validation_error(
            layer="pydantic_guardrail",
            message="FinancialAction validation failed",
            error=exc,
        )
        raise FinancialActionValidationError(validation_error) from exc
