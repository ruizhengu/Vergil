"""
Verification Test Suite
========================

Comprehensive testing framework for Vergil's verification system.

Modules:
- test_verification_local: Basic unit tests (6 test suites)
- test_verification_advanced: Comprehensive tests (32 test cases, 4 suites)
- diagnose_failures: Diagnostic tool for test failures
- test_address_fix: Quick address validation tests
- check_address_length: Address length utility

Usage:
    >>> from config import setup_paths
    >>> setup_paths()
    >>> import test_verification_local
    >>> import test_verification_advanced

Or run directly:
    cd apps/backend/verification_test
    python test_verification_local.py
    python test_verification_advanced.py
    python run_all_tests.py
"""

__version__ = "1.0.0"
__author__ = "Vergil Team"

from .config import setup_paths

# Auto-setup paths when this module is imported
setup_paths()

__all__ = [
    "setup_paths",
]
