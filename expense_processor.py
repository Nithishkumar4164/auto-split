"""Main expense processor that orchestrates the entire workflow."""
import logging
from typing import Dict, Optional
from pathlib import Path

from image_parser import ImageParser, TransactionDetails
from alias_manager import AliasManager
from utr_tracker import UTRTracker
from splitwise_client import SplitwiseClient
from drive_handler import DriveHandler

logger = logging.getLogger(__name__)


class ExpenseProcessor:
    """Processor for creating Splitwise expenses from transaction images."""
    
    def __init__(
        self,
        image_parser: ImageParser,
        alias_manager: AliasManager,
        utr_tracker: UTRTracker,
        splitwise_client: SplitwiseClient,
        drive_handler: DriveHandler
    ):
        """Initialize expense processor.
        
        Args:
            image_parser: Image parser instance
            alias_manager: Alias manager instance
            utr_tracker: UTR tracker instance
            splitwise_client: Splitwise client instance
            drive_handler: Drive handler instance
        """
        self.image_parser = image_parser
        self.alias_manager = alias_manager
        self.utr_tracker = utr_tracker
        self.splitwise_client = splitwise_client
        self.drive_handler = drive_handler
    
    def process_image(
        self,
        image_path: str,
        group_name: Optional[str] = None
    ) -> Dict:
        """Process a transaction image and create Splitwise expense.
        
        Args:
            image_path: Path to transaction image
            group_name: Splitwise group name (optional)
            
        Returns:
            Processing result dict
        """
        try:
            logger.info(f"Processing image: {image_path}")
            
            # Step 1: Parse image to extract transaction details
            transaction = self.image_parser.parse_image(image_path)
            
            if not transaction.is_valid():
                return {
                    'success': False,
                    'error': 'Invalid transaction details - missing amount or UTR',
                    'transaction': transaction.to_dict()
                }
            
            logger.info(f"Parsed transaction: {transaction}")
            
            # Step 2: Check if UTR already processed
            if transaction.utr and self.utr_tracker.is_processed(transaction.utr):
                existing_info = self.utr_tracker.get_utr_info(transaction.utr)
                logger.warning(f"UTR {transaction.utr} already processed")
                return {
                    'success': False,
                    'error': 'Duplicate transaction - UTR already processed',
                    'utr': transaction.utr,
                    'existing_expense': existing_info
                }
            
            # Step 3: Get detected participants (don't match yet, let MCP do it)
            detected_participants = transaction.participants if transaction.participants else []
            
            if detected_participants:
                logger.info(f"Detected participants: {detected_participants}")
            else:
                logger.warning("No participants found in transaction message")
            
            # Step 4: Get all aliases to provide context to MCP
            all_aliases = self.alias_manager.aliases
            logger.debug(f"Available aliases: {all_aliases}")
            
            # Step 5: Determine expense description
            description = self._build_expense_description(transaction)
            
            # Step 6: Find group ID if group name provided
            group_id = None
            if group_name:
                group_id = self.splitwise_client.find_group_by_name(group_name)
                if not group_id:
                    logger.warning(f"Group not found: {group_name}")
            
            # Step 7: Create Splitwise expense (MCP will match participants using aliases)
            expense_result = self.splitwise_client.prepare_expense_with_image(
                description=description,
                cost=transaction.amount,
                participants=detected_participants,
                image_path=image_path,
                group_id=group_id,
                all_aliases=all_aliases
            )
            
            if not expense_result.get('success'):
                return {
                    'success': False,
                    'error': 'Failed to create Splitwise expense',
                    'details': expense_result
                }
            
            # Step 8: Record UTR as processed
            expense_id = expense_result.get('expense_id')
            self.utr_tracker.add_utr(
                utr=transaction.utr,
                amount=transaction.amount,
                expense_id=expense_id,
                group_name=group_name,
                participants=detected_participants
            )
            
            logger.info(f"Successfully created expense for UTR {transaction.utr}")
            
            return {
                'success': True,
                'transaction': transaction.to_dict(),
                'detected_participants': detected_participants,
                'group_name': group_name,
                'expense_id': expense_id,
                'description': description,
                'mcp_instructions': expense_result.get('instructions')
            }
            
        except Exception as e:
            logger.error(f"Error processing image: {e}", exc_info=True)
            return {
                'success': False,
                'error': str(e)
            }
    
    def _build_expense_description(self, transaction: TransactionDetails) -> str:
        """Build expense description from transaction details.
        
        Format: If message is "ExpenseTitle- participants", use just "ExpenseTitle"
        
        Args:
            transaction: Transaction details
            
        Returns:
            Expense description
        """
        # Use message if available, otherwise use recipient
        if transaction.message:
            # If message has dash separator (ExpenseTitle- participants), use only the title part
            if '-' in transaction.message:
                title = transaction.message.split('-', 1)[0].strip()
                logger.debug(f"Extracted expense title: '{title}'")
                return title
            # Otherwise use full message
            return transaction.message
        elif transaction.recipient:
            return f"Payment to {transaction.recipient}"
        else:
            return f"Transaction - ₹{transaction.amount}"
    
    def process_drive_event(self, event_data: Dict) -> Dict:
        """Process Google Drive upload event.
        
        Args:
            event_data: Event data from Cloud Run
            
        Returns:
            Processing result dict
        """
        try:
            # Process the drive event
            processed_event = self.drive_handler.process_drive_event(event_data)
            
            if not processed_event:
                return {
                    'success': False,
                    'error': 'Failed to process drive event'
                }
            
            file_id = processed_event['file_id']
            file_name = processed_event['file_name']
            group_name = processed_event['group_name']
            
            logger.info(f"Processing file: {file_name}, group: {group_name}")
            
            # Download file to temporary location
            temp_dir = Path('/tmp/autosplit')
            temp_dir.mkdir(exist_ok=True)
            
            local_path = temp_dir / file_name
            
            if not self.drive_handler.download_file(file_id, str(local_path)):
                return {
                    'success': False,
                    'error': 'Failed to download file from Drive'
                }
            
            # Process the image
            result = self.process_image(str(local_path), group_name)
            
            # Clean up temporary file
            if local_path.exists():
                local_path.unlink()
            
            return result
            
        except Exception as e:
            logger.error(f"Error processing drive event: {e}", exc_info=True)
            return {
                'success': False,
                'error': str(e)
            }

