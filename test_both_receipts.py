#!/usr/bin/env python3
"""Test both receipts with the updated message parser."""

import sys
sys.path.insert(0, '/path/to/auto-split')
from image_parser import ImageParser
import logging

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

parser = ImageParser()

print("="*80)
print("TESTING BOTH RECEIPTS")
print("="*80)

test_cases = [
    {
        "name": "New Loyal Mini Bazar",
        "path": "tests/test_images/New Loyal Mini Bazar - Rs. 27.jpeg",
        "expected_amount": 27.0,
        "expected_message": "Milk- me sarsan",
        "expected_participants": ["sarsan"]
    },
    {
        "name": "Rajeev Shetty",
        "path": "/path/to/home/Downloads/WhatsApp Image 2025-12-24 at 7.07.34 PM.jpeg",
        "expected_amount": 50.0,
        "expected_message": "Tea-me boops",
        "expected_participants": ["boops"]
    }
]

all_pass = True

for test in test_cases:
    print(f"\n{'='*80}")
    print(f"Testing: {test['name']}")
    print(f"{'='*80}")
    
    details = parser.parse_image(test['path'])
    
    print(f"\n📋 Results:")
    print(f"  Amount:       ₹{details.amount}")
    print(f"  Message:      '{details.message}'")
    print(f"  Participants: {details.participants}")
    
    # Check results
    checks = []
    
    if details.amount == test['expected_amount']:
        checks.append("✅ Amount correct")
    else:
        checks.append(f"❌ Amount: expected ₹{test['expected_amount']}, got ₹{details.amount}")
        all_pass = False
    
    if details.message == test['expected_message']:
        checks.append("✅ Message correct")
    else:
        checks.append(f"❌ Message: expected '{test['expected_message']}', got '{details.message}'")
        all_pass = False
    
    if details.participants == test['expected_participants']:
        checks.append("✅ Participants correct")
    else:
        checks.append(f"❌ Participants: expected {test['expected_participants']}, got {details.participants}")
        all_pass = False
    
    print(f"\n{'  '.join(checks)}")

print(f"\n{'='*80}")
if all_pass:
    print("🎉"*20)
    print("✅ ALL TESTS PASSED! Both receipts work correctly!")
    print("🎉"*20)
else:
    print("❌ SOME TESTS FAILED")
print(f"{'='*80}")

