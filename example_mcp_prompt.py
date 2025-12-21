"""Example script showing how the MCP prompt is constructed with aliases."""
import json
from splitwise_client import SplitwiseClient
from alias_manager import AliasManager

# Initialize components
alias_manager = AliasManager('aliases.example.json')
splitwise_client = SplitwiseClient(mcp_handler=None)

# Example detected participants from OCR
detected_participants = ['alex boops', 'Dilawar']

# Example transaction details
description = "Dilawar 7 spices me alex boops"
cost = 460.00
group_id = None
image_path = "/path/to/receipt.jpg"

# Get all aliases
all_aliases = alias_manager.aliases

print("=" * 80)
print("EXAMPLE: How Auto-Split constructs MCP prompts")
print("=" * 80)
print()

print("1. Detected participants from transaction image:")
print(f"   {detected_participants}")
print()

print("2. Available aliases in system:")
for canonical_name, aliases in all_aliases.items():
    print(f"   - {canonical_name}: {', '.join(aliases)}")
print()

# Create the expense (which prepares the MCP call)
result = splitwise_client.create_expense(
    description=description,
    cost=cost,
    participants=detected_participants,
    group_id=group_id,
    image_path=image_path,
    all_aliases=all_aliases
)

print("3. Generated MCP instruction prompt:")
print("-" * 80)
print(result['instructions'])
print("-" * 80)
print()

print("4. MCP Parameters that would be sent:")
print(json.dumps(result['mcp_params'], indent=2))
print()

print("5. How it works:")
print("   - The MCP's AI reads the detected names: 'alex boops', 'Dilawar'")
print("   - It sees the alias mappings showing 'Alex Boops' has aliases ['alex', 'boops']")
print("   - It intelligently matches 'alex boops' → 'Alex Boops'")
print("   - It matches 'Dilawar' → 'Dilawar Hussain' (using fuzzy matching)")
print("   - It creates the expense split with the actual Splitwise users")
print()
print("=" * 80)
