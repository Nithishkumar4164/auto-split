"""Base class for Splitwise integrations."""
from abc import ABC, abstractmethod
from typing import Dict, List, Optional


class SplitwiseBase(ABC):
    """Abstract base class for Splitwise integrations.

    Concrete subclasses must implement create_expense and get_groups.
    find_group_by_name has a default implementation that works for both modes.
    """

    @abstractmethod
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
        """Create a Splitwise expense."""

    @abstractmethod
    def get_groups(self) -> List[Dict]:
        """Return list of {'id': str, 'name': str} dicts."""

    def find_group_by_name(self, group_name: str) -> Optional[str]:
        """Find group ID by name (case-insensitive)."""
        import logging
        logger = logging.getLogger(__name__)

        logger.info(f"Finding group: {group_name}")
        groups = self.get_groups()
        for group in groups:
            if group.get('name', '').lower() == group_name.lower():
                logger.info(f"Found group '{group_name}' with ID {group['id']}")
                return group['id']
        logger.warning(f"Group '{group_name}' not found")
        return None

    @staticmethod
    def build_bot_comment(participant_mapping: Optional[Dict[str, str]] = None,
                          current_user_extra_shares: int = 0) -> str:
        """Build the standard bot comment text appended to every expense."""
        comment = (
            "This entry was added by a bot.\n"
            "Please feel free to reach out to the expense creator if you "
            "believe you are added incorrectly in this expense or if your share is wrong"
        )

        if not participant_mapping:
            return comment

        comment += "\n\nParticipant name matching:"
        friend_name_counts: Dict[str, int] = {}
        unmatched_count = 0
        me_alias_count = 0

        for detected_name, friend_name in participant_mapping.items():
            comment += f"\n\u2022 '{detected_name}' \u2192 {friend_name}"
            if friend_name == "You (current user) - unmatched":
                unmatched_count += 1
            elif friend_name == "You (current user)":
                me_alias_count += 1
            else:
                friend_name_counts[friend_name] = friend_name_counts.get(friend_name, 0) + 1

        duplicates_found = any(c > 1 for c in friend_name_counts.values())
        if duplicates_found or current_user_extra_shares > 0:
            comment += "\n\nShare allocation:"
            for fn, count in friend_name_counts.items():
                if count > 1:
                    comment += f"\n\u2022 {fn}: {count} shares"
            if current_user_extra_shares > 0:
                total = 1 + current_user_extra_shares
                parts = ["1 as payer"]
                if me_alias_count > 0:
                    parts.append(f"{me_alias_count} from 'me' aliases")
                if unmatched_count > 0:
                    parts.append(f"{unmatched_count} unmatched")
                comment += f"\n\u2022 You (current user): {total} shares ({' + '.join(parts)})"

        return comment
