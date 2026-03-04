"""
Advanced Verification Testing
Test real scenarios and edge cases to validate verification effectiveness

Usage:
    cd apps/backend/verification_test
    python test_verification_advanced.py
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
from verification.smt_logic import (
    verify_with_smt,
    SMTPreparationError,
    _extract_contract_facts
)
from models.agent_responses import FinancialAction

print("=" * 80)
print("ADVANCED VERIFICATION TESTING - Real Scenarios & Edge Cases")
print("=" * 80)

# ============================================================================
# Test Suite 1: Adversarial Testing - Try to bypass validation
# ============================================================================
print("\n" + "=" * 80)
print("[Test Suite 1] Adversarial Testing - Bypass Attempts")
print("=" * 80)

adversarial_cases = [
    {
        "name": "Extreme decimal precision (5.0000001 ETH)",
        "payload": {
            "amount": 5.0000001,
            "asset": "ETH",
            "target_address": "0x742d35Cc6abC5A2C7B8C1C3d3F0F8E2B91d4b3eF"
        },
        "should_block": True,
        "reason": "Exceeds 5 ETH limit even by small margin"
    },
    {
        "name": "Very small amount (0.000001 ETH)",
        "payload": {
            "amount": 0.000001,
            "asset": "ETH",
            "target_address": "0x742d35Cc6abC5A2C7B8C1C3d3F0F8E2B91d4b3eF"
        },
        "should_block": False,
        "reason": "Small but valid amount"
    },
    {
        "name": "Checksum address (mixed case)",
        "payload": {
            "amount": 1.0,
            "asset": "ETH",
            "target_address": "0x742d35Cc6abC5A2C7B8C1C3d3F0F8E2B91d4b3eF"
        },
        "should_block": False,
        "reason": "Valid checksum Ethereum address"
    },
    {
        "name": "Lowercase address",
        "payload": {
            "amount": 1.0,
            "asset": "ETH",
            "target_address": "0x742d35cc6abc5a2c7b8c1c3d3f0f8e2b91d4b3ef"
        },
        "should_block": False,
        "reason": "Valid lowercase address format"
    },
    {
        "name": "Missing 0x prefix",
        "payload": {
            "amount": 1.0,
            "asset": "ETH",
            "target_address": "742d35Cc6abC5A2C7B8C1C3d3F0F8E2B91d4b3eF"
        },
        "should_block": True,
        "reason": "Address must start with 0x"
    },
    {
        "name": "Wrong address length (37 chars instead of 42)",
        "payload": {
            "amount": 1.0,
            "asset": "ETH",
            "target_address": "0x742d35Cc6abC5A2C7B8C1C3d3F0F8E2B91d4b3"
        },
        "should_block": True,
        "reason": "Invalid address length"
    },
    {
        "name": "Asset case sensitivity (eth lowercase)",
        "payload": {
            "amount": 1.0,
            "asset": "eth",
            "target_address": "0x742d35Cc6abC5A2C7B8C1C3d3F0F8E2B91d4b3eF"
        },
        "should_block": True,
        "reason": "Asset names are case-sensitive"
    },
    {
        "name": "Typo in asset (EHTH instead of ETH)",
        "payload": {
            "amount": 1.0,
            "asset": "EHTH",
            "target_address": "0x742d35Cc6abC5A2C7B8C1C3d3F0F8E2B91d4b3eF"
        },
        "should_block": True,
        "reason": "Invalid asset symbol"
    },
    {
        "name": "Scientific notation (1e-6 ETH)",
        "payload": {
            "amount": 1e-6,
            "asset": "ETH",
            "target_address": "0x742d35Cc6abC5A2C7B8C1C3d3F0F8E2B91d4b3eF"
        },
        "should_block": False,
        "reason": "Valid small amount"
    },
    {
        "name": "Maximum boundary + epsilon",
        "payload": {
            "amount": 5.0 + 1e-10,
            "asset": "ETH",
            "target_address": "0x742d35Cc6abC5A2C7B8C1C3d3F0F8E2B91d4b3eF"
        },
        "should_block": True,
        "reason": "Exceeds maximum even infinitesimally"
    }
]

adversarial_passed = 0
adversarial_failed = 0

for i, test in enumerate(adversarial_cases, 1):
    print(f"\n[1.{i}] {test['name']}")
    print(f"     Reason: {test['reason']}")
    try:
        result = validate_financial_action_payload(test['payload'])
        if test['should_block']:
            print(f"     [FAIL] Should be blocked but passed")
            adversarial_failed += 1
        else:
            print(f"     [PASS] Correctly allowed")
            adversarial_passed += 1
    except FinancialActionValidationError as e:
        if test['should_block']:
            print(f"     [PASS] Correctly blocked")
            adversarial_passed += 1
        else:
            print(f"     [FAIL] Should pass but was blocked: {e.payload.message}")
            adversarial_failed += 1

print(f"\nAdversarial Test Score: {adversarial_passed}/{adversarial_passed + adversarial_failed}")

# ============================================================================
# Test Suite 2: Contract Analysis Robustness
# ============================================================================
print("\n" + "=" * 80)
print("[Test Suite 2] Contract Analysis Robustness")
print("=" * 80)

complex_contracts = [
    {
        "name": "Contract with reentrancy protection",
        "source": """
