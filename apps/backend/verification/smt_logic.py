import json
import os
import re
from typing import Any, Dict, List, Optional
from pathlib import Path

from dotenv import load_dotenv
import requests
from z3 import And, Bool, BoolVal, Or, Real, RealVal, Solver, String, StringVal, sat

from models.agent_responses import FinancialAction, StructuredValidationError, build_validation_error, SMTState

env_path = Path(__file__).parent.parent.parent.parent / ".env"
load_dotenv(env_path)


PREDEFINED_REQUIREMENTS: List[str] = [
    "amount must be > 0",
    "amount must be <= 5.0 ETH",
    "asset must be one of ETH, USDC, WETH",
    "target_address must be a valid Ethereum address",
]


class SMTPreparationError(Exception):
    def __init__(self, payload: StructuredValidationError):
        self.payload = payload
        super().__init__(payload.message)


def _extract_contract_facts(contract_source: str) -> Dict[str, Any]:
    source = contract_source or ""
    function_names = re.findall(r"function\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(", source)
    has_transfer_fn = "transfer" in function_names
    has_only_owner = bool(re.search(r"\bonlyOwner\b", source))
    has_require_checks = "require(" in source
    return {
        "functions": function_names,
        "has_transfer_function": has_transfer_fn,
        "has_only_owner_modifier": has_only_owner,
        "has_require_checks": has_require_checks,
    }


def _default_constraint_bundle(action: FinancialAction, contract_facts: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "pre_condition": [
            {"left": "amount", "op": ">", "right": 0.0},
            {"left": "amount", "op": "<=", "right": 5.0},
            {"left": "asset", "op": "in", "right": ["ETH", "USDC", "WETH"]},
            {"left": "target_address_valid", "op": "==", "right": True},
        ],
        "post_condition": [
            {"left": "transfer_requested", "op": "==", "right": True},
            {
                "left": "contract.has_require_checks",
                "op": "==",
                "right": contract_facts.get("has_require_checks", False),
            },
            {
                "left": "contract.has_transfer_function",
                "op": "==",
                "right": contract_facts.get("has_transfer_function", False),
            },
        ],
        "sources": {
            "user_intent": "parsed-fallback",
            "predefined_requirements": PREDEFINED_REQUIREMENTS,
        },
        "tokens_used": 0,
    }


def _extract_constraints_with_llm(
    user_intent: str,
    predefined_requirements: List[str],
    action: FinancialAction,
    contract_facts: Dict[str, Any],
) -> Dict[str, Any]:
    api_key = os.getenv("OPENAI_API_KEY")
    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    if not api_key:
        result = _default_constraint_bundle(action, contract_facts)
        result["llm_used"] = False
        result["model"] = None
        result["llm_reason"] = "No OPENAI_API_KEY found"
        return result

    prompt = {
        "user_intent": user_intent,
        "predefined_requirements": predefined_requirements,
        "financial_action": action.model_dump(),
        "contract_facts": contract_facts,
        "output_schema": {
            "pre_condition": [{"left": "field", "op": "<=|>=|==|in|>", "right": "value"}],
            "post_condition": [{"left": "field", "op": "<=|>=|==|in|>", "right": "value"}],
        },
    }

    try:
        response = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "You are an SMT constraint extraction engine. "
                            "Return strict JSON only with keys pre_condition and post_condition."
                        ),
                    },
                    {"role": "user", "content": json.dumps(prompt, ensure_ascii=False)},
                ],
                "temperature": 0,
                "response_format": {"type": "json_object"},
            },
            timeout=20,
        )

        response.raise_for_status()
        payload = response.json()
        content = payload["choices"][0]["message"]["content"]

        tokens_used = 0
        if "usage" in payload:
            tokens_used = payload["usage"].get("total_tokens", 0)

        parsed = json.loads(content)

        if "pre_condition" not in parsed or "post_condition" not in parsed:
            result = _default_constraint_bundle(action, contract_facts)
            result["llm_used"] = False
            result["model"] = model
            result["llm_reason"] = "LLM response missing required fields"
            result["tokens_used"] = tokens_used
            return result

        parsed["llm_used"] = True
        parsed["model"] = model
        parsed["llm_response"] = content
        parsed["tokens_used"] = tokens_used
        parsed["sources"] = {
            "user_intent": user_intent,
            "predefined_requirements": predefined_requirements,
        }
        return parsed

    except requests.exceptions.Timeout:
        result = _default_constraint_bundle(action, contract_facts)
        result["llm_used"] = False
        result["model"] = model
        result["llm_reason"] = "API timeout"
        result["tokens_used"] = 0
        return result
    except requests.exceptions.HTTPError as e:
        result = _default_constraint_bundle(action, contract_facts)
        result["llm_used"] = False
        result["model"] = model
        result["llm_reason"] = f"HTTP Error {e.response.status_code}: {e.response.text[:100]}"
        result["tokens_used"] = 0
        return result
    except Exception as e:
        result = _default_constraint_bundle(action, contract_facts)
        result["llm_used"] = False
        result["model"] = model
        result["llm_reason"] = f"Error: {str(e)}"
        result["tokens_used"] = 0
        return result


