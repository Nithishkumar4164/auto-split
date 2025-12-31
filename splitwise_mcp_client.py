"""Splitwise client using Zapier MCP for creating expenses."""
import logging
from typing import Dict, List, Optional

from splitwise_base import SplitwiseBase

logger = logging.getLogger(__name__)


class SplitwiseMCPClient(SplitwiseBase):
    """Client for interacting with Splitwise via Zapier MCP."""
    
    def __init__(self, mcp_handler=None):
        """Initialize Splitwise MCP client.
        
        Args:
            mcp_handler: Handler for MCP tool calls (optional)
        """
        self.mcp_handler = mcp_handler
        logger.info("Initialized Splitwise MCP client")
    
    def create_expense(
        self,
        description: str,
        cost: float,
        participants: List[str],
        group_id: Optional[str] = None,
        image_path: Optional[str] = None,
        all_aliases: Optional[Dict[str, List[str]]] = None,
        date: Optional[str] = None
    ) -> Dict:
        """Create a Splitwise expense.
        
        Args:
            description: Expense description
            cost: Total cost of expense
            participants: List of participant names detected from transaction
            group_id: Splitwise group ID (optional)
            image_path: Path to image file to attach (optional)
            all_aliases: Dictionary mapping canonical names to aliases (optional)
            date: ISO 8601 formatted date string (optional, e.g., "2025-12-21T19:12:00Z")
            
        Returns:
            Response from Splitwise API
        """
        try:
            # Build instructions for MCP with alias context
            instructions = self._build_instructions(
                description, cost, participants, group_id, image_path, all_aliases, date
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
                'message': 'Expense creation request prepared for MCP',
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
        all_aliases: Optional[Dict[str, List[str]]] = None,
        date: Optional[str] = None
    ) -> str:
        """Build instructions for MCP tool call with alias context.
        
        Args:
            description: Expense description
            cost: Total cost
            participants: List of participant names detected from transaction
            group_id: Group ID (optional)
            image_path: Image path (optional)
            all_aliases: Dictionary mapping canonical names to their aliases
            date: ISO 8601 formatted date string (optional, e.g., "2025-12-21T19:12:00Z")
            
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
                if canonical_name.lower() == "me":
                    instructions += f"  - {canonical_name} (aliases: {aliases_str}) - SPECIAL: These refer to YOU, the expense creator. Assign their shares to yourself.\n"
                else:
                    instructions += f"  - {canonical_name} (also known as: {aliases_str})\n"
            instructions += "\n"
        
        # Instructions for AI to figure out users
        instructions += "Please:\n"
        instructions += "1. Match the detected participant names to the actual Splitwise users using the alias information above\n"
        instructions += "   SPECIAL: If any participant matches 'me' aliases, those shares should be assigned to YOU (the expense creator), not matched to friends\n"
        instructions += "   SPECIAL: If a participant cannot be matched to any Splitwise friend, assign their share to YOU (the expense creator)\n"
        instructions += "2. IMPORTANT: If the same friend appears multiple times in the detected participants, give them multiple shares proportionally\n"
        instructions += "   Example: If detected participants are ['John', 'Jane', 'John'], then John gets 2 shares and Jane gets 1 share\n"
        instructions += "   Example with 'me': If detected participants are ['amma', 'John', 'appa'] and 'me' aliases are ['amma', 'appa'],\n"
        instructions += "   then YOU get 3 shares (1 as payer + 2 from 'me' aliases) and John gets 1 share. Total = 4 shares.\n"
        instructions += "   Example with unmatched: If detected participants are ['UnknownPerson', 'John'] and UnknownPerson can't be matched,\n"
        instructions += "   then YOU get 2 shares (1 as payer + 1 unmatched) and John gets 1 share. Total = 3 shares.\n"
        instructions += "3. Split the expense based on share counts (including yourself as the payer with at least 1 share)\n"
        instructions += "4. IMPORTANT: Set the currency code to 'INR' (Indian Rupees) - do NOT use USD or any other currency\n"
        
        # Add date instruction if provided
        if date:
            instructions += f"5. Set the expense date to {date} (ISO 8601 format)\n"
            step_num = 6
        else:
            step_num = 5
        
        if group_id:
            instructions += f"{step_num}. Add this expense to group ID {group_id}\n"
            step_num += 1
        else:
            instructions += f"{step_num}. Create this expense outside of any group\n"
            step_num += 1
        
        if image_path:
            instructions += f"{step_num}. Attach the receipt image from {image_path}\n"
            step_num += 1
        
        # Add comment instruction as the final step with participant mapping
        comment_text = (
            "This entry was added by a bot.\\n"
            "Please feel free to reach out to the expense creator if you believe you are added incorrectly in this expense or if your share is wrong"
        )
        
        # Add participant matching information
        if participants:
            comment_text += "\\n\\nParticipant name matching:"
            
            # Check for "me" aliases
            me_aliases_lower = []
            if all_aliases and "me" in all_aliases:
                me_aliases_lower = [alias.lower() for alias in all_aliases["me"]]
            
            me_participants = []
            for participant in participants:
                if me_aliases_lower and participant.lower() in me_aliases_lower:
                    comment_text += f"\\n• '{participant}' → You (current user)"
                    me_participants.append(participant)
                else:
                    comment_text += f"\\n• '{participant}' → [matched Splitwise friend name OR 'You (current user) - unmatched' if no match found]"
            
            # Check for duplicates and add share allocation info if needed
            from collections import Counter
            participant_counts = Counter(participants)
            duplicates_found = any(count > 1 for count in participant_counts.values())
            me_count = len(me_participants)
            
            if duplicates_found or me_count > 0:
                comment_text += "\\n\\nShare allocation:"
                for participant, count in participant_counts.items():
                    if me_aliases_lower and participant.lower() in me_aliases_lower:
                        continue  # Skip "me" participants, will be shown separately
                    if count > 1:
                        comment_text += f"\\n• [matched name for {participant}]: {count} shares"
                
                # Show current user's total shares
                # Note: Include placeholders for unmatched shares in the instructions
                if me_count > 0:
                    comment_text += f"\\n• You (current user): [total shares] shares (1 as payer + {me_count} from 'me' aliases + [N] unmatched if any)"
                else:
                    comment_text += f"\\n• You (current user): [total shares] shares (1 as payer + [N] unmatched if any)"
        
        instructions += f"{step_num}. After creating the expense, add a comment with this text (replace [matched Splitwise friend name] placeholders with actual matched names): \"{comment_text}\"\n"
        
        return instructions
    
    def get_groups(self) -> List[Dict]:
        """Get list of Splitwise groups.
        
        Note: This would need to be implemented via MCP or API
        For now, returns empty list as placeholder.
        
        Returns:
            List of groups
        """
        logger.info("Getting Splitwise groups (MCP mode - not fully implemented)")
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
        all_aliases: Optional[Dict[str, List[str]]] = None,
        date: Optional[str] = None
    ) -> Dict:
        """Prepare expense creation with image attachment.
        
        Args:
            description: Expense description
            cost: Total cost
            participants: List of participants detected from transaction
            image_path: Path to transaction image
            group_id: Group ID (optional)
            all_aliases: Dictionary mapping canonical names to aliases (optional)
            date: ISO 8601 formatted date string (optional, e.g., "2025-12-21T19:12:00Z")
            
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
            all_aliases=all_aliases,
            date=date
        )
        
        return result
