#!/usr/bin/env python3
"""Test the new message format parsing."""
from image_parser import ImageParser

# Initialize parser
parser = ImageParser()

# Test cases
test_messages = [
    "Testtransfer- me sanj boops",
    "Dilawar 7 spices- me alex boops",
    "Lunch at cafe- me sanj sivak",
    "Movie tickets- alex boops sanj",
    "Old format with people alex and boops",
]

print("=" * 80)
print("Testing Message Format Parsing")
print("=" * 80)

for message in test_messages:
    print(f"\nMessage: '{message}'")
    participants = parser.parse_participants(message)
    print(f"Participants: {participants}")
    
    # Extract title if dash present
    if '-' in message:
        title = message.split('-', 1)[0].strip()
        print(f"Title: '{title}'")

print("\n" + "=" * 80)


