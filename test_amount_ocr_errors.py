#!/usr/bin/env python3
"""Test amount parsing with common OCR errors."""
from image_parser import ImageParser

# Initialize parser
parser = ImageParser()

# Test cases with OCR errors
test_texts = [
    # OCR reads ₹1 as "z1"
    ("Sample Store z1", 1.0, "₹ misread as 'z'"),
    
    # OCR reads ₹1 as "21" (₹ read as 2)
    ("Sample Store 21", 1.0, "₹ misread as '2', making ₹1 become 21"),
    
    # Correct reading
    ("Amount: ₹1", 1.0, "Correct ₹ symbol"),
    ("Amount: ₹460", 460.0, "Correct ₹ symbol"),
    
    # Other OCR errors
    ("Paid to someone z5", 5.0, "₹5 read as z5"),
    ("Total: 31", 1.0, "₹1 read as 31"),
    
    # Should NOT be misread (actual amounts)
    ("Amount: ₹111", 111.0, "Actual ₹111"),
    ("Amount: ₹210", 210.0, "Actual ₹210"),
]

print("=" * 80)
print("Testing Amount Parsing with OCR Errors")
print("=" * 80)

for text, expected_amount, description in test_texts:
    print(f"\nTest: {description}")
    print(f"Text: '{text}'")
    print(f"Expected: ₹{expected_amount}")
    
    parsed_amount = parser.parse_amount(text)
    
    if parsed_amount == expected_amount:
        print(f"✅ PASS: Got ₹{parsed_amount}")
    else:
        print(f"❌ FAIL: Got ₹{parsed_amount} instead of ₹{expected_amount}")

print("\n" + "=" * 80)

