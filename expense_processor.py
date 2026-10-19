"""Main expense processor that orchestrates the entire workflow."""
import logging
from typing import Dict, Optional

from image_parser import ImageParser, TransactionDetails
from alias_manager import AliasManager
from utr_tracker import UTRTracker
from splitwise_base import SplitwiseBase
from config import Config

logger = logging.getLogger(__name__)


class ExpenseProcessor:
    """Processor for creating Splitwise expenses from transaction images."""

    def __init__(
        self,
        image_parser: ImageParser,
        alias_manager: AliasManager,
        utr_tracker: UTRTracker,
        splitwise_client: SplitwiseBase,
    ):
        self.image_parser = image_parser
        self.alias_manager = alias_manager
        self.utr_tracker = utr_tracker
        self.splitwise_client = splitwise_client

    def process(self, image_path: str, group_name: Optional[str] = None) -> Dict:
        """Process a local transaction image and create a Splitwise expense."""
        try:
            logger.info(f"Processing image: {image_path}")

            # 1. Parse image
            transaction = self.image_parser.parse_image(image_path)

            if not transaction.is_valid():
                return {
                    'success': False,
                    'error': 'Invalid transaction details - missing amount or UTR',
                    'transaction': transaction.to_dict(),
                }

            logger.info(f"Parsed transaction: {transaction}")

            # 2. Duplicate check
            if transaction.utr and self.utr_tracker.is_processed(transaction.utr):
                existing_info = self.utr_tracker.get_utr_info(transaction.utr)
                logger.warning(f"UTR {transaction.utr} already processed")
                if Config.REJECT_DUPLICATE_UTR:
                    return {
                        'success': False,
                        'error': 'Duplicate transaction - UTR already processed',
                        'utr': transaction.utr,
                        'existing_expense': existing_info,
                    }
                logger.info("REJECT_DUPLICATE_UTR is disabled, continuing despite duplicate UTR")

            # 3. Participants
            detected_participants = transaction.participants or []
            if detected_participants:
                logger.info(f"Detected participants: {detected_participants}")
            else:
                logger.warning("No participants found in transaction message")

            # 4. Alias context
            all_aliases = self.alias_manager.aliases
            logger.debug(f"Available aliases: {all_aliases}")

            # 5. Description
            description = self._build_expense_description(transaction)

            # 6. Group lookup
            group_id = None
            if group_name:
                group_id = self.splitwise_client.find_group_by_name(group_name)
                if not group_id:
                    logger.warning(f"Group not found: {group_name}")

            # 7. Create expense
            expense_result = self.splitwise_client.create_expense(
                description=description,
                cost=transaction.amount,
                participants=detected_participants,
                image_path=image_path,
                group_id=group_id,
                all_aliases=all_aliases,
                date=transaction.date,
            )

            if not expense_result.get('success'):
                return {
                    'success': False,
                    'error': 'Failed to create Splitwise expense',
                    'details': expense_result,
                }

            # 8. Record UTR
            expense_id = expense_result.get('expense_id')
            self.utr_tracker.add_utr(
                utr=transaction.utr,
                amount=transaction.amount,
                expense_id=expense_id,
                group_name=group_name,
                participants=detected_participants,
            )

            logger.info(f"Successfully created expense for UTR {transaction.utr}")

            return {
                'success': True,
                'transaction': transaction.to_dict(),
                'detected_participants': detected_participants,
                'group_name': group_name,
                'expense_id': expense_id,
                'description': description,
                'mcp_instructions': expense_result.get('instructions'),
            }

        except Exception as e:
            logger.error(f"Error processing image: {e}", exc_info=True)
            return {'success': False, 'error': str(e)}

    @staticmethod
    def _build_expense_description(transaction: TransactionDetails) -> str:
        if transaction.message:
            if '-' in transaction.message:
                title = transaction.message.split('-', 1)[0].strip()
                return title if title else transaction.message
            return transaction.message
        elif transaction.recipient:
            return f"Payment to {transaction.recipient}"
        else:
            return f"Transaction - ₹{transaction.amount}"
