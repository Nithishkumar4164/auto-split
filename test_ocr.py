#!/usr/bin/env python3
"""Quick script to test OCR extraction on a transaction image."""
import sys
from image_parser import ImageParser

if len(sys.argv) < 2:
    print("Usage: python test_ocr.py <image_path>")
    print("Example: python test_ocr.py '/path/to/home/Downloads/WhatsApp Image 2025-12-21 at 3.53.35 PM.jpeg'")
    sys.exit(1)

image_path = sys.argv[1]

# Initialize parser
parser = ImageParser(tesseract_cmd='/opt/homebrew/bin/tesseract')

print("=" * 80)
print("Testing OCR on:", image_path)
print("=" * 80)

# Extract raw text
print("\n1. Extracting text with OCR...")
text = parser._extract_text(image_path)

print("\n2. RAW OCR TEXT:")
print("-" * 80)
print(text)
print("-" * 80)

# Parse transaction details
print("\n3. Parsing transaction details...")
transaction = parser.parse_image(image_path)

print("\n4. PARSED DETAILS:")
print("-" * 80)
print(f"Amount:       ₹{transaction.amount}" if transaction.amount else "Amount:       NOT FOUND")
print(f"UTR:          {transaction.utr}" if transaction.utr else "UTR:          NOT FOUND")
print(f"Message:      {transaction.message}" if transaction.message else "Message:      NOT FOUND")
print(f"Recipient:    {transaction.recipient}" if transaction.recipient else "Recipient:    NOT FOUND")
print(f"Participants: {transaction.participants}")
print(f"Valid:        {transaction.is_valid()}")
print("-" * 80)

if not transaction.is_valid():
    print("\n⚠️  VALIDATION FAILED!")
    if not transaction.amount:
        print("   - Amount is missing")
    if not transaction.utr:
        print("   - UTR is missing")
else:
    print("\n✅ Transaction is VALID")

print("\n" + "=" * 80)
