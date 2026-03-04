import sys

# Check address lengths
addresses = [
    ("Original from tests", "0x742d35Cc6abC5A2C7B8C1C3d3F0F8E2B91d4b3eF"),
    ("Checksum variant", "0x742D35cc6634C0532925a3b844Bc9c7595f5421"),
    ("Lowercase variant", "0x742d35cc6634c0532925a3b844bc9c7595f5421"),
]

print("Address length check:\n")
for desc, addr in addresses:
    print(f"{desc}")
    print(f"  Address: {addr}")
    print(f"  Length:  {len(addr)} (should be 42: 0x + 40 hex chars)")
    if len(addr) != 42:
        print(f"  ERROR:   Wrong length! Missing {42 - len(addr)} chars")
    print()

# Correct address (42 chars total)
correct = "0x742d35Cc6abC5A2C7B8C1C3d3F0F8E2B91d4b3eF"
print(f"CORRECT: {correct}")
print(f"Length:  {len(correct)}")
