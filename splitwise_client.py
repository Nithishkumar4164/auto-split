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
        image_path: Optional[str] = None,
        all_aliases: Optional[Dict[str, List[str]]] = None
    ) -> Dict:
        """Create a Splitwise expense.
        
        Args:
            description: Expense description
            cost: Total cost of expense
            participants: List of participant names detected from transaction
            group_id: Splitwise group ID (optional)
            image_path: Path to image file to attach (optional)
            all_aliases: Dictionary mapping canonical names to aliases (optional)
            
        Returns:
            Response from Splitwise API
        """
        try:
            # Build instructions for MCP with alias context
            instructions = self._build_instructions(
                description, cost, participants, group_id, image_path, all_aliases
            )
            
            logger.info(f"Creating Splitwise expense: {description} - ₹{cost}")
            logger.debug(f"Detected participants: {participants}")
            
            # Prepare MCP call parameters
            mcp_params = {
                'instructions': instructions,
                'output_hint': 'return the expense ID, the users it was split with, and any status messages',
                'description': description,
                'cost': str(cost)
            }
            
            # Add optional group parameter
            if group_id:
                mcp_params['group_id'] = group_id
            
            logger.info(f"Prepared MCP call for expense creation")
            logger.debug(f"Instructions: {instructions}")
            
            return {
                'success': True,
                'mcp_params': mcp_params,
                'message': 'Expense creation request prepared',
                'instructions': instructions
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
        image_path: Optional[str] = None,
        all_aliases: Optional[Dict[str, List[str]]] = None
    ) -> str:
        """Build instructions for MCP tool call with alias context.
        
        Args:
            description: Expense description
            cost: Total cost
            participants: List of participant names detected from transaction
            group_id: Group ID (optional)
            image_path: Image path (optional)
            all_aliases: Dictionary mapping canonical names to their aliases
            
        Returns:
            Instructions string
        """
        instructions = f"Create a Splitwise expense with description '{description}' for ₹{cost}.\n\n"
        
        # Add detected participants context
        if participants:
            participants_str = ', '.join(participants)
            instructions += f"Detected participants from transaction: {participants_str}\n\n"
        
        # Add alias mapping context to help AI match participants
        if all_aliases:
            instructions += "Here are all known users and their aliases:\n"
            for canonical_name, aliases in all_aliases.items():
                aliases_str = ', '.join(aliases) if aliases else 'no aliases'
                instructions += f"  - {canonical_name} (also known as: {aliases_str})\n"
            instructions += "\n"
        
        # Instructions for AI to figure out users
        instructions += "Please:\n"
        instructions += "1. Match the detected participant names to the actual Splitwise users using the alias information above\n"
        instructions += "2. Split the expense equally among the matched users (including me as the payer)\n"
        
        if group_id:
            instructions += f"3. Add this expense to group ID {group_id}\n"
        else:
            instructions += "3. Create this expense outside of any group\n"
        
        if image_path:
            instructions += f"4. Attach the receipt image from {image_path}\n"
        
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
        group_id: Optional[str] = None,
        all_aliases: Optional[Dict[str, List[str]]] = None
    ) -> Dict:
        """Prepare expense creation with image attachment.
        
        Args:
            description: Expense description
            cost: Total cost
            participants: List of participants detected from transaction
            image_path: Path to transaction image
            group_id: Group ID (optional)
            all_aliases: Dictionary mapping canonical names to aliases (optional)
            
        Returns:
            Response dict
        """
        # First upload image
        image_url = self.upload_image(image_path)
        
        # Then create expense with alias context
        result = self.create_expense(
            description=description,
            cost=cost,
            participants=participants,
            group_id=group_id,
            image_path=image_url,
            all_aliases=all_aliases
        )
        
        return result

