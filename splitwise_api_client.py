"""Splitwise API client using the official Python SDK."""
import logging
from typing import Dict, List, Optional
from splitwise import Splitwise
from splitwise.expense import Expense
from splitwise.user import ExpenseUser

from splitwise_base import SplitwiseBase

logger = logging.getLogger(__name__)


class SplitwiseAPIClient(SplitwiseBase):
    """Client for interacting with Splitwise via the official API."""
    
    def __init__(self, consumer_key: str, consumer_secret: str, api_key: str):
        """Initialize Splitwise API client.
        
        Args:
            consumer_key: Splitwise consumer key
            consumer_secret: Splitwise consumer secret
            api_key: Splitwise API key for testing
        """
        self.splitwise = Splitwise(consumer_key, consumer_secret, api_key=api_key)
        self._current_user = None
        self._groups_cache = None
        
        logger.info("Initialized Splitwise API client")
    
    def _get_current_user(self):
        """Get current user (cached)."""
        if not self._current_user:
            try:
                self._current_user = self.splitwise.getCurrentUser()
                logger.info(f"Current user: {self._current_user.getFirstName()} {self._current_user.getLastName()}")
            except Exception as e:
                logger.error(f"Error getting current user: {e}", exc_info=True)
        return self._current_user
    
    def _match_participants_to_friends(
        self,
        participants: List[str],
        all_aliases: Optional[Dict[str, List[str]]] = None
    ) -> List[int]:
        """Match participant names to Splitwise friend IDs.
        
        Args:
            participants: List of detected participant names
            all_aliases: Dictionary mapping canonical names to aliases
            
        Returns:
            List of friend IDs
        """
        if not participants:
            return []
        
        try:
            friends = self.splitwise.getFriends()
            matched_ids = []
            
            logger.info(f"Attempting to match participants: {participants}")
            logger.info(f"Available aliases: {all_aliases}")
            
            for participant in participants:
                participant_lower = participant.lower().strip()
                matched = False
                
                # Try to match with friends
                for friend in friends:
                    friend_first = friend.getFirstName() or ""
                    friend_last = friend.getLastName() or ""
                    friend_name = f"{friend_first} {friend_last}".strip().lower()
                    
                    # Exact match with full name
                    if participant_lower == friend_name:
                        if friend.getId() not in matched_ids:
                            matched_ids.append(friend.getId())
                            logger.info(f"✓ Matched '{participant}' to {friend_first} {friend_last} (ID: {friend.getId()}) - exact name match")
                            matched = True
                        break
                    
                    # Partial match with first or last name
                    if participant_lower in friend_name or friend_name in participant_lower:
                        if friend.getId() not in matched_ids:
                            matched_ids.append(friend.getId())
                            logger.info(f"✓ Matched '{participant}' to {friend_first} {friend_last} (ID: {friend.getId()}) - partial name match")
                            matched = True
                        break
                    
                    # Check aliases if provided
                    if all_aliases:
                        for canonical_name, aliases in all_aliases.items():
                            canonical_lower = canonical_name.lower()
                            
                            # Check if this friend matches the canonical name
                            if canonical_lower == friend_name or canonical_lower in friend_name:
                                # Now check if participant matches any alias
                                aliases_lower = [a.lower() for a in aliases]
                                if participant_lower in aliases_lower:
                                    if friend.getId() not in matched_ids:
                                        matched_ids.append(friend.getId())
                                        logger.info(f"✓ Matched '{participant}' to {friend_first} {friend_last} (ID: {friend.getId()}) - alias match via '{canonical_name}'")
                                        matched = True
                                    break
                                
                                # Check if participant is a substring of any alias or vice versa
                                for alias in aliases_lower:
                                    if participant_lower in alias or alias in participant_lower:
                                        if friend.getId() not in matched_ids:
                                            matched_ids.append(friend.getId())
                                            logger.info(f"✓ Matched '{participant}' to {friend_first} {friend_last} (ID: {friend.getId()}) - partial alias match")
                                            matched = True
                                        break
                    
                    if matched:
                        break
                
                if not matched:
                    logger.warning(f"✗ Could not match participant '{participant}' to any Splitwise friend")
            
            logger.info(f"Matched {len(matched_ids)} friends: {matched_ids}")
            return matched_ids
            
        except Exception as e:
            logger.error(f"Error matching participants: {e}", exc_info=True)
            return []
    
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
        """Create a Splitwise expense using the API.
        
        Args:
            description: Expense description
            cost: Total cost of expense
            participants: List of participant names detected from transaction
            group_id: Splitwise group ID (optional)
            image_path: Path to image file to attach (optional)
            all_aliases: Dictionary mapping canonical names to aliases (optional)
            date: ISO 8601 formatted date string (optional, e.g., "2025-12-21T19:12:00Z")
            
        Returns:
            Response dict with success status and expense details
        """
        try:
            current_user = self._get_current_user()
            if not current_user:
                return {
                    'success': False,
                    'error': 'Failed to get current user'
                }
            
            # Match participants to friend IDs
            friend_ids = self._match_participants_to_friends(participants, all_aliases)
            
            # Create expense object
            expense = Expense()
            expense.setCost(str(cost))
            expense.setDescription(description)
            expense.setCurrencyCode('INR')  # Set currency to Indian Rupees by default
            
            # Set expense date if provided
            if date:
                try:
                    expense.setDate(date)
                    logger.info(f"Set expense date to: {date}")
                except Exception as e:
                    logger.warning(f"Failed to set expense date: {e}")
            
            if group_id:
                expense.setGroupId(int(group_id))
            
            # Add current user as payer
            current_user_expense = ExpenseUser()
            current_user_expense.setId(current_user.getId())
            current_user_expense.setPaidShare(str(cost))
            
            # Calculate owed share with rounding
            total_users = len(friend_ids) + 1  # Friends + current user
            owed_per_person = cost / total_users
            
            # Round each person's share to 2 decimal places
            rounded_owed_per_person = round(owed_per_person, 2)
            
            # Calculate sum of all rounded shares
            total_rounded_shares = rounded_owed_per_person * total_users
            
            # Calculate difference (remainder)
            remainder = cost - total_rounded_shares
            
            # If remainder is positive and less than 1, add it to current user's share
            current_user_owed = rounded_owed_per_person
            if 0 < remainder < 1.0:
                current_user_owed = round(current_user_owed + remainder, 2)
                logger.info(f"Adding remainder {remainder:.2f} to current user's share. New share: {current_user_owed:.2f}")
            elif remainder != 0:
                logger.debug(f"Remainder {remainder:.2f} is outside threshold (< 1), not adjusting")
            
            current_user_expense.setOwedShare(str(current_user_owed))
            
            users = [current_user_expense]
            
            # Add friends with rounded shares
            for friend_id in friend_ids:
                friend_expense = ExpenseUser()
                friend_expense.setId(friend_id)
                friend_expense.setPaidShare('0.00')
                friend_expense.setOwedShare(str(rounded_owed_per_person))
                users.append(friend_expense)
            
            expense.setUsers(users)
            
            # Set receipt if provided
            if image_path:
                try:
                    expense.setReceipt(image_path)
                    logger.info(f"Added receipt: {image_path}")
                except Exception as e:
                    logger.warning(f"Failed to add receipt: {e}")
            
            # Create the expense
            created_expense, errors = self.splitwise.createExpense(expense)
            
            if errors:
                logger.error(f"Errors creating expense: {errors}")
                # Convert SplitwiseError objects to strings for JSON serialization
                error_messages = [str(error) for error in errors] if isinstance(errors, list) else [str(errors)]
                return {
                    'success': False,
                    'error': '; '.join(error_messages),
                    'errors': error_messages
                }
            
            logger.info(f"Created expense ID: {created_expense.getId()}")
            
            return {
                'success': True,
                'expense_id': created_expense.getId(),
                'matched_friends': friend_ids,
                'total_users': total_users,
                'message': 'Expense created successfully via API'
            }
            
        except Exception as e:
            logger.error(f"Error creating expense: {e}", exc_info=True)
            return {
                'success': False,
                'error': str(e)
            }
    
    def get_groups(self) -> List[Dict]:
        """Get list of Splitwise groups.
        
        Returns:
            List of groups
        """
        if self._groups_cache:
            return self._groups_cache
        
        try:
            groups = self.splitwise.getGroups()
            self._groups_cache = [
                {
                    'id': str(group.getId()),
                    'name': group.getName()
                }
                for group in groups
            ]
            logger.info(f"Retrieved {len(self._groups_cache)} groups")
            return self._groups_cache
            
        except Exception as e:
            logger.error(f"Error getting groups: {e}", exc_info=True)
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
                logger.info(f"Found group '{group_name}' with ID {group['id']}")
                return group['id']
        
        logger.warning(f"Group '{group_name}' not found")
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
        # For API, we can directly create expense with image
        return self.create_expense(
            description=description,
            cost=cost,
            participants=participants,
            group_id=group_id,
            image_path=image_path,
            all_aliases=all_aliases,
            date=date
        )