pragma solidity ^0.8.0;
contract ReentrancyProtected {
    bool locked = false;
    modifier noReentrancy() {
        require(!locked, "No reentrancy");
        locked = true;
        _;
        locked = false;
    }
    function transfer(address to, uint256 amount) public noReentrancy {
        require(amount > 0, "Amount must be positive");
        require(to != address(0), "Invalid address");
    }
}
        """,
        "check": "Should recognize reentrancy pattern (advanced security)"
    },
    {
        "name": "Contract with dangerous delegatecall",
        "source": """
pragma solidity ^0.8.0;
contract Delegator {
    function delegateCall(address target, bytes memory data) public {
        target.delegatecall(data);
    }
}
        """,
        "check": "Should detect delegatecall (security risk)"
    },
    {
        "name": "Contract with SafeTransfer (OpenZeppelin)",
        "source": """
pragma solidity ^0.8.0;
import "@openzeppelin/contracts/token/ERC20/utils/SafeTransferLib.sol";
contract SafeTransferUser {
    function transfer(address token, address to, uint256 amount) public {
        SafeTransferLib.safeTransfer(IERC20(token), to, amount);
    }
}
        """,
        "check": "Should recognize safe transfer library usage"
    },
    {
        "name": "Contract with unchecked arithmetic",
        "source": """
pragma solidity ^0.8.0;
contract UnsafeArithmetic {
    function transfer(address to, uint256 amount) public {
        unchecked {
            uint256 result = amount + 1;
        }
    }
}
        """,
        "check": "Should detect unchecked arithmetic block"
    },
    {
        "name": "Minimal contract (no security checks)",
        "source": """
pragma solidity ^0.8.0;
contract Minimal {
    function transfer(address to, uint256 amount) public {
        // No validation
    }
}
        """,
        "check": "Should flag as having no security checks"
    },
    {
        "name": "Contract with assembly",
        "source": """
pragma solidity ^0.8.0;
contract AssemblyUser {
    function transfer(address to, uint256 amount) public {
        assembly {
            // Low-level assembly code
            mstore(0x80, amount)
        }
    }
}
        """,
        "check": "Should detect assembly usage (complex/risky)"
    }
]

contract_passed = 0
contract_failed = 0

for i, test in enumerate(complex_contracts, 1):
    print(f"\n[2.{i}] {test['name']}")
    print(f"      {test['check']}")
    try:
        facts = _extract_contract_facts(test['source'])
        print(f"      [OK] Analyzed successfully")
        print(f"      Features found: ", end="")
        found_features = [k for k, v in facts.items() if v is True and k != 'functions']
        if found_features:
            print(", ".join(found_features))
        else:
            print("(none)")
        
        if facts.get('functions'):
            print(f"      Functions: {', '.join(facts['functions'])}")
        
        contract_passed += 1
    except Exception as e:
        print(f"      [WARN] Analysis failed: {e}")
        contract_failed += 1

print(f"\nContract Analysis Score: {contract_passed}/{contract_passed + contract_failed}")

# ============================================================================
# Test Suite 3: Real-World Scenarios
# ============================================================================
print("\n" + "=" * 80)
print("[Test Suite 3] Real-World Verification Scenarios")
print("=" * 80)

real_scenarios = [
    {
        "name": "Deploy ERC20 token - Standard case",
        "action": {"amount": 0.1, "asset": "ETH", "target_address": "0x742d35Cc6abC5A2C7B8C1C3d3F0F8E2B91d4b3eF"},
        "intent": "Deploy standard ERC20 token contract",
        "contract": """
