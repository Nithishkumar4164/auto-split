"""Splitwise API client using the official Python SDK."""
import logging
from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

from splitwise import Splitwise
from splitwise.expense import Expense
from splitwise.user import ExpenseUser

from splitwise_base import SplitwiseBase

logger = logging.getLogger(__name__)


class SplitwiseAPIClient(SplitwiseBase):
    """Client for interacting with Splitwise via the official API."""

    def __init__(self, consumer_key: str, consumer_secret: str, api_key: str):
        self.splitwise = Splitwise(consumer_key, consumer_secret, api_key=api_key)
        self._current_user = None
        self._groups_cache = None
        logger.info("Initialized Splitwise API client")

    def _get_current_user(self):
        if not self._current_user:
            try:
                self._current_user = self.splitwise.getCurrentUser()
                logger.info(
                    f"Current user: {self._current_user.getFirstName()} "
                    f"{self._current_user.getLastName()}"
                )
            except Exception as e:
                logger.error(f"Error getting current user: {e}", exc_info=True)
        return self._current_user

    def _match_participants_to_friends(
        self,
        participants: List[str],
        all_aliases: Optional[Dict[str, List[str]]] = None,
    ) -> tuple[List[int], Dict[str, str], int]:
        """Match participant names to Splitwise friend IDs.

        Returns (friend_ids_with_dupes, participant_to_friend_map, current_user_extra_shares).
        """
        if not participants:
            return [], {}, 0

        try:
            friends = self.splitwise.getFriends()
            matched_ids: List[int] = []
            participant_to_friend: Dict[str, str] = {}
            current_user_extra_shares = 0

            me_aliases = []
            if all_aliases and "me" in all_aliases:
                me_aliases = [a.lower() for a in all_aliases["me"]]
                logger.info(f"Found 'me' aliases: {me_aliases}")

            logger.info(f"Attempting to match participants: {participants}")

            for participant in participants:
                participant_lower = participant.lower().strip()
                matched = False

                # Check "me" aliases first
                if me_aliases and participant_lower in me_aliases:
                    current_user_extra_shares += 1
                    participant_to_friend[participant] = "You (current user)"
                    logger.info(f"Matched '{participant}' to current user via 'me' alias")
                    continue

                for friend in friends:
                    friend_first = friend.getFirstName() or ""
                    friend_last = friend.getLastName() or ""
                    friend_name = f"{friend_first} {friend_last}".strip()
                    friend_name_lower = friend_name.lower()

                    # Exact match
                    if participant_lower == friend_name_lower:
                        matched_ids.append(friend.getId())
                        participant_to_friend[participant] = friend_name
                        matched = True
                        break

                    # Partial match
                    if participant_lower in friend_name_lower or friend_name_lower in participant_lower:
                        matched_ids.append(friend.getId())
                        participant_to_friend[participant] = friend_name
                        matched = True
                        break

                    # Alias match
                    if all_aliases:
                        for canonical_name, aliases in all_aliases.items():
                            canonical_lower = canonical_name.lower()
                            if canonical_lower == friend_name_lower or canonical_lower in friend_name_lower:
                                aliases_lower = [a.lower() for a in aliases]
                                if participant_lower in aliases_lower:
                                    matched_ids.append(friend.getId())
                                    participant_to_friend[participant] = friend_name
                                    matched = True
                                    break
                                for alias in aliases_lower:
                                    if participant_lower in alias or alias in participant_lower:
                                        matched_ids.append(friend.getId())
                                        participant_to_friend[participant] = friend_name
                                        matched = True
                                        break
                        if matched:
                            break

                if not matched:
                    current_user_extra_shares += 1
                    participant_to_friend[participant] = "You (current user) - unmatched"
                    logger.warning(f"Could not match '{participant}' - assigning to current user")

            logger.info(f"Matched {len(matched_ids)} friends, extra user shares: {current_user_extra_shares}")
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
        date: Optional[str] = None,
    ) -> Dict:
        try:
            current_user = self._get_current_user()
            if not current_user:
                return {'success': False, 'error': 'Failed to get current user'}

            friend_ids, participant_mapping, extra_shares = self._match_participants_to_friends(
                participants, all_aliases
            )

            expense = Expense()
            expense.setCost(str(cost))
            expense.setDescription(description)
            expense.setCurrencyCode('INR')

            if date:
                try:
                    expense.setDate(date)
                except Exception as e:
                    logger.warning(f"Failed to set expense date: {e}")

            if group_id:
                expense.setGroupId(int(group_id))

            # Build share counts
            friend_share_counts = Counter(friend_ids)
            current_user_shares = 1 + extra_shares
            total_shares = len(friend_ids) + current_user_shares
            rounded_per_share = round(cost / total_shares, 2)

            logger.info(f"Total shares: {total_shares} (user: {current_user_shares}, friends: {len(friend_ids)})")

            # Current user
            current_user_expense = ExpenseUser()
            current_user_expense.setId(current_user.getId())
            current_user_expense.setPaidShare(str(cost))

            current_user_owed = rounded_per_share * current_user_shares

            # Friends
            unique_friends: Dict[int, float] = {}
            friend_total_owed = 0
            for fid, count in friend_share_counts.items():
                owed = round(rounded_per_share * count, 2)
                unique_friends[fid] = owed
                friend_total_owed += owed

            # Absorb rounding remainder into current user's share
            remainder = cost - (current_user_owed + friend_total_owed)
            if abs(remainder) < 1.0 and remainder != 0:
                current_user_owed = round(current_user_owed + remainder, 2)

            current_user_expense.setOwedShare(str(current_user_owed))

            users = [current_user_expense]
            for fid, owed in unique_friends.items():
                eu = ExpenseUser()
                eu.setId(fid)
                eu.setPaidShare('0.00')
                eu.setOwedShare(str(owed))
                users.append(eu)

            expense.setUsers(users)

            if image_path:
                try:
                    expense.setReceipt(image_path)
                except Exception as e:
                    logger.warning(f"Failed to add receipt: {e}")

            created_expense, errors = self.splitwise.createExpense(expense)

            if errors:
                error_messages = []
                for err in (errors if isinstance(errors, list) else [errors]):
                    if hasattr(err, 'getMessage'):
                        error_messages.append(err.getMessage())
                    elif hasattr(err, 'message'):
                        error_messages.append(err.message)
                    elif hasattr(err, 'errors'):
                        error_messages.append(str(err.errors))
                    else:
                        error_messages.append(str(err))
                logger.error(f"Errors creating expense: {'; '.join(error_messages)}")
                return {'success': False, 'error': '; '.join(error_messages), 'errors': error_messages}

            logger.info(f"Created expense ID: {created_expense.getId()}")

            # Add bot comment
            comment = self.build_bot_comment(participant_mapping, extra_shares)
            try:
                self.splitwise.createComment(created_expense.getId(), comment)
            except Exception as e:
                logger.warning(f"Failed to add comment: {e}")

            return {
                'success': True,
                'expense_id': created_expense.getId(),
                'matched_friends': friend_ids,
                'unique_friends': list(unique_friends.keys()),
                'total_shares': total_shares,
                'share_counts': dict(friend_share_counts),
                'message': 'Expense created successfully via API',
            }

        except Exception as e:
            logger.error(f"Error creating expense: {e}", exc_info=True)
            return {'success': False, 'error': str(e)}

    def get_groups(self) -> List[Dict]:
        if self._groups_cache:
            return self._groups_cache
        try:
            groups = self.splitwise.getGroups()
            cutoff = datetime.now(timezone.utc) - timedelta(days=30)
            self._groups_cache = []
            for g in groups:
                try:
                    balances = g.getBalances() or []
                    has_balance = any(abs(float(b.getAmount())) > 0.01 for b in balances)
                except (AttributeError, TypeError, ValueError):
                    has_balance = False
                try:
                    updated_at = datetime.fromisoformat(g.getUpdatedAt().replace('Z', '+00:00'))
                    recently_active = updated_at >= cutoff
                except (AttributeError, TypeError, ValueError):
                    recently_active = False
                is_active = has_balance or recently_active
                self._groups_cache.append({'id': str(g.getId()), 'name': g.getName(), 'active': is_active})
            logger.info(f"Retrieved {len(self._groups_cache)} groups")
            return self._groups_cache
        except Exception as e:
            logger.error(f"Error getting groups: {e}", exc_info=True)
            return []
