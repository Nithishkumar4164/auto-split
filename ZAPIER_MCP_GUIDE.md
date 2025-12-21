# Zapier Splitwise MCP Integration Guide

This guide explains how to integrate AutoSplit with Splitwise using Zapier's Model Context Protocol (MCP) tools.

## Overview

AutoSplit uses Zapier MCP to create Splitwise expenses. The integration happens through AI assistant (Claude) which has access to MCP tools in supported environments.

## MCP Tool: mcp_Zapier_splitwise_create_expense

### Tool Signature

```python
mcp_Zapier_splitwise_create_expense(
    description: str,        # Expense description
    cost: str,              # Total cost as string
    group_id: str,          # Optional: Splitwise group ID
    users: List[str],       # List of participant names/emails
    instructions: str,      # Human-readable instructions for AI
    output_hint: str        # What data to return
)
```

## How AutoSplit Uses MCP

### 1. Transaction Processing Flow

```python
# From expense_processor.py
def process_image(self, image_path: str, group_name: Optional[str] = None):
    # Step 1: Parse image
    transaction = self.image_parser.parse_image(image_path)
    # Result: amount=460.0, utr="987654321098", message="Dilawar 7 spices me alex boops"
    
    # Step 2: Check UTR uniqueness
    if self.utr_tracker.is_processed(transaction.utr):
        return {'success': False, 'error': 'Duplicate'}
    
    # Step 3: Match participants
    matched = self.alias_manager.match_participants(transaction.participants)
    # Result: ["Alex Boops"] (matched from "alex boops")
    
    # Step 4: Find group
    group_id = self.splitwise_client.find_group_by_name(group_name)
    
    # Step 5: Create expense via MCP
    result = self.splitwise_client.prepare_expense_with_image(
        description=transaction.message,
        cost=transaction.amount,
        participants=matched,
        image_path=image_path,
        group_id=group_id
    )
```

### 2. Preparing MCP Call

```python
# From splitwise_client.py
def create_expense(self, description, cost, participants, group_id=None, image_path=None):
    # Build human-readable instructions
    instructions = f"Create a Splitwise expense with description '{description}' "
    instructions += f"for ₹{cost} split equally among: {', '.join(participants)}. "
    
    if group_id:
        instructions += f"Add this expense to group ID {group_id}. "
    else:
        instructions += "Create this expense outside of any group. "
    
    if image_path:
        instructions += f"Attach the image from {image_path} to the expense. "
    
    # Prepare MCP parameters
    mcp_params = {
        'description': description,
        'cost': str(cost),  # Zapier expects string
        'users': participants,
        'instructions': instructions,
        'output_hint': 'return the expense ID, status, and any error messages'
    }
    
    if group_id:
        mcp_params['group_id'] = group_id
    
    return {'success': True, 'mcp_params': mcp_params}
```

## Real-World Examples

### Example 1: Group Expense with Image

**Scenario**: Transaction image uploaded to `Splitwise/Roommates/transaction.jpeg`

**Extracted Data**:
```python
{
    "amount": 460.0,
    "message": "Dilawar 7 spices me alex boops",
    "utr": "987654321098",
    "participants": ["alex boops"]
}
```

**Matched Participants**:
```python
["Alex Boops"]  # From aliases: "alex boops" → "Alex Boops"
```

**MCP Call**:
```python
mcp_Zapier_splitwise_create_expense(
    description="Dilawar 7 spices me alex boops",
    cost="460",
    group_id="12345678",  # Roommates group ID
    users=["Alex Boops"],
    instructions="""
        Create a Splitwise expense with description 'Dilawar 7 spices me alex boops' 
        for ₹460 split equally among: Alex Boops. 
        Add this expense to group ID 12345678. 
        Attach the image from /tmp/autosplit/transaction.jpeg to the expense.
    """,
    output_hint="return the expense ID, status, and any error messages"
)
```

