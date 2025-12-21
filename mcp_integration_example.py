"""
Example integration showing how to use Zapier MCP for Splitwise expense creation.

This file demonstrates how the AutoSplit application integrates with Splitwise
using the Zapier MCP (Model Context Protocol) tools.

The actual MCP tool calls should be made by the AI assistant (Claude) when
running in an environment that supports MCP.
"""

import json
from typing import Dict, List


class SplitwiseMCPIntegration:
    """
    Example class showing how to prepare data for Splitwise MCP calls.
    
    In production, the MCP tools would be called by the AI assistant via:
    - mcp_Zapier_splitwise_create_expense
    """
    
    @staticmethod
    def prepare_create_expense_call(
        description: str,
        cost: float,
        group_id: str = None,
        users: List[str] = None
    ) -> Dict:
        """
        Prepare parameters for Splitwise expense creation via MCP.
        
        Args:
            description: Expense description (e.g., "Dilawar 7 spices me alex boops")
            cost: Total cost of expense (e.g., 460.0)
            group_id: Optional Splitwise group ID
            users: List of participant names/emails
            
        Returns:
            Dictionary with MCP call parameters
        """
        # Build human-readable instructions for the MCP tool
        instructions = f"Create a Splitwise expense with description '{description}' "
        instructions += f"for ₹{cost} (Indian Rupees). "
        
        if group_id:
            instructions += f"Add this expense to group ID '{group_id}'. "
        else:
            instructions += "Create this expense outside of any group. "
        
        if users:
            instructions += f"Split equally among: {', '.join(users)}."
        
        # Prepare MCP tool call parameters
        mcp_params = {
            "tool_name": "mcp_Zapier_splitwise_create_expense",
            "parameters": {
                "description": description,
                "cost": str(cost),  # Zapier expects string
                "instructions": instructions,
                "output_hint": "return the expense ID, created date, and any error messages"
            }
        }
        
        # Add optional parameters
        if group_id:
            mcp_params["parameters"]["group_id"] = group_id
        
        if users:
            mcp_params["parameters"]["users"] = users
        
        return mcp_params
    
    @staticmethod
    def example_usage():
        """
        Example usage showing various scenarios.
        """
        print("=" * 80)
        print("Splitwise MCP Integration Examples")
        print("=" * 80)
        print()
        
        # Example 1: Create expense in a group
        print("Example 1: Create expense in a group")
        print("-" * 40)
        params1 = SplitwiseMCPIntegration.prepare_create_expense_call(
            description="Dilawar 7 spices me alex boops",
            cost=460.0,
            group_id="12345678",  # Roommates group ID
            users=["alex boops", "current user"]
        )
        print(json.dumps(params1, indent=2))
        print()
        
        # Example 2: Create expense outside group
        print("Example 2: Create expense outside group")
        print("-" * 40)
        params2 = SplitwiseMCPIntegration.prepare_create_expense_call(
            description="Grocery shopping",
            cost=1250.50,
            users=["John Doe", "Jane Smith"]
        )
        print(json.dumps(params2, indent=2))
        print()
        
        # Example 3: Create expense with single participant
        print("Example 3: Create expense with single participant")
        print("-" * 40)
        params3 = SplitwiseMCPIntegration.prepare_create_expense_call(
            description="Lunch payment",
            cost=300.0,
            users=["friend@example.com"]
        )
        print(json.dumps(params3, indent=2))
        print()


def demonstrate_full_workflow():
    """
    Demonstrate the full workflow from transaction image to Splitwise expense.
    """
    print("=" * 80)
    print("Full AutoSplit Workflow Example")
    print("=" * 80)
    print()
    
    # Step 1: Image uploaded to Google Drive
    print("Step 1: Transaction image uploaded")
    print("-" * 40)
    print("Location: gs://bucket/Splitwise/Roommates/transaction_123.jpeg")
    print()
    
    # Step 2: OCR extracts transaction details
    print("Step 2: OCR extracts transaction details")
    print("-" * 40)
    transaction_data = {
        "amount": 460.0,
        "recipient": "DILAWAR",
        "message": "Dilawar 7 spices me alex boops",
        "utr": "987654321098",
        "participants": ["alex boops"]
    }
    print(json.dumps(transaction_data, indent=2))
    print()
    
    # Step 3: Match participants using aliases
    print("Step 3: Match participants to canonical names")
    print("-" * 40)
    matched_participants = ["Alex Boops"]  # Matched from "alex boops" alias
    print(f"Matched: {matched_participants}")
    print()
    
    # Step 4: Find Splitwise group
    print("Step 4: Find Splitwise group")
    print("-" * 40)
    group_name = "Roommates"
    group_id = "12345678"  # Found from group name
    print(f"Group: {group_name} (ID: {group_id})")
    print()
    
    # Step 5: Prepare MCP call
    print("Step 5: Prepare Splitwise MCP call")
    print("-" * 40)
    mcp_params = SplitwiseMCPIntegration.prepare_create_expense_call(
        description=transaction_data["message"],
        cost=transaction_data["amount"],
        group_id=group_id,
        users=matched_participants
    )
    print(json.dumps(mcp_params, indent=2))
    print()
    
    # Step 6: Execute MCP call (would be done by AI assistant)
    print("Step 6: AI assistant executes MCP call")
    print("-" * 40)
    print("Tool: mcp_Zapier_splitwise_create_expense")
    print("Status: Expense created successfully")
    print("Expense ID: exp_789012")
    print()
    
    # Step 7: Track UTR
    print("Step 7: Record UTR to prevent duplicates")
    print("-" * 40)
    utr_record = {
        "utr": transaction_data["utr"],
        "amount": transaction_data["amount"],
        "expense_id": "exp_789012",
        "group_name": group_name,
        "participants": matched_participants,
        "processed_at": "2025-12-19T15:17:00"
    }
    print(json.dumps(utr_record, indent=2))
    print()
    
    print("=" * 80)
    print("Workflow completed successfully!")
    print("=" * 80)


if __name__ == "__main__":
    # Run examples
    SplitwiseMCPIntegration.example_usage()
    print("\n" * 2)
    demonstrate_full_workflow()
    
    print("\n" * 2)
    print("NOTE: In production, the MCP tool calls are executed by the AI assistant")
    print("(Claude) in an environment that supports the Model Context Protocol.")
    print("The AutoSplit application prepares the parameters and instructions,")
    print("and the AI assistant handles the actual Zapier/Splitwise integration.")