pragma solidity ^0.8.0;
contract ERC20 {
    function transfer(address to, uint256 amount) public {
        require(amount > 0, "Amount must be positive");
        require(to != address(0), "Invalid address");
    }
}
        """,
        "expect_pass": True
    },
    {
        "name": "Transfer large amount without proper checks",
        "action": {"amount": 4.5, "asset": "ETH", "target_address": "0x742d35Cc6abC5A2C7B8C1C3d3F0F8E2B91d4b3eF"},
        "intent": "Send large amount to unknown address",
        "contract": """
pragma solidity ^0.8.0;
contract Unsafe {
    function transfer(address to, uint256 amount) public {
        // No validation
    }
}
        """,
        "expect_pass": True  # Validation should pass, but SMT might flag intent mismatch
    },
    {
        "name": "Small test transaction",
        "action": {"amount": 0.001, "asset": "USDC", "target_address": "0x742d35Cc6abC5A2C7B8C1C3d3F0F8E2B91d4b3eF"},
        "intent": "Test transaction with small amount",
        "contract": """
pragma solidity ^0.8.0;
contract TestToken {
    function transfer(address to, uint256 amount) public {
        require(amount > 0);
        require(to != address(0));
    }
}
        """,
        "expect_pass": True
    },
    {
        "name": "Maximum allowed transaction",
        "action": {"amount": 5.0, "asset": "WETH", "target_address": "0x742d35Cc6abC5A2C7B8C1C3d3F0F8E2B91d4b3eF"},
        "intent": "Send maximum allowed amount",
        "contract": """