def _constraint_to_z3_expr(
    constraint: Dict[str, Any],
    amount_var: Any,
    asset_var: Any,
    target_addr_valid_var: Any,
    transfer_requested_var: Any,
    contract_has_require_var: Any,
    contract_has_transfer_var: Any,
) -> Any:
    left = constraint.get("left")
    op = constraint.get("op")
    right = constraint.get("right")

    if left == "amount":
        right_value = RealVal(str(float(right)))
        if op == ">":
            return amount_var > right_value
        if op == ">=":
            return amount_var >= right_value
        if op == "<":
            return amount_var < right_value
        if op == "<=":
            return amount_var <= right_value
        if op == "==":
            return amount_var == right_value

    if left == "asset":
        if op == "in" and isinstance(right, list):
            return Or(*(asset_var == StringVal(str(v)) for v in right))
        if op == "==":
            return asset_var == StringVal(str(right))

    if left == "target_address_valid" and op == "==":
        return target_addr_valid_var == BoolVal(bool(right))

    if left == "transfer_requested" and op == "==":
        return transfer_requested_var == BoolVal(bool(right))

    if left == "contract.has_require_checks" and op == "==":
        return contract_has_require_var == BoolVal(bool(right))

    if left == "contract.has_transfer_function" and op == "==":
        return contract_has_transfer_var == BoolVal(bool(right))

    return BoolVal(True)


def build_smt_state(action: FinancialAction) -> SMTState:
    pre_condition: Dict[str, Any] = {
        "asset": action.asset,
        "amount_gt_zero": action.amount > 0,
        "amount_le_5_eth": action.amount <= 5.0,
        "target_address_format_valid": True,
    }
    post_condition: Dict[str, Any] = {
        "transfer_requested": True,
        "target_address": action.target_address,
        "asset": action.asset,
        "amount": action.amount,
    }
    return SMTState(pre_condition=pre_condition, post_condition=post_condition, action=action)


def verify_with_smt(
    action: FinancialAction,
    user_intent: str,
    contract_source: Optional[str] = None,
    predefined_requirements: Optional[List[str]] = None,
) -> Dict[str, Any]:
    requirements = predefined_requirements or PREDEFINED_REQUIREMENTS
    contract_facts = _extract_contract_facts(contract_source or "")
    constraint_bundle = _extract_constraints_with_llm(user_intent, requirements, action, contract_facts)
    smt_state = build_smt_state(action)

    amount_var = Real("amount")
    asset_var = String("asset")
    target_addr_valid_var = Bool("target_address_valid")
    transfer_requested_var = Bool("transfer_requested")
    contract_has_require_var = Bool("contract_has_require_checks")
    contract_has_transfer_var = Bool("contract_has_transfer_function")

    solver = Solver()
    solver.add(amount_var == RealVal(str(action.amount)))
    solver.add(asset_var == StringVal(action.asset))
    solver.add(target_addr_valid_var == BoolVal(True))
    solver.add(transfer_requested_var == BoolVal(True))
    solver.add(contract_has_require_var == BoolVal(contract_facts.get("has_require_checks", False)))
    solver.add(contract_has_transfer_var == BoolVal(contract_facts.get("has_transfer_function", False)))

    z3_constraints: List[Any] = []
    for c in constraint_bundle.get("pre_condition", []):
        z3_constraints.append(
            _constraint_to_z3_expr(
                c,
                amount_var,
                asset_var,
                target_addr_valid_var,
                transfer_requested_var,
                contract_has_require_var,
                contract_has_transfer_var,
            )
        )
    for c in constraint_bundle.get("post_condition", []):
        z3_constraints.append(
            _constraint_to_z3_expr(
                c,
                amount_var,
                asset_var,
                target_addr_valid_var,
                transfer_requested_var,
                contract_has_require_var,
                contract_has_transfer_var,
            )
        )

    if z3_constraints:
        solver.add(And(*z3_constraints))

    result = solver.check()
    is_valid = result == sat

    if not is_valid:
        payload = build_validation_error(
            layer="smt_logic_preparation",
            message="SMT verification failed. Transaction was blocked.",
            error=Exception("Z3 solver returned UNSAT"),
        )
        raise SMTPreparationError(payload)

    return {
        "valid": True,
        "smt_state": smt_state.model_dump(),
        "contract_facts": contract_facts,
        "constraints": constraint_bundle,
        "solver_result": str(result),
        "llm_used": constraint_bundle.get("llm_used", False),
        "model": constraint_bundle.get("model"),
        "llm_reason": constraint_bundle.get("llm_reason"),
        "llm_response": constraint_bundle.get("llm_response"),
        "tokens_used": constraint_bundle.get("tokens_used", 0),
    }