**Expected Response**:
```json
{
    "expense_id": "exp_789012",
    "status": "success",
    "created_at": "2025-12-19T15:17:00Z",
    "group_id": "12345678",
    "cost": "460",
    "currency": "INR"
}
```

### Example 2: Non-Group Expense

**Scenario**: Transaction image uploaded to `Splitwise/transaction.jpeg` (root level)

**MCP Call**:
```python
mcp_Zapier_splitwise_create_expense(
    description="Lunch payment",
    cost="300",
    users=["John Doe", "Jane Smith"],
    instructions="""
        Create a Splitwise expense with description 'Lunch payment' 
        for ₹300 split equally among: John Doe, Jane Smith. 
        Create this expense outside of any group.
    """,
    output_hint="return the expense ID, status, and any error messages"
)
```

### Example 3: Single Participant

**Scenario**: Payment to one person

**MCP Call**:
```python
mcp_Zapier_splitwise_create_expense(
    description="Grocery reimbursement",
    cost="1250.50",
    users=["Alice Cooper"],
    instructions="""
        Create a Splitwise expense with description 'Grocery reimbursement' 
        for ₹1250.50 split equally among: Alice Cooper. 
        Create this expense outside of any group.
    """,
    output_hint="return the expense ID, status, and any error messages"
)
```

## Setting Up Zapier for MCP

### 1. Connect Splitwise to Zapier

