"""Quick API smoke test (single batch, no waiting)."""

import sys
from datetime import datetime
from config import setup_paths

setup_paths()

from verification.smt_logic import verify_with_smt
from models.agent_responses import FinancialAction


def run_test(name: str, action: FinancialAction):
    """Run a single verification test."""
    print(f"[{name}]")
    print(f"  Amount: {action.amount} {action.asset}")
    print(f"  Target: {action.target_address}")
    
    try:
        result = verify_with_smt(action, "mock_contract_code")
        valid = result.get("valid", False)
        tokens = result.get("tokens_used", 0)
        llm_used = result.get("llm_used", False)
        model = result.get("model", "N/A")
        
        print(f"  ✓ Verification: {'PASS' if valid else 'BLOCKED'}")
        print(f"  ✓ LLM used: {'YES' if llm_used else 'NO'}")
        print(f"  ✓ Model: {model}")
        print(f"  ✓ Tokens: {tokens}\n")
        
        return {
            "name": name,
            "valid": valid,
            "tokens": tokens,
            "llm_used": llm_used,
            "model": model,
        }
    except Exception as e:
        print(f"  ✗ Error: {e}\n")
        return {
            "name": name,
            "valid": False,
            "tokens": 0,
            "llm_used": False,
            "error": str(e),
        }


if __name__ == "__main__":
    print("="*60)
    print("Quick API Test (3 requests, no delay)")
    print("="*60)
    print(f"Start time: {datetime.now().strftime('%H:%M:%S')}\n")
    
    # Prepare 3 valid scenarios
    tests = [
        ("Test 1: Small ETH", FinancialAction(
            amount=0.5,
            asset="ETH",
            target_address="0x742d35Cc6634C0532925a3b844Bc9e7595f42bE0"
        )),
        ("Test 2: Mid USDC", FinancialAction(
            amount=2.5,
            asset="USDC",
            target_address="0x5A0b54D5dc17e0AadC383d2db43B0a0D3E029c4c"
        )),
        ("Test 3: Large WETH", FinancialAction(
            amount=4.8,
            asset="WETH",
            target_address="0x1234567890123456789012345678901234567890"
        )),
    ]
    
    # Run all tests
    results = []
    for name, action in tests:
        result = run_test(name, action)
        results.append(result)
    
    # Summary
    print("="*60)
    print("Summary")
    print("="*60)
    total_tokens = sum(r.get("tokens", 0) for r in results)
    llm_called = sum(1 for r in results if r.get("llm_used", False))
    
    print(f"End time: {datetime.now().strftime('%H:%M:%S')}")
    print(f"Total tests: {len(results)}")
    print(f"LLM calls: {llm_called}/{len(results)}")
    print(f"Total tokens: {total_tokens}")
    print(f"Avg tokens/request: {total_tokens/len(results) if results else 0:.1f}")
    
    print("\nRate-limit checks:")
    print(f"  ✓ 3 RPM: OK ({len(results)} requests sent)")
    print(f"  ✓ 40,000 TPM: {'OK' if total_tokens < 40000 else 'WARNING'} ({total_tokens} tokens used)")
    
    if llm_called > 0:
        print(f"\n✅ OpenAI API called successfully {llm_called} times")
    else:
        print("\n⚠️  Warning: No OpenAI API call detected")