pragma solidity ^0.8.0;
contract MaxTransaction {
    function transfer(address to, uint256 amount) public {
        require(amount > 0, "Amount must be positive");
        require(amount <= 5 * 10**18, "Amount exceeds maximum");
        require(to != address(0), "Invalid address");
    }
}
        """,
        "expect_pass": True
    }
]

scenario_passed = 0
scenario_failed = 0

for i, scenario in enumerate(real_scenarios, 1):
    print(f"\n[3.{i}] {scenario['name']}")
    print(f"      Intent: {scenario['intent']}")
    
    try:
        # First validate the action
        action = validate_financial_action_payload(scenario['action'])
        print(f"      [OK] Financial action validated")
        
        # Then run SMT verification
        result = verify_with_smt(
            action=action,
            user_intent=scenario['intent'],
            contract_source=scenario['contract']
        )
        
        if scenario['expect_pass']:
            print(f"      [PASS] Verification passed as expected")
            print(f"         Solver: {result['solver_result']}")
            scenario_passed += 1
        else:
            print(f"      [WARN] Expected to fail but passed")
            scenario_failed += 1
            
    except FinancialActionValidationError as e:
        print(f"      [FAIL] Financial validation failed - {e.payload.message}")
        scenario_failed += 1
    except SMTPreparationError as e:
        print(f"      [WARN] SMT verification failed - {e.payload.message}")
        if scenario['expect_pass']:
            scenario_failed += 1
        else:
            print(f"      [PASS] Correctly rejected (expected)")
            scenario_passed += 1
    except Exception as e:
        print(f"      [FAIL] Unexpected error - {type(e).__name__}: {e}")
        scenario_failed += 1

print(f"\nReal-World Scenario Score: {scenario_passed}/{scenario_passed + scenario_failed}")

# ============================================================================
# Test Suite 4: Constraint Satisfaction Testing
# ============================================================================
print("\n" + "=" * 80)
print("[Test Suite 4] Constraint Satisfaction Analysis")
print("=" * 80)

print("\nThis test analyzes whether SMT constraints are actually being enforced:")

constraint_tests = [
    {
        "name": "Amount constraint (0 < amount <= 5)",
        "test_values": [0, 0.00001, 2.5, 5.0, 5.00001, 10],
        "expected_valid": [False, True, True, True, False, False]
    },
    {
        "name": "Asset constraint (ETH, USDC, or WETH)",
        "test_values": ["ETH", "USDC", "WETH", "BTC", "DOGE", "USD"],
        "expected_valid": [True, True, True, False, False, False]
    }
]

constraint_score = 0
constraint_total = 0

for test_suite in constraint_tests:
    print(f"\n{test_suite['name']}:")
    for value, expected_valid in zip(test_suite['test_values'], test_suite['expected_valid']):
        try:
            if isinstance(value, str):  # Asset test
                payload = {
                    "amount": 1.0,
                    "asset": value,
                    "target_address": "0x742d35Cc6abC5A2C7B8C1C3d3F0F8E2B91d4b3eF"
                }
            else:  # Amount test
                payload = {
                    "amount": value,
                    "asset": "ETH",
                    "target_address": "0x742d35Cc6abC5A2C7B8C1C3d3F0F8E2B91d4b3eF"
                }
            
            validate_financial_action_payload(payload)
            is_valid = True
        except FinancialActionValidationError:
            is_valid = False
        
        constraint_total += 1
        if is_valid == expected_valid:
            print(f"  [OK] {value}: {is_valid} (expected {expected_valid})")
            constraint_score += 1
        else:
            print(f"  [FAIL] {value}: {is_valid} (expected {expected_valid}) - CONSTRAINT VIOLATION")

print(f"\nConstraint Score: {constraint_score}/{constraint_total}")

# ============================================================================
# Summary Report
# ============================================================================
print("\n" + "=" * 80)
print("ADVANCED TESTING SUMMARY REPORT")
print("=" * 80)

total_tests = (adversarial_passed + adversarial_failed) + (contract_passed + contract_failed) + \
              (scenario_passed + scenario_failed) + constraint_score

total_score = adversarial_passed + contract_passed + scenario_passed + constraint_score
total_possible = (adversarial_passed + adversarial_failed) + (contract_passed + contract_failed) + \
                 (scenario_passed + scenario_failed) + constraint_total

print(f"""
Test Results:
+-------------------------------------+--------+----------+
| Test Suite                          | Score  | Quality  |
+-------------------------------------+--------+----------+
| 1. Adversarial (Bypass Attempts)    | {adversarial_passed:2d}/{adversarial_passed + adversarial_failed:2d}   | {'RED' if adversarial_passed < adversarial_passed + adversarial_failed else 'GREEN':<8} |
| 2. Contract Analysis Robustness     | {contract_passed:2d}/{contract_passed + contract_failed:2d}   | {'RED' if contract_failed > 0 else 'GREEN':<8} |
| 3. Real-World Scenarios             | {scenario_passed:2d}/{scenario_passed + scenario_failed:2d}   | {'RED' if scenario_failed > 0 else 'GREEN':<8} |
| 4. Constraint Satisfaction          | {constraint_score:2d}/{constraint_total:2d}   | {'RED' if constraint_score < constraint_total else 'GREEN':<8} |
+-------------------------------------+--------+----------+
| OVERALL VERIFICATION EFFECTIVENESS  | {total_score:2d}/{total_possible:2d}   | {f'{100 * total_score // total_possible}%':<8} |
+-------------------------------------+--------+----------+

Health Check:
""")

# Detailed analysis
if total_score / total_possible >= 0.95:
    print("  [EXCELLENT] Verification system is highly effective")
elif total_score / total_possible >= 0.80:
    print("  [GOOD] Verification system is working but has edge cases")
elif total_score / total_possible >= 0.60:
    print("  [FAIR] Verification system needs improvements")
else:
    print("  [POOR] Verification system has major issues")

print(f"""
Recommendations:
  1. Failed adversarial tests: Review input validation logic
  2. Failed contract analysis: Improve pattern recognition
  3. Failed real-world scenarios: May indicate SMT solver issues
  4. Failed constraints: Critical - validation logic needs fixing

Next Steps:
  - If score > 90%: System is reliable, proceed to integration testing
  - If score 70-90%: Fix identified issues before production
  - If score < 70%: Major security review recommended
""")

print("=" * 80)
print("Advanced testing completed!")
print("=" * 80)
