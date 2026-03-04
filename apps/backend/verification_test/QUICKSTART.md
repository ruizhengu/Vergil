# Quick Start Guide - Verification Tests

All test files are now organized in the `verification_test/` directory!

## Running Tests

Navigate to the `apps/backend/verification_test` directory and run:

### Run All Tests
```bash
cd apps/backend/verification_test
python test_verification_local.py      # Basic unit tests (~30 sec)
python test_verification_advanced.py   # Comprehensive tests (~1 min)
```

### Run Individual Tests
```bash
# Diagnose specific failures
python diagnose_failures.py

# Test address validation
python test_address_fix.py

# Check address length
python check_address_length.py
```

### Run All at Once (Master Script)
```bash
python run_all_tests.py              # Run all tests
python run_all_tests.py local        # Run only local tests
python run_all_tests.py advanced     # Run only advanced tests
```

## File Structure

```
apps/backend/
├── verification_test/           (New folder for all tests)
│   ├── README.md               (Detailed documentation)
│   ├── config.py               (Path configuration)
│   ├── run_all_tests.py        (Master test runner)
│   ├── test_verification_local.py       (6 test suites)
│   ├── test_verification_advanced.py    (32 test cases)
│   ├── diagnose_failures.py             (Failure diagnosis)
│   ├── test_address_fix.py              (Address validation)
│   └── check_address_length.py          (Length check utility)
├── verification/               (Core verification modules)
│   ├── guardrails.py
│   └── smt_logic.py
├── models/
│   └── agent_responses.py      (Contains FinancialAction model)
└── ... (other backend files)
```

## Expected Results

### test_verification_local.py
- **Expected:** 6 test suites all passing
- **Time:** ~30 seconds

### test_verification_advanced.py
- **Expected:** 32/32 tests passing (100%)
- **Output:** Comprehensive score report
- **Time:** ~1 minute

## Test Scores Reference

| Score | Status | Action |
|-------|--------|--------|
| 100% | Excellent | Ready for production |
| 90-99% | Good | Minor edge cases only |
| 80-89% | Fair | Fix before production |
| 70-79% | Poor | Needs improvements |
| <70% | Critical | Major issues |

## Troubleshooting

### ImportError: No module named 'verification'
- Make sure you're running the script from `apps/backend/verification_test` directory
- Or run `python -c "from config import setup_paths; setup_paths()"` first

### Z3 module not found
```bash
pip install z3-solver
```

### Python-dotenv not installed
```bash
pip install python-dotenv
```

### Address validation failing
- Run `python test_address_fix.py` to diagnose
- Addresses must be 42 characters: `0x` + 40 hex chars
- Check for typos in address format

## Next Steps

1. **First time:** Run `python test_verification_local.py` (quick validation)
2. **Full validation:** Run `python test_verification_advanced.py` (comprehensive)
3. **If any fail:** Run `python diagnose_failures.py` for details
4. **Success:** Score ≥90% → Ready for integration testing

## File Summary

| File | Purpose | Time | Tests |
|------|---------|------|-------|
| test_verification_local.py | Basic unit tests | 30s | 6 suites |
| test_verification_advanced.py | Comprehensive tests | 60s | 32 cases |
| diagnose_failures.py | Failure diagnosis | 30s | Detail view |
| test_address_fix.py | Address validation | 5s | 3 cases |
| check_address_length.py | Length check | 1s | Utility |

**Total comprehensive test run:** ~2 minutes for full validation
