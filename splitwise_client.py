"""Splitwise client using Zapier MCP for creating expenses."""
import logging
from typing import Dict, List, Optional
import base64

logger = logging.getLogger(__name__)


class SplitwiseClient:
    """Client for interacting with Splitwise via Zapier MCP."""
    
    def __init__(self, mcp_handler):
        """Initialize Splitwise client.
        
        Args:
            mcp_handler: Handler for MCP tool calls
        """
        self.mcp_handler = mcp_handler
    
    def create_expense(
        self,
        description: str,
        cost: float,
        participants: List[str],
        group_id: Optional[str] = None,
        image_path: Optional[str] = None
    ) -> Dict:
        """Create a Splitwise expense.
        
        Args:
            description: Expense description
            cost: Total cost of expense
            participants: List of participant names
            group_id: Splitwise group ID (optional)
            image_path: Path to image file to attach (optional)
            
        Returns:
            Response from Splitwise API
        """
        try:
            # Prepare expense data
            expense_data = {
                'description': description,
                'cost': str(cost),
                'users': participants
            }
            
            if group_id:
                expense_data['group_id'] = group_id
            
            # Build instructions for MCP
            instructions = self._build_instructions(
                description, cost, participants, group_id, image_path
            )
            
            logger.info(f"Creating Splitwise expense: {description} - ₹{cost}")
            logger.debug(f"Expense data: {expense_data}")
            
            # Call MCP tool (this would be done by the caller in practice)
            # For now, we prepare the call parameters
            mcp_params = {
                'instructions': instructions,
                'output_hint': 'return the expense ID, status, and any error messages'
            }
            
            # Add optional parameters
            if group_id:
                mcp_params['group_id'] = group_id
            
            mcp_params['description'] = description
            mcp_params['cost'] = str(cost)
            mcp_params['users'] = participants
            
            logger.info(f"Prepared MCP call for expense creation")
            
            return {
                'success': True,
                'mcp_params': mcp_params,
                'message': 'Expense creation request prepared'
            }
            
        except Exception as e:
            logger.error(f"Error creating expense: {e}", exc_info=True)
            return {
                'success': False,
                'error': str(e)
            }
    
    def _build_instructions(
        self,
        description: str,
        cost: float,
        participants: List[str],
        group_id: Optional[str] = None,
        image_path: Optional[str] = None
    ) -> str:
        """Build instructions for MCP tool call.
        
        Args:
            description: Expense description
            cost: Total cost
            participants: List of participants
            group_id: Group ID (optional)
            image_path: Image path (optional)
            
        Returns:
            Instructions string
        """
        participants_str = ', '.join(participants)
        
        instructions = f"Create a Splitwise expense with description '{description}' "
        instructions += f"for ₹{cost} split equally among: {participants_str}. "
        
        if group_id:
            instructions += f"Add this expense to group ID {group_id}. "
        else:
            instructions += "Create this expense outside of any group. "
        
        if image_path:
            instructions += f"Attach the image from {image_path} to the expense. "
        
        return instructions
    
    def get_groups(self) -> List[Dict]:
        """Get list of Splitwise groups.
        
        Note: This would need to be implemented via MCP or API
        For now, returns empty list as placeholder.
        
        Returns:
            List of groups
        """
        logger.info("Getting Splitwise groups")
        # This would need MCP implementation
        return []
    
    def find_group_by_name(self, group_name: str) -> Optional[str]:
        """Find group ID by name.
        
        Args:
            group_name: Name of the group
            
        Returns:
            Group ID or None
        """
        logger.info(f"Finding group: {group_name}")
        groups = self.get_groups()
        
        for group in groups:
            if group.get('name', '').lower() == group_name.lower():
                return group.get('id')
        
        return None
    
    def upload_image(self, image_path: str) -> Optional[str]:
        """Upload image to Splitwise.
        
        Args:
            image_path: Path to image file
            
        Returns:
            Image URL or None
        """
        try:
            logger.info(f"Uploading image: {image_path}")
            
            # Read and encode image
            with open(image_path, 'rb') as f:
                image_data = f.read()
            
            # For now, we'll return the path
            # In production, this would upload via MCP
            return image_path
            
        except Exception as e:
            logger.error(f"Error uploading image: {e}", exc_info=True)
            return None
    
    def prepare_expense_with_image(
        self,
        description: str,
        cost: float,
        participants: List[str],
        image_path: str,
        group_id: Optional[str] = None
    ) -> Dict:
        """Prepare expense creation with image attachment.
        
        Args:
            description: Expense description
            cost: Total cost
            participants: List of participants
            image_path: Path to transaction image
            group_id: Group ID (optional)
            
        Returns:
            Response dict
        """
        # First upload image
        image_url = self.upload_image(image_path)
        
        # Then create expense
        result = self.create_expense(
            description=description,
            cost=cost,
            participants=participants,
            group_id=group_id,
            image_path=image_url
        )
        
        return result

