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
    ) -> tuple[List[int], Dict[str, str], int]:
        """Match participant names to Splitwise friend IDs.
        
        Args:
            participants: List of detected participant names (can contain duplicates)
            all_aliases: Dictionary mapping canonical names to aliases
            
        Returns:
            Tuple of (List of friend IDs with duplicates preserved, 
                     Dict mapping participant names to friend names,
                     Number of extra shares for current user from "me" aliases)
        """
        if not participants:
            return [], {}, 0
        
        try:
            friends = self.splitwise.getFriends()
            matched_ids = []  # Can contain duplicates
            participant_to_friend = {}
            current_user_extra_shares = 0
            
            # Extract "me" aliases if present
            me_aliases = []
            if all_aliases and "me" in all_aliases:
                me_aliases = [alias.lower() for alias in all_aliases["me"]]
                logger.info(f"Found 'me' aliases: {me_aliases}")
            
            logger.info(f"Attempting to match participants: {participants}")
            logger.info(f"Available aliases: {all_aliases}")
            
            for participant in participants:
                participant_lower = participant.lower().strip()
                matched = False
                
                # First check if participant matches "me" aliases
                if me_aliases and participant_lower in me_aliases:
                    current_user_extra_shares += 1
                    participant_to_friend[participant] = "You (current user)"
                    logger.info(f"✓ Matched '{participant}' to current user via 'me' alias")
                    matched = True
                    continue
                
                # Try to match with friends
                for friend in friends:
                    friend_first = friend.getFirstName() or ""
                    friend_last = friend.getLastName() or ""
                    friend_name = f"{friend_first} {friend_last}".strip()
                    friend_name_lower = friend_name.lower()
                    
                    # Exact match with full name
                    if participant_lower == friend_name_lower:
                        matched_ids.append(friend.getId())
                        participant_to_friend[participant] = friend_name
                        logger.info(f"✓ Matched '{participant}' to {friend_name} (ID: {friend.getId()}) - exact name match")
                        matched = True
                        break
                    
                    # Partial match with first or last name
                    if participant_lower in friend_name_lower or friend_name_lower in participant_lower:
                        matched_ids.append(friend.getId())
                        participant_to_friend[participant] = friend_name
                        logger.info(f"✓ Matched '{participant}' to {friend_name} (ID: {friend.getId()}) - partial name match")
                        matched = True
                        break
                    
                    # Check aliases if provided
                    if all_aliases:
                        for canonical_name, aliases in all_aliases.items():
                            canonical_lower = canonical_name.lower()
                            
                            # Check if this friend matches the canonical name
                            if canonical_lower == friend_name_lower or canonical_lower in friend_name_lower:
                                # Now check if participant matches any alias
                                aliases_lower = [a.lower() for a in aliases]
                                if participant_lower in aliases_lower:
                                    matched_ids.append(friend.getId())
                                    participant_to_friend[participant] = friend_name
                                    logger.info(f"✓ Matched '{participant}' to {friend_name} (ID: {friend.getId()}) - alias match via '{canonical_name}'")
                                    matched = True
                                    break
                                
                                # Check if participant is a substring of any alias or vice versa
                                for alias in aliases_lower:
                                    if participant_lower in alias or alias in participant_lower:
                                        matched_ids.append(friend.getId())
                                        participant_to_friend[participant] = friend_name
                                        logger.info(f"✓ Matched '{participant}' to {friend_name} (ID: {friend.getId()}) - partial alias match")
                                        matched = True
                                        break
                    
                    if matched:
                        break
                
                if not matched:
                    # If no match found, assign share to current user
                    logger.warning(f"✗ Could not match participant '{participant}' to any Splitwise friend - assigning share to current user")
                    current_user_extra_shares += 1
                    participant_to_friend[participant] = "You (current user) - unmatched"
            
            logger.info(f"Matched {len(matched_ids)} friends: {matched_ids}")
            logger.info(f"Current user extra shares: {current_user_extra_shares}")
            logger.info(f"Participant to friend mapping: {participant_to_friend}")
            return matched_ids, participant_to_friend, current_user_extra_shares
            
        except Exception as e:
            logger.error(f"Error matching participants: {e}", exc_info=True)
            return [], {}, 0
    
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
            friend_ids, participant_mapping, current_user_extra_shares = self._match_participants_to_friends(participants, all_aliases)
            
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
            
            # Count how many shares each friend has (handles duplicates)
            from collections import Counter
            friend_share_counts = Counter(friend_ids)
            
            # Calculate total shares including current user
            # Current user gets 1 share as payer + any extra shares from "me" aliases
            current_user_shares = 1 + current_user_extra_shares
            total_shares = len(friend_ids) + current_user_shares  # Each appearance counts as 1 share
            cost_per_share = cost / total_shares
            
            # Round per-share amount to 2 decimal places
            rounded_cost_per_share = round(cost_per_share, 2)
            
            logger.info(f"Total shares: {total_shares} (current user: {current_user_shares}, friends: {len(friend_ids)})")
            if current_user_extra_shares > 0:
                logger.info(f"Current user has {current_user_extra_shares} extra share(s) from 'me' aliases")
            logger.info(f"Cost per share: ₹{rounded_cost_per_share}")
            if len(friend_share_counts) < len(friend_ids):
                logger.info(f"Duplicate friends detected. Share counts: {dict(friend_share_counts)}")
            
            # Calculate current user's share (base share + extra shares from "me" aliases)
            current_user_owed = rounded_cost_per_share * current_user_shares
            
            # Calculate total owed by friends
            friend_total_owed = 0
            unique_friends = {}
            
            for friend_id, count in friend_share_counts.items():
                friend_owed_amount = round(rounded_cost_per_share * count, 2)
                unique_friends[friend_id] = friend_owed_amount
                friend_total_owed += friend_owed_amount
                logger.info(f"Friend ID {friend_id}: {count} share(s) = ₹{friend_owed_amount}")
            
            # Calculate remainder and adjust current user's share
            remainder = cost - (current_user_owed + friend_total_owed)
            if abs(remainder) < 1.0 and remainder != 0:
                current_user_owed = round(current_user_owed + remainder, 2)
                logger.info(f"Adjusting for rounding: remainder {remainder:.2f}, current user's share: {current_user_owed:.2f}")
            elif remainder != 0:
                logger.warning(f"Large remainder {remainder:.2f}, not adjusting (may cause error)")
            
            current_user_expense.setOwedShare(str(current_user_owed))
            
            users = [current_user_expense]
            
            # Add each unique friend with their calculated share
            for friend_id, owed_amount in unique_friends.items():
                friend_expense = ExpenseUser()
                friend_expense.setId(friend_id)
                friend_expense.setPaidShare('0.00')
                friend_expense.setOwedShare(str(owed_amount))
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
                logger.error(f"Errors creating expense: {expense}\n {errors}")
                # Extract detailed error messages from SplitwiseError objects
                error_messages = []
                errors_list = errors if isinstance(errors, list) else [errors]
                for error in errors_list:
                    if hasattr(error, 'getMessage'):
                        error_messages.append(error.getMessage())
                    elif hasattr(error, 'message'):
                        error_messages.append(error.message)
                    elif hasattr(error, 'errors'):
                        error_messages.append(str(error.errors))
                    else:
                        error_messages.append(str(error))
                logger.error(f"Detailed errors: {'; '.join(error_messages)}")
                return {
                    'success': False,
                    'error': '; '.join(error_messages),
                    'errors': error_messages
                }
            
            logger.info(f"Created expense ID: {created_expense.getId()}")
            
            # Add a comment to the expense
            comment_text = (
                "This entry was added by a bot.\n"
                "Please feel free to reach out to the expense creator if you believe you are added incorrectly in this expense or if your share is wrong"
            )
            
            # Add participant mapping information if available
            if participant_mapping:
                comment_text += "\n\nParticipant name matching:"
                # Track which friend names appeared multiple times
                friend_name_counts = {}
                unmatched_count = 0
                me_alias_count = 0
                
                for detected_name, friend_name in participant_mapping.items():
                    comment_text += f"\n• '{detected_name}' → {friend_name}"
                    
                    if friend_name == "You (current user) - unmatched":
                        unmatched_count += 1
                    elif friend_name == "You (current user)":
                        me_alias_count += 1
                    else:
                        friend_name_counts[friend_name] = friend_name_counts.get(friend_name, 0) + 1
                
                # If any friend appeared multiple times, show share allocation
                duplicates_found = any(count > 1 for count in friend_name_counts.values())
                current_user_has_extra = current_user_extra_shares > 0
                
                if duplicates_found or current_user_has_extra:
                    comment_text += "\n\nShare allocation:"
                    for friend_name, count in friend_name_counts.items():
                        if count > 1:
                            comment_text += f"\n• {friend_name}: {count} shares"
                    
                    # Show current user's total shares breakdown
                    if current_user_has_extra:
                        total_current_user_shares = 1 + current_user_extra_shares
                        breakdown_parts = ["1 as payer"]
                        if me_alias_count > 0:
                            breakdown_parts.append(f"{me_alias_count} from 'me' aliases")
                        if unmatched_count > 0:
                            breakdown_parts.append(f"{unmatched_count} unmatched")
                        breakdown = " + ".join(breakdown_parts)
                        comment_text += f"\n• You (current user): {total_current_user_shares} shares ({breakdown})"
            
            try:
                self.splitwise.createComment(created_expense.getId(), comment_text)
                logger.info(f"Added comment to expense {created_expense.getId()}")
            except Exception as e:
                logger.warning(f"Failed to add comment to expense: {e}")
            
            return {
                'success': True,
                'expense_id': created_expense.getId(),
                'matched_friends': friend_ids,
                'unique_friends': list(unique_friends.keys()),
                'total_shares': total_shares,
                'share_counts': dict(friend_share_counts),
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