1. Log in to [Zapier](https://zapier.com)
2. Navigate to "My Apps"
3. Click "Add Connection"
4. Search for "Splitwise"
5. Click "Connect"
6. Authorize Zapier to access your Splitwise account
7. Test the connection

### 2. Configure Splitwise Groups

Get your Splitwise group IDs:

```bash
# Using Splitwise API
curl https://secure.splitwise.com/api/v3.0/get_groups \
  -H "Authorization: Bearer YOUR_API_KEY"
```

Map group names to IDs in your application:
```python
# In your deployment, you might want to store this mapping
SPLITWISE_GROUPS = {
    "Roommates": "12345678",
    "Friends": "23456789",
    "Family": "34567890"
}
```

### 3. Test MCP Integration

Create a test script:

```python
# test_mcp.py
from splitwise_client import SplitwiseClient

client = SplitwiseClient(mcp_handler=None)

# Prepare a test expense
result = client.create_expense(
    description="Test expense",
    cost=100.0,
    participants=["Test User"],
    group_id="12345678"
)

print(result)
```

## Handling MCP Responses

### Success Response

```python
{
    'success': True,
    'expense_id': 'exp_123456',
    'cost': '460',
    'currency': 'INR',
    'created_at': '2025-12-19T15:17:00Z'
}
```

Process success:
```python
if result.get('success'):
    expense_id = result.get('expense_id')
    
    # Record UTR
    utr_tracker.add_utr(
        utr=transaction.utr,
        amount=transaction.amount,
        expense_id=expense_id,
        group_name=group_name,
        participants=matched_participants
    )
```

### Error Response

```python
{
    'success': False,
    'error': 'Invalid group ID',
    'error_code': 'INVALID_GROUP'
}
```

Handle errors:
```python
if not result.get('success'):
    error = result.get('error', 'Unknown error')
    logger.error(f"Failed to create expense: {error}")
    
    # Optionally retry or notify
    return {
        'success': False,
        'error': f'Splitwise expense creation failed: {error}'
    }
```

## Advanced Features

### 1. Expense Categories

Add categories to expenses:

```python
mcp_params['instructions'] += " Categorize this expense as 'Food and Drink'."
```

### 2. Custom Split Ratios

Instead of equal split:

```python
instructions = f"Split this expense with 60% to User1 and 40% to User2."
```

### 3. Adding Notes

Include additional context:

```python
description = f"{transaction.message}\n\nUTR: {transaction.utr}\nPaid via: {transaction.recipient_upi}"
```

### 4. Recurring Expenses

For subscriptions:

```python
instructions += " Set this as a monthly recurring expense."
```

## Error Handling

### Common Errors and Solutions

#### 1. "User not found"
```python
# Solution: Check aliases and participant matching
matched = alias_manager.match_participants(names, threshold=70)
if not matched:
    logger.warning(f"No participants matched for: {names}")
```

#### 2. "Invalid group ID"
```python
# Solution: Verify group exists
group_id = splitwise_client.find_group_by_name(group_name)
if not group_id:
    logger.warning(f"Group not found: {group_name}")
    # Create expense without group
    group_id = None
```

#### 3. "Duplicate expense"
```python
# Solution: Check UTR before creating
if utr_tracker.is_processed(utr):
    return {'success': False, 'error': 'Duplicate UTR'}
```

#### 4. "Rate limit exceeded"
```python
# Solution: Implement exponential backoff
import time

def create_with_retry(max_retries=3):
    for attempt in range(max_retries):
        try:
            return splitwise_client.create_expense(...)
        except RateLimitError:
            wait_time = 2 ** attempt
            time.sleep(wait_time)
    raise Exception("Max retries exceeded")
```

## Testing MCP Integration

### Unit Test Example

```python
# tests/test_splitwise_mcp.py
def test_create_expense_mcp_params():
    client = SplitwiseClient(mcp_handler=None)
    
    result = client.create_expense(
        description="Test",
        cost=100.0,
        participants=["User1"],
        group_id="123"
    )
    
    assert result['success'] is True
    assert 'mcp_params' in result
    assert result['mcp_params']['description'] == "Test"
    assert result['mcp_params']['cost'] == "100.0"
```

### Integration Test

```python
# Test with actual MCP (requires MCP environment)
def test_real_expense_creation():
    # This would run in an environment with MCP support
    processor = ExpenseProcessor(...)
    
    result = processor.process_image(
        "test_transaction.jpeg",
        group_name="TestGroup"
    )
    
    assert result['success'] is True
    assert 'expense_id' in result
```

## Best Practices

### 1. Always Include Instructions
```python
# Good: Detailed instructions
instructions = """
    Create a Splitwise expense with description 'Dinner' 
    for ₹500 split equally among: Alice, Bob. 
    Add to group 'Friends'. 
    Categorize as 'Food and Drink'.
"""

# Bad: Minimal instructions
instructions = "Create expense"
```

### 2. Handle Partial Failures
```python
# If participant matching fails, still try to create expense
if not matched_participants:
    # Fall back to using email or creating without specific users
    matched_participants = [transaction.recipient]
```

### 3. Log All MCP Calls
```python
logger.info(f"MCP Call: {mcp_params}")
# After call
logger.info(f"MCP Response: {response}")
```

### 4. Validate Data Before MCP Call
```python
if not description or not cost or not participants:
    logger.error("Invalid expense data")
    return {'success': False, 'error': 'Missing required fields'}
```

## Monitoring and Debugging

### Check MCP Call Logs
```bash
# In Cloud Run logs
gcloud logging read \
  "resource.labels.service_name=autosplit AND textPayload=~'MCP'" \
  --limit 50
```

### Track Success/Failure Rates
```python
# Add metrics
total_expenses = 0
successful_expenses = 0
failed_expenses = 0

if result.get('success'):
    successful_expenses += 1
else:
    failed_expenses += 1
```

## Resources

- [Zapier Documentation](https://zapier.com/help)
- [Splitwise API Docs](https://dev.splitwise.com)
- [MCP Protocol](https://modelcontextprotocol.io)
- [AutoSplit Documentation](README.md)

## Support

If you encounter issues:
1. Check Zapier connection status
2. Verify Splitwise API credentials
3. Review MCP call logs
4. Test with simple expense first
5. Check participant names and aliases

---

**Ready to integrate?** Follow the examples above and refer to `mcp_integration_example.py` for more code samples!

