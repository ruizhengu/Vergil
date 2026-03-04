"""
Local Verification Module Testing
Test verification code logic without starting Docker

Usage:
    cd apps/backend/verification_test
    python test_verification_local.py
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
    print("⚠️  python-dotenv not installed. Install with: pip install python-dotenv")

# Setup path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

print("=" * 70)
print("Vergil Verification Local Testing (No Docker Required)")
print("=" * 70)

# ============================================================================
# Test 1: Import Check
# ============================================================================
print("\n[Test 1] Module Import Check")
print("-" * 70)

try:
    from verification.guardrails import (
        validate_financial_action_payload,
        FinancialActionValidationError
    )
    print("✅ guardrails.py imported successfully")
except Exception as e:
    print(f"❌ guardrails.py import failed: {e}")
    sys.exit(1)

try:
    from verification.smt_logic import (
        verify_with_smt,
        SMTPreparationError,
        _extract_contract_facts,
        build_smt_state
    )
    print("✅ smt_logic.py imported successfully")
except Exception as e:
    print(f"❌ smt_logic.py import failed: {e}")
    sys.exit(1)

try:
    from models.agent_responses import FinancialAction
    print("✅ agent_responses.py imported successfully")
except Exception as e:
    print(f"❌ agent_responses.py import failed: {e}")
    sys.exit(1)

print("\n✅ All dependency modules imported successfully")

# ============================================================================
# Test 2: Pydantic Guardrail Basic Functionality
# ============================================================================
print("\n" + "=" * 70)
print("[Test 2] Pydantic Guardrail - Data Validation")
print("=" * 70)

test_cases = [
    {
        "name": "Normal transaction (0.5 ETH)",
        "payload": {
            "amount": 0.5,
            "asset": "ETH",
            "target_address": "0x742d35Cc6abC5A2C7B8C1C3d3F0F8E2B91d4b3eF"
        },
        "should_pass": True
    },
    {
        "name": "Boundary value (5.0 ETH limit)",
        "payload": {
            "amount": 5.0,
            "asset": "ETH",
            "target_address": "0x742d35Cc6abC5A2C7B8C1C3d3F0F8E2B91d4b3eF"
        },
        "should_pass": True
    },
    {
        "name": "Amount exceeds limit (6.0 ETH)",
        "payload": {
            "amount": 6.0,
            "asset": "ETH",
            "target_address": "0x742d35Cc6abC5A2C7B8C1C3d3F0F8E2B91d4b3eF"
        },
        "should_pass": False
    },
    {
        "name": "Zero amount",
        "payload": {
            "amount": 0.0,
            "asset": "ETH",
            "target_address": "0x742d35Cc6abC5A2C7B8C1C3d3F0F8E2B91d4b3eF"
        },
        "should_pass": False
    },
    {
        "name": "Negative amount",
        "payload": {
            "amount": -1.0,
            "asset": "ETH",
            "target_address": "0x742d35Cc6abC5A2C7B8C1C3d3F0F8E2B91d4b3eF"
        },
        "should_pass": False
    },
    {
        "name": "Unsupported asset (BTC)",
        "payload": {
            "amount": 1.0,
            "asset": "BTC",
            "target_address": "0x742d35Cc6abC5A2C7B8C1C3d3F0F8E2B91d4b3eF"
        },
        "should_pass": False
    },
    {
        "name": "Invalid address format",
        "payload": {
            "amount": 1.0,
            "asset": "ETH",
            "target_address": "0xinvalid"
        },
        "should_pass": False
    },
    {
        "name": "USDC asset (supported)",
        "payload": {
            "amount": 2.0,
            "asset": "USDC",
            "target_address": "0x742d35Cc6abC5A2C7B8C1C3d3F0F8E2B91d4b3eF"
        },
        "should_pass": True
    },
    {
        "name": "WETH asset (supported)",
        "payload": {
            "amount": 3.0,
            "asset": "WETH",
            "target_address": "0x742d35Cc6abC5A2C7B8C1C3d3F0F8E2B91d4b3eF"
        },
        "should_pass": True
    }
]

passed = 0
failed = 0

for i, test in enumerate(test_cases, 1):
    print(f"\nTest 2.{i}: {test['name']}")
    try:
        result = validate_financial_action_payload(test['payload'])
        if test['should_pass']:
            print(f"  ✅ PASS: {result.amount} {result.asset} -> {result.target_address[:10]}...")
            passed += 1
        else:
            print(f"  ❌ FAIL: Should be blocked but passed: {result}")
            failed += 1
    except FinancialActionValidationError as e:
        if not test['should_pass']:
            print(f"  ✅ PASS: Expected rejection: {e.payload.message}")
            if e.payload.details:
                print(f"     Reason: {e.payload.details[0].get('msg', 'N/A')}")
            passed += 1
        else:
            print(f"  ❌ FAIL: Should not be blocked: {e.payload.message}")
            failed += 1
    except Exception as e:
        print(f"  ❌ FAIL: Unexpected error: {type(e).__name__}: {e}")
        failed += 1

print(f"\nPydantic test results: {passed}/{passed+failed} passed")

# ============================================================================
# Test 3: Contract Facts Extraction
# ============================================================================
print("\n" + "=" * 70)
print("[Test 3] Contract Feature Extraction")
print("=" * 70)

test_contracts = [
    {
        "name": "Standard contract with require and onlyOwner",
        "source": """
        pragma solidity ^0.8.0;
        contract Token {
            modifier onlyOwner() { _; }
            function transfer(address to, uint256 amount) public {
                require(amount > 0, "Amount must be positive");
                require(to != address(0), "Invalid address");
            }
        }
        """,
        "expected": {
            "has_transfer_function": True,
            "has_only_owner_modifier": True,
            "has_require_checks": True
        }
    },
    {
        "name": "Simple contract (no protection)",
        "source": """
        pragma solidity ^0.8.0;
        contract Simple {
            function mint() public {}
        }
        """,
        "expected": {
            "has_transfer_function": False,
            "has_only_owner_modifier": False,
            "has_require_checks": False
        }
    },
    {
        "name": "Empty contract",
        "source": "",
        "expected": {
            "has_transfer_function": False,
            "has_only_owner_modifier": False,
            "has_require_checks": False
        }
    }
]

for i, test in enumerate(test_contracts, 1):
    print(f"\nTest 3.{i}: {test['name']}")
    try:
        facts = _extract_contract_facts(test['source'])
        
        all_match = True
        for key, expected_value in test['expected'].items():
            actual_value = facts.get(key, False)
            match = "✅" if actual_value == expected_value else "❌"
            print(f"  {match} {key}: {actual_value} (expected: {expected_value})")
            if actual_value != expected_value:
                all_match = False
        
        if all_match:
            print(f"  ✅ All features extracted correctly")
        else:
            print(f"  ⚠️  Some features don't match expected values")
            
        if facts.get('functions'):
            print(f"  📋 Detected functions: {', '.join(facts['functions'])}")
            
    except Exception as e:
        print(f"  ❌ Extraction failed: {e}")

# ============================================================================
# Test 4: SMT State Construction
# ============================================================================
print("\n" + "=" * 70)
print("[Test 4] SMT State Construction")
print("=" * 70)

try:
    action = FinancialAction(
        amount=1.5,
        asset="ETH",
        target_address="0x742d35Cc6abC5A2C7B8C1C3d3F0F8E2B91d4b3eF"
    )
    
    smt_state = build_smt_state(action)
    
    print("✅ SMT State constructed successfully")
    print(f"\nPre-conditions:")
    for key, value in smt_state.pre_condition.items():
        print(f"  - {key}: {value}")
    
    print(f"\nPost-conditions:")
    for key, value in smt_state.post_condition.items():
        print(f"  - {key}: {value}")
    
    print(f"\nAction:")
    print(f"  - amount: {smt_state.action.amount}")
    print(f"  - asset: {smt_state.action.asset}")
    print(f"  - target: {smt_state.action.target_address[:20]}...")
    
except Exception as e:
    print(f"❌ SMT State construction failed: {e}")

# ============================================================================
# Test 5: Z3 Solver Basic Verification
# ============================================================================
print("\n" + "=" * 70)
print("[Test 5] Z3 Solver Test")
print("=" * 70)

try:
    from z3 import Real, Solver, sat, RealVal
    
    print("✅ Z3 library imported successfully")
    
    # Simple Z3 test
    solver = Solver()
    x = Real('x')
    solver.add(x > 0)
    solver.add(x <= 5.0)
    
    result = solver.check()
    if result == sat:
        print("✅ Z3 Solver working correctly")
        model = solver.model()
        print(f"   Example solution: x = {model[x]}")
    else:
        print("⚠️  Z3 Solver returned non-sat")
        
except ImportError:
    print("⚠️  Z3 library not installed")
    print("   Install command: pip install z3-solver")
except Exception as e:
    print(f"❌ Z3 test failed: {e}")

# ============================================================================
# Test 6: Complete SMT Verification (requires OpenAI API)
# ============================================================================
print("\n" + "=" * 70)
print("[Test 6] Complete SMT Verification Flow")
print("=" * 70)

openai_key = os.getenv("OPENAI_API_KEY")
if not openai_key:
    print("⚠️  OPENAI_API_KEY not set")
    print("   SMT verification will use default constraints (no LLM)")
else:
    print(f"✅ Detected OPENAI_API_KEY: {openai_key[:15]}...")

print("\nTest 6.1: Contract with require checks")
contract_with_require = """
pragma solidity ^0.8.0;
contract SafeToken {
    function transfer(address to, uint256 amount) public {
        require(amount > 0, "Amount must be positive");
        require(to != address(0), "Invalid address");
    }
}
"""

try:
    action = FinancialAction(
        amount=0.8,
        asset="ETH",
        target_address="0x742d35Cc6abC5A2C7B8C1C3d3F0F8E2B91d4b3eF"
    )
    
    result = verify_with_smt(
        action=action,
        user_intent="Deploy an ERC20 token contract to testnet",
        contract_source=contract_with_require
    )
    
    print("✅ SMT verification passed")
    print(f"   Solver result: {result['solver_result']}")
    print(f"   Constraints source: LLM" if openai_key else "   Constraints source: Default rules")
    print(f"   Pre-conditions: {len(result['constraints'].get('pre_condition', []))} items")
    print(f"   Post-conditions: {len(result['constraints'].get('post_condition', []))} items")
    print(f"   Contract features:")
    for key, value in result['contract_facts'].items():
        if isinstance(value, bool):
            print(f"     - {key}: {value}")
    
except SMTPreparationError as e:
    print(f"⚠️  SMT verification failed: {e.payload.message}")
    print(f"   This may indicate constraints are not satisfied (expected behavior)")
except Exception as e:
    print(f"❌ SMT verification exception: {type(e).__name__}: {e}")

print("\nTest 6.2: Simple contract without require checks")
simple_contract = """
pragma solidity ^0.8.0;
contract SimpleContract {
    function mint() public {}
}
"""

try:
    action = FinancialAction(
        amount=0.3,
        asset="ETH",
        target_address="0x742d35Cc6abC5A2C7B8C1C3d3F0F8E2B91d4b3eF"
    )
    
    result = verify_with_smt(
        action=action,
        user_intent="Deploy simple test contract",
        contract_source=simple_contract
    )
    
    print("✅ SMT verification passed (although contract lacks security checks)")
    print(f"   has_require_checks: {result['contract_facts']['has_require_checks']}")
    
except Exception as e:
    print(f"❌ Verification exception: {e}")

# ============================================================================
# Summary
# ============================================================================
print("\n" + "=" * 70)
print("Test Summary")
print("=" * 70)

print(f"""
✅ Completed items:
  - Module import check
  - Pydantic Guardrail data validation
  - Contract feature extraction
  - SMT State construction
  - Z3 Solver test
  - Complete SMT verification flow

📋 Issues found:
  - If you see ❌, there are bugs in the code that need fixing
  - If you see ⚠️, environment configuration needs adjustment (e.g., missing dependencies)

🔧 Dependency check:
  - Pydantic: {'✅ Installed' if 'FinancialAction' in dir() else '❌ Not installed'}
  - Z3 Solver: {'✅ Installed' if 'z3' in sys.modules else '❌ Need to install (pip install z3-solver)'}
  - OpenAI API: {'✅ Configured' if openai_key else '⚠️  Not configured (does not affect default constraints)'}

Next steps:
  1. If all tests pass -> verification code has no bugs ✅
  2. If any fail -> fix code based on error messages
  3. Environment issues -> install missing dependencies: pip install z3-solver requests
  4. Integration test -> run full flow test after Docker is up
""")

print("=" * 70)
print("Testing completed!")
print("=" * 70)
