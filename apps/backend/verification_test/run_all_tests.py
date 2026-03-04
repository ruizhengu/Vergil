"""
Main test runner - Execute all verification tests from this directory

Usage:
    python run_all_tests.py
    python run_all_tests.py local
    python run_all_tests.py advanced
    python run_all_tests.py diagnose
"""

import sys
import subprocess
from pathlib import Path

# Setup paths
from config import setup_paths
setup_paths()

def run_test(test_name):
    """Run a specific test file"""
    tests_dir = Path(__file__).parent
    if test_name in ["verification_local", "verification_advanced"]:
        test_file = tests_dir / f"test_{test_name}.py"
    else:
        test_file = tests_dir / f"{test_name}.py"
    
    if not test_file.exists():
        print(f"❌ Test file not found: {test_file}")
        return False
    
    print(f"\n{'='*80}")
    print(f"Running: {test_file.name}")
    print(f"{'='*80}\n")
    
    try:
        result = subprocess.run([sys.executable, str(test_file)], check=False)
        return result.returncode == 0
    except Exception as e:
        print(f"❌ Error running test: {e}")
        return False

def main():
    """Run tests based on command line arguments"""
    if len(sys.argv) < 2:
        # Run all tests
        tests = ["verification_local", "verification_advanced"]
    else:
        test_arg = sys.argv[1].lower()
        if test_arg == "all":
            tests = ["verification_local", "verification_advanced"]
        elif test_arg in ["local", "advanced", "quick_api", "rate_limit_compliant"]:
            if test_arg in ["local", "advanced"]:
                tests = [f"verification_{test_arg}"]
            else:
                tests = [test_arg]
        else:
            print(f"Unknown test: {test_arg}")
            print("Available tests: local, advanced, quick_api, rate_limit_compliant, all")
            return 1
    
    results = {}
    for test in tests:
        results[test] = run_test(test)
    
    # Summary
    print(f"\n{'='*80}")
    print("TEST SUMMARY")
    print(f"{'='*80}\n")
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for test, result in results.items():
        status = "[PASS]" if result else "[FAIL]"
        print(f"{status} {test}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    return 0 if passed == total else 1

if __name__ == "__main__":
    sys.exit(main())
