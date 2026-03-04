# Verification System Test Suite

This directory contains comprehensive tests for the Vergil verification system, including Pydantic validation and SMT solver verification.

## Test Files

### 1. `test_verification_local.py`
Basic unit tests for verification components
- Module import checks
- Pydantic guardrail validation (9 test cases)
- Contract feature extraction
- SMT state construction
- Z3 solver functionality
- Complete SMT verification flow

**Usage:**
```bash
cd apps/backend/verification_test
python test_verification_local.py
```

### 2. `test_verification_advanced.py`
Comprehensive testing with adversarial cases and edge cases
- **Test Suite 1:** Adversarial testing (bypass attempts) - 10 test cases
- **Test Suite 2:** Contract analysis robustness - 6 complex contracts
- **Test Suite 3:** Real-world scenarios - 4 practical use cases
- **Test Suite 4:** Constraint satisfaction analysis - 12 constraint tests

**Usage:**
```bash
cd apps/backend/verification_test
python test_verification_advanced.py
```

**Expected Output:** 32/32 tests passed (100% effectiveness)

### 3. `diagnose_failures.py`
Diagnostic tool to identify specific test failures
Shows:
- Each test's input payload
- Expected vs actual results
- Detailed error messages
- Failure reason analysis

**Usage:**
```bash
cd apps/backend/verification_test
python diagnose_failures.py
```

### 4. `test_address_fix.py`
Quick test to verify Ethereum address validation
Tests:
- Checksum addresses (EIP-55)
- Lowercase addresses
- Uppercase addresses

**Usage:**
```bash
cd apps/backend/verification_test
python test_address_fix.py
```

## Test Results Interpretation

### Score Ranges
- **90-100%:** System is highly effective and production-ready
- **70-90%:** System works but has edge cases - fix before production
- **60-70%:** System needs improvements
- **<60%:** Major security review required

### Common Issues and Fixes

#### Address Validation Failures
- Addresses must be exactly 42 characters: `0x` + 40 hex characters
- Supports full lowercase, full uppercase, and EIP-55 checksum (mixed case)
- Cannot be used: `0x` + 39 chars, or without `0x` prefix

#### Pydantic Validation Failures
- Amount must be: `0 < amount ≤ 5.0` ETH
- Assets must be: `ETH`, `USDC`, or `WETH` (case-sensitive)
- Address format must be valid Ethereum address

#### SMT Solver Issues
- Requires Z3: `pip install z3-solver`
- Requires OpenAI API key (optional, uses default constraints if not set)

## Prerequisites

```bash
pip install python-dotenv z3-solver pydantic
```

Optional for full SMT verification with LLM:
```bash
pip install openai
```

## Dependencies

- Python 3.8+
- pydantic (Validation)
- z3-solver (Constraint solving)
- python-dotenv (.env file loading)
- openai (Optional, for LLM-based constraints generation)

## Running All Tests

```bash
# In apps/backend/verification_test directory
python test_verification_local.py
python test_verification_advanced.py
```

Expected combined output:
- Local tests: 6 test suites
- Advanced tests: 4 test suites with 32 total test cases
- Overall effectiveness: 93-100%

## Troubleshooting

### Module Import Errors
```bash
cd apps/backend
python -c "from verification.guardrails import validate_financial_action_payload; print('OK')"
```

### Address Validation Errors
Use `test_address_fix.py` to diagnose address format issues

### SMT Solver Issues
```bash
pip install z3-solver --upgrade
python -c "from z3 import *; print('Z3 OK')"
```

## Next Steps

1. **If all tests pass (>90%):** System is ready for integration testing
2. **If some tests fail:** Run `diagnose_failures.py` to identify issues
3. **For production deployment:** Ensure 100% test pass rate
