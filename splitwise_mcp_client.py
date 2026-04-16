"""Splitwise client using Zapier MCP for creating expenses."""
import logging
from collections import Counter
from typing import Dict, List, Optional

from splitwise_base import SplitwiseBase

logger = logging.getLogger(__name__)


class SplitwiseMCPClient(SplitwiseBase):
    """Client for interacting with Splitwise via Zapier MCP."""

    def __init__(self, mcp_handler=None):
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
        date: Optional[str] = None,
    ) -> Dict:
        try:
            instructions = self._build_instructions(
                description, cost, participants, group_id, image_path, all_aliases, date
            )

            logger.info(f"Creating Splitwise expense: {description} - \u20b9{cost}")

            mcp_params: Dict = {
                'instructions': instructions,
                'output_hint': 'return the expense ID, the users it was split with, and any status messages',
                'description': description,
                'cost': str(cost),
            }
            if group_id:
                mcp_params['group_id'] = group_id

            return {
                'success': True,
                'mcp_params': mcp_params,
                'message': 'Expense creation request prepared for MCP',
                'instructions': instructions,
            }

        except Exception as e:
            logger.error(f"Error creating expense: {e}", exc_info=True)
            return {'success': False, 'error': str(e)}

    def get_groups(self) -> List[Dict]:
        logger.info("Getting Splitwise groups (MCP mode - not fully implemented)")
        return []

    # ── private helpers ─────────────────────────────────────────────

    def _build_instructions(
        self,
        description: str,
        cost: float,
        participants: List[str],
        group_id: Optional[str] = None,
        image_path: Optional[str] = None,
        all_aliases: Optional[Dict[str, List[str]]] = None,
        date: Optional[str] = None,
    ) -> str:
        lines = [f"Create a Splitwise expense with description '{description}' for \u20b9{cost}.", ""]

        if participants:
            lines.append(f"Detected participants from transaction: {', '.join(participants)}")
            lines.append("")

        if all_aliases:
            lines.append("Here are all known users and their aliases:")
            for canonical, aliases in all_aliases.items():
                alias_str = ', '.join(aliases) if aliases else 'no aliases'
                if canonical.lower() == "me":
                    lines.append(
                        f"  - {canonical} (aliases: {alias_str}) - SPECIAL: These refer to YOU, "
                        "the expense creator. Assign their shares to yourself."
                    )
                else:
                    lines.append(f"  - {canonical} (also known as: {alias_str})")
            lines.append("")

        step = 1
        steps = [
            "Match the detected participant names to the actual Splitwise users using the alias information above",
            "   SPECIAL: If any participant matches 'me' aliases, those shares should be assigned to YOU (the expense creator), not matched to friends",
            "   SPECIAL: If a participant cannot be matched to any Splitwise friend, assign their share to YOU (the expense creator)",
            "IMPORTANT: If the same friend appears multiple times in the detected participants, give them multiple shares proportionally",
            "   Example: If detected participants are ['John', 'Jane', 'John'], then John gets 2 shares and Jane gets 1 share",
            "   Example with 'me': If detected participants are ['amma', 'John', 'appa'] and 'me' aliases are ['amma', 'appa'],\n"
            "   then YOU get 3 shares (1 as payer + 2 from 'me' aliases) and John gets 1 share. Total = 4 shares.",
            "   Example with unmatched: If detected participants are ['UnknownPerson', 'John'] and UnknownPerson can't be matched,\n"
            "   then YOU get 2 shares (1 as payer + 1 unmatched) and John gets 1 share. Total = 3 shares.",
            "Split the expense based on share counts (including yourself as the payer with at least 1 share)",
            "IMPORTANT: Set the currency code to 'INR' (Indian Rupees) - do NOT use USD or any other currency",
        ]

        for s in steps:
            if s.startswith("   "):
                lines.append(s)
            else:
                lines.append(f"{step}. {s}")
                step += 1

        if date:
            lines.append(f"{step}. Set the expense date to {date} (ISO 8601 format)")
            step += 1

        if group_id:
            lines.append(f"{step}. Add this expense to group ID {group_id}")
        else:
            lines.append(f"{step}. Create this expense outside of any group")
        step += 1

        if image_path:
            lines.append(f"{step}. Attach the receipt image from {image_path}")
            step += 1

        # Build comment instruction
        comment_text = self._build_comment_instruction(participants, all_aliases)
        lines.append(
            f"{step}. After creating the expense, add a comment with this text "
            f"(replace [matched Splitwise friend name] placeholders with actual matched names): "
            f'"{comment_text}"'
        )

        return "\n".join(lines)

    @staticmethod
    def _build_comment_instruction(
        participants: List[str],
        all_aliases: Optional[Dict[str, List[str]]] = None,
    ) -> str:
        text = (
            "This entry was added by a bot.\\n"
            "Please feel free to reach out to the expense creator if you believe "
            "you are added incorrectly in this expense or if your share is wrong"
        )
        if not participants:
            return text

        text += "\\n\\nParticipant name matching:"

        me_aliases_lower = []
        if all_aliases and "me" in all_aliases:
            me_aliases_lower = [a.lower() for a in all_aliases["me"]]

        me_participants = []
        for p in participants:
            if me_aliases_lower and p.lower() in me_aliases_lower:
                text += f"\\n\u2022 '{p}' \u2192 You (current user)"
                me_participants.append(p)
            else:
                text += f"\\n\u2022 '{p}' \u2192 [matched Splitwise friend name OR 'You (current user) - unmatched' if no match found]"

        counts = Counter(participants)
        has_dupes = any(c > 1 for c in counts.values())
        me_count = len(me_participants)

        if has_dupes or me_count > 0:
            text += "\\n\\nShare allocation:"
            for p, c in counts.items():
                if me_aliases_lower and p.lower() in me_aliases_lower:
                    continue
                if c > 1:
                    text += f"\\n\u2022 [matched name for {p}]: {c} shares"

            if me_count > 0:
                text += f"\\n\u2022 You (current user): [total shares] shares (1 as payer + {me_count} from 'me' aliases + [N] unmatched if any)"
            else:
                text += "\\n\u2022 You (current user): [total shares] shares (1 as payer + [N] unmatched if any)"

        return text
