"""
Diagnostic script to identify exact failures in adversarial testing
"""

import sys
import os
from pathlib import Path

# Load .env file
try:
    from dotenv import load_dotenv
    env_path = Path(__file__).parent.parent.parent.parent / ".env"
    load_dotenv(env_path)
except ImportError:
    pass

# Setup path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from verification.guardrails import (
    validate_financial_action_payload,
    FinancialActionValidationError
)

print("=" * 80)
print("ADVERSARIAL TEST FAILURE DIAGNOSIS")
print("=" * 80)

# These are the 10 adversarial test cases
adversarial_cases = [
    {
        "name": "Extreme decimal precision (5.0000001 ETH)",
        "payload": {
            "amount": 5.0000001,
            "asset": "ETH",
            "target_address": "0x742d35Cc6abC5A2C7B8C1C3d3F0F8E2B91d4b3eF"
        },
        "should_block": True,
    },
    {
        "name": "Very small amount (0.000001 ETH)",
        "payload": {
            "amount": 0.000001,
            "asset": "ETH",
            "target_address": "0x742d35Cc6abC5A2C7B8C1C3d3F0F8E2B91d4b3eF"
        },
        "should_block": False,
    },
    {
        "name": "Checksum address (mixed case)",
        "payload": {
            "amount": 1.0,
            "asset": "ETH",
            "target_address": "0x742D35cc6634C0532925a3b844Bc9c7595f5421"
        },
        "should_block": False,
    },
    {
        "name": "Lowercase address",
        "payload": {
            "amount": 1.0,
            "asset": "ETH",
            "target_address": "0x742d35cc6634c0532925a3b844bc9c7595f5421"
        },
        "should_block": False,
    },
    {
        "name": "Missing 0x prefix",
        "payload": {
            "amount": 1.0,
            "asset": "ETH",
            "target_address": "742d35Cc6abC5A2C7B8C1C3d3F0F8E2B91d4b3eF"
        },
        "should_block": True,
    },
    {
        "name": "Wrong address length (37 chars instead of 42)",
        "payload": {
            "amount": 1.0,
            "asset": "ETH",
            "target_address": "0x742d35Cc6abC5A2C7B8C1C3d3F0F8E2B91d4b3"
        },
        "should_block": True,
    },
    {
        "name": "Asset case sensitivity (eth lowercase)",
        "payload": {
            "amount": 1.0,
            "asset": "eth",
            "target_address": "0x742d35Cc6abC5A2C7B8C1C3d3F0F8E2B91d4b3eF"
        },
        "should_block": True,
    },
    {
        "name": "Typo in asset (EHTH instead of ETH)",
        "payload": {
            "amount": 1.0,
            "asset": "EHTH",
            "target_address": "0x742d35Cc6abC5A2C7B8C1C3d3F0F8E2B91d4b3eF"
        },
        "should_block": True,
    },
    {
        "name": "Scientific notation (1e-6 ETH)",
        "payload": {
            "amount": 1e-6,
            "asset": "ETH",
            "target_address": "0x742d35Cc6abC5A2C7B8C1C3d3F0F8E2B91d4b3eF"
        },
        "should_block": False,
    },
    {
        "name": "Maximum boundary + epsilon",
        "payload": {
            "amount": 5.0 + 1e-10,
            "asset": "ETH",
            "target_address": "0x742d35Cc6abC5A2C7B8C1C3d3F0F8E2B91d4b3eF"
        },
        "should_block": True,
    }
]

print("\nRunning each test individually:\n")

failures = []
for i, test in enumerate(adversarial_cases, 1):
    print(f"[Test {i}] {test['name']}")
    print(f"  Payload: {test['payload']}")
    print(f"  Expected: {'BLOCK' if test['should_block'] else 'ALLOW'}")
    
    try:
        result = validate_financial_action_payload(test['payload'])
        actual_result = "ALLOW"
        print(f"  Actual:   {actual_result}")
        
        if test['should_block']:
            print(f"  Status:   [FAIL] - Should block but allowed")
            print(f"  Result:   {result}")
            failures.append((i, test['name'], f"Should block but allowed: {result}"))
        else:
            print(f"  Status:   [PASS] - Correctly allowed")
            
    except FinancialActionValidationError as e:
        actual_result = "BLOCK"
        print(f"  Actual:   {actual_result}")
        print(f"  Error:    {e.payload.message}")
        if e.payload.details:
            print(f"  Details:  {e.payload.details[0] if e.payload.details else 'N/A'}")
        
        if test['should_block']:
            print(f"  Status:   [PASS] - Correctly blocked")
        else:
            print(f"  Status:   [FAIL] - Should allow but blocked")
            msg = e.payload.details[0].get('msg', str(e.payload.message)) if e.payload.details else e.payload.message
            failures.append((i, test['name'], msg))
    
    except Exception as e:
        print(f"  Actual:   ERROR")
        print(f"  Error:    {type(e).__name__}: {e}")
        print(f"  Status:   [FAIL] - Unexpected error")
        failures.append((i, test['name'], f"{type(e).__name__}: {e}"))
    
    print()

# Summary
print("=" * 80)
print("FAILURE SUMMARY")
print("=" * 80)

if failures:
    print(f"\nFound {len(failures)} failures:\n")
    for test_num, test_name, reason in failures:
        print(f"  Test {test_num}: {test_name}")
        print(f"    Reason: {reason}\n")
else:
    print("\nNo failures found!")

print("=" * 80)
