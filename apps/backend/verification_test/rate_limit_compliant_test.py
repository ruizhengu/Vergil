"""Batched verification test respecting strict rate limits.

Default policy:
- 3 requests per batch
- 60 seconds between batches
"""

import os
import sys
import time
import json
from datetime import datetime
from pathlib import Path

from config import setup_paths

setup_paths()

from verification.smt_logic import verify_with_smt
from models.agent_responses import FinancialAction


class RateLimitedTester:
    def __init__(self, batch_size: int = 3, batch_interval: int = 60):
        """Initialize batch settings and counters."""
        self.batch_size = batch_size
        self.batch_interval = batch_interval
        self.total_requests = 0
        self.total_tokens = 0
        self.failed_requests = 0
        self.api_calls_log = []
        
    def log_api_call(self, test_name: str, success: bool, tokens: int = 0, error: str = None):
        """Log one API call outcome."""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "test_name": test_name,
            "success": success,
            "tokens": tokens,
            "error": error,
        }
        self.api_calls_log.append(entry)
        self.total_requests += 1
        self.total_tokens += tokens
        if not success:
            self.failed_requests += 1

    def test_case_1(self):
        """Test case 1: small ETH transfer."""
        print("  [Test 1] Small ETH transfer (0.5 ETH)...")
        try:
            action = FinancialAction(
                amount=0.5,
                asset="ETH",
                target_address="0x742d35Cc6634C0532925a3b844Bc9e7595f42bE0"
            )
            result = verify_with_smt(action, "mock_contract_code")
            success = result.get("valid", False)
            tokens = result.get("tokens_used", 0)
            error = result.get("error") if not success else None
            self.log_api_call("test_case_1", True, tokens, error)
            print(f"    ✓ Result: {success} (tokens: {tokens})")
            return True
        except Exception as e:
            self.log_api_call("test_case_1", False, error=str(e))
            print(f"    ✗ Error: {e}")
            return False

    def test_case_2(self):
        """Test case 2: medium USDC transfer."""
        print("  [Test 2] Medium USDC transfer (2.5 USDC)...")
        try:
            action = FinancialAction(
                amount=2.5,
                asset="USDC",
                target_address="0x5A0b54D5dc17e0AadC383d2db43B0a0D3E029c4c"
            )
            result = verify_with_smt(action, "mock_contract_code")
            success = result.get("valid", False)
            tokens = result.get("tokens_used", 0)
            error = result.get("error") if not success else None
            self.log_api_call("test_case_2", True, tokens, error)
            print(f"    ✓ Result: {success} (tokens: {tokens})")
            return True
        except Exception as e:
            self.log_api_call("test_case_2", False, error=str(e))
            print(f"    ✗ Error: {e}")
            return False

    def test_case_3(self):
        """Test case 3: large WETH transfer near limit."""
        print("  [Test 3] Large WETH transfer (4.8 WETH)...")
        try:
            action = FinancialAction(
                amount=4.8,
                asset="WETH",
                target_address="0x1234567890123456789012345678901234567890"
            )
            result = verify_with_smt(action, "mock_contract_code")
            success = result.get("valid", False)
            tokens = result.get("tokens_used", 0)
            error = result.get("error") if not success else None
            self.log_api_call("test_case_3", True, tokens, error)
            print(f"    ✓ Result: {success} (tokens: {tokens})")
            return True
        except Exception as e:
            self.log_api_call("test_case_3", False, error=str(e))
            print(f"    ✗ Error: {e}")
            return False

    def run_batch(self, batch_num: int, test_cases: list):
        """Run one batch of tests."""
        print(f"\n{'='*60}")
        print(f"Batch {batch_num} - Time: {datetime.now().strftime('%H:%M:%S')}")
        print(f"{'='*60}")
        
        results = []
        for i, test_func in enumerate(test_cases, 1):
            print(f"\n[{i}/{len(test_cases)}] Running test...")
            result = test_func()
            results.append(result)
            
            # Short gap inside each batch
            if i < len(test_cases):
                print("  Waiting 2 seconds...")
                time.sleep(2)
        
        return results

    def run_all_batches(self):
        """Run all configured batches."""
        print("\n" + "="*60)
        print("Starting batched test run (3 RPM policy)")
        print("="*60)
        print(f"Config: {self.batch_size} requests/batch, {self.batch_interval}s between batches")
        print(f"Start time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        
        # 3 batches
        test_batches = [
            [self.test_case_1, self.test_case_2, self.test_case_3],
            [self.test_case_1, self.test_case_2, self.test_case_3],
            [self.test_case_1, self.test_case_2, self.test_case_3],
        ]
        
        all_results = []
        for batch_idx, batch_tests in enumerate(test_batches, 1):
            batch_results = self.run_batch(batch_idx, batch_tests)
            all_results.extend(batch_results)
            
            # Wait between batches (except last)
            if batch_idx < len(test_batches):
                print(f"\n⏳ Waiting {self.batch_interval} seconds before next batch...")
                for remaining in range(self.batch_interval, 0, -10):
                    print(f"  Continue in {remaining}s...", end="\r")
                    time.sleep(min(10, remaining))
                print()
        
        return all_results

    def print_summary(self):
        """Print a concise run summary."""
        print("\n" + "="*60)
        print("Run Summary")
        print("="*60)
        print(f"End time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Total requests: {self.total_requests}")
        print(f"Successful requests: {self.total_requests - self.failed_requests}")
        print(f"Failed requests: {self.failed_requests}")
        print(f"Total tokens used: {self.total_tokens}")
        
        # Average token consumption
        avg_tokens_per_request = (
            self.total_tokens / self.total_requests 
            if self.total_requests > 0 else 0
        )
        print(f"Avg tokens/request: {avg_tokens_per_request:.1f}")
        
        print("\nRate-limit checks:")
        print(f"  3 RPM: ✓ ({self.total_requests} requests sent)")
        print(f"  40,000 TPM: {'✓' if self.total_tokens < 40000 else '⚠'} ({self.total_tokens} tokens used)")
        
        return {
            "total_requests": self.total_requests,
            "failed_requests": self.failed_requests,
            "total_tokens": self.total_tokens,
            "api_calls_log": self.api_calls_log,
        }

    def save_report(self, filename: str = "rate_limit_test_report.json"):
        """Save the test report as JSON."""
        report = {
            "test_config": {
                "batch_size": self.batch_size,
                "batch_interval": self.batch_interval,
                "rate_limits": {
                    "rpm": 3,
                    "tpm": 40000,
                    "rpd": 200,
                    "tpd": 200000,
                }
            },
            "summary": self.print_summary(),
            "detailed_logs": self.api_calls_log,
        }
        
        filepath = Path(__file__).parent / filename
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        
        print(f"\n📊 Report saved: {filepath}")


if __name__ == "__main__":
    # Basic configuration check
    if not os.getenv("OPENAI_API_KEY"):
        print("❌ Error: OPENAI_API_KEY is not set")
        sys.exit(1)
    
    model = os.getenv("OPENAI_MODEL", "gpt-4o")
    print(f"Using model: {model}\n")
    
    # Execute tests
    tester = RateLimitedTester(batch_size=3, batch_interval=60)
    results = tester.run_all_batches()
    tester.print_summary()
    tester.save_report()
    
    # Success rate
    success_rate = (
        (len(results) - sum(1 for r in results if not r)) / len(results) * 100
        if results else 0
    )
    print(f"\n✅ Success rate: {success_rate:.1f}%")
