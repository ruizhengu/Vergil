"""
Quick test to verify address validation fix
"""

import sys
from pathlib import Path

backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

# Force reimport
if 'models.agent_responses' in sys.modules:
    del sys.modules['models.agent_responses']
if 'verification.guardrails' in sys.modules:
    del sys.modules['verification.guardrails']

from verification.guardrails import validate_financial_action_payload, FinancialActionValidationError

print("Testing address validation fix...\n")

test_cases = [
    ("Checksum address", "0x742d35Cc6abC5A2C7B8C1C3d3F0F8E2B91d4b3eF", True),
    ("Lowercase address", "0x742d35cc6abc5a2c7b8c1c3d3f0f8e2b91d4b3ef", True),
]

for desc, addr, should_pass in test_cases:
    payload = {
        "amount": 1.0,
        "asset": "ETH",
        "target_address": addr
    }
    
    try:
        result = validate_financial_action_payload(payload)
        status = "[PASS]" if should_pass else "[FAIL - should block]"
        print(f"{status} {desc}")
        print(f"  Address: {addr}")
    except FinancialActionValidationError as e:
        status = "[FAIL - should allow]" if should_pass else "[PASS]"
        print(f"{status} {desc}")
        print(f"  Address: {addr}")
        print(f"  Error: {e.payload.message}")
        if e.payload.details:
            print(f"  Details: {e.payload.details[0].get('msg', 'N/A')}")
    print()
