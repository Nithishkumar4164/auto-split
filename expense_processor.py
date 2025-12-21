"""Main expense processor that orchestrates the entire workflow."""
import logging
import os
import requests
from typing import Dict, Optional
from pathlib import Path

from image_parser import ImageParser, TransactionDetails
from alias_manager import AliasManager
from utr_tracker import UTRTracker
from splitwise_client import SplitwiseClient
from drive_handler import DriveHandler
from config import Config

logger = logging.getLogger(__name__)

# Try to import GCS client (optional dependency)
try:
    from google.cloud import storage
    from google.oauth2 import service_account
    GCS_AVAILABLE = True
except ImportError:
    GCS_AVAILABLE = False
    logger.warning("Google Cloud Storage client not available. GCS event processing will use mediaLink.")


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
        
        Args:
            transaction: Transaction details
            
        Returns:
            Expense description
        """
        # Use message if available, otherwise use recipient
        if transaction.message:
            return transaction.message
        elif transaction.recipient:
            return f"Payment to {transaction.recipient}"
        else:
            return f"Transaction - ₹{transaction.amount}"
    
    def process_drive_event(self, event_data: Dict) -> Dict:
        """Process Google Drive or GCS upload event.
        
        Args:
            event_data: Event data from Cloud Run (can be Drive or GCS event)
            
        Returns:
            Processing result dict
        """
        try:
            # Check if this is a GCS event (has 'bucket' and 'kind' fields)
            if event_data.get('kind') == 'storage#object' and event_data.get('bucket'):
                return self._process_gcs_event(event_data)
            
            # Otherwise, treat as Drive event
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
    
    def _process_gcs_event(self, event_data: Dict) -> Dict:
        """Process Google Cloud Storage upload event.
        
        Args:
            event_data: GCS object event data
            
        Returns:
            Processing result dict
        """
        try:
            bucket_name = event_data.get('bucket')
            file_name = event_data.get('name')
            media_link = event_data.get('mediaLink')
            
            if not bucket_name or not file_name:
                logger.warning("Missing bucket or name in GCS event")
                return {
                    'success': False,
                    'error': 'Missing bucket or name in GCS event'
                }
            
            logger.info(f"Processing GCS event: gs://{bucket_name}/{file_name}")
            
            # Check if it's an image file
            if not self._is_image_file(file_name):
                logger.info(f"Skipping non-image file: {file_name}")
                return {
                    'success': False,
                    'error': f'Not an image file: {file_name}'
                }
            
            # Parse path to get group name
            # Expected format: "Test Group/TransactionReceipt...jpeg"
            group_name = self._parse_gcs_path(file_name)
            logger.info(f"Extracted group name: {group_name}")
            
            # Download file to temporary location
            temp_dir = Path('/tmp/autosplit')
            temp_dir.mkdir(exist_ok=True)
            
            local_file_name = Path(file_name).name
            local_path = temp_dir / local_file_name
            
            # Download from GCS
            if not self._download_from_gcs(bucket_name, file_name, str(local_path), media_link):
                return {
                    'success': False,
                    'error': f'Failed to download file from GCS: gs://{bucket_name}/{file_name}'
                }
            
            # Process the image
            result = self.process_image(str(local_path), group_name)
            
            # Clean up temporary file
            if local_path.exists():
                local_path.unlink()
            
            return result
            
        except Exception as e:
            logger.error(f"Error processing GCS event: {e}", exc_info=True)
            return {
                'success': False,
                'error': str(e)
            }
    
    def _parse_gcs_path(self, file_path: str) -> Optional[str]:
        """Parse GCS file path to extract group name.
        
        Expected format: "Test Group/TransactionReceipt...jpeg"
        or: "TransactionReceipt...jpeg" (for non-group expenses)
        
        Args:
            file_path: Full file path in GCS
            
        Returns:
            Group name or None
        """
        parts = Path(file_path).parts
        
        # If only 1 part: filename only (no group)
        if len(parts) == 1:
            return None
        
        # If 2+ parts: GroupName/filename.jpeg
        if len(parts) >= 2:
            return parts[0]
        
        return None
    
    def _is_image_file(self, filename: str) -> bool:
        """Check if file is an image.
        
        Args:
            filename: File name
            
        Returns:
            True if image file, False otherwise
        """
        image_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.bmp']
        ext = Path(filename).suffix.lower()
        return ext in image_extensions
    
    def _download_from_gcs(self, bucket_name: str, blob_name: str, destination_path: str, media_link: Optional[str] = None) -> bool:
        """Download file from Google Cloud Storage.
        
        Args:
            bucket_name: GCS bucket name
            blob_name: GCS blob (file) name
            destination_path: Local path to save file
            media_link: Optional mediaLink URL for direct download
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Use GCS client with proper authentication (preferred method)
            if GCS_AVAILABLE:
                try:
                    # Initialize storage client with service account credentials if available
                    credentials_path = Config.GOOGLE_APPLICATION_CREDENTIALS
                    if credentials_path and os.path.exists(credentials_path):
                        logger.info(f"Using service account credentials from: {credentials_path}")
                        credentials = service_account.Credentials.from_service_account_file(
                            credentials_path,
                            scopes=['https://www.googleapis.com/auth/cloud-platform']
                        )
                        storage_client = storage.Client(credentials=credentials, project=Config.GOOGLE_CLOUD_PROJECT)
                    else:
                        # Use default credentials (Application Default Credentials)
                        # In Cloud Run, this will use the attached service account automatically
                        # In local dev, this will use gcloud auth application-default login credentials
                        logger.info("Using Application Default Credentials (ADC)")
                        storage_client = storage.Client(project=Config.GOOGLE_CLOUD_PROJECT)
                    
                    bucket = storage_client.bucket(bucket_name)
                    blob = bucket.blob(blob_name)
                    
                    # Create directories if needed
                    os.makedirs(os.path.dirname(destination_path), exist_ok=True)
                    
                    # Download the file
                    blob.download_to_filename(destination_path)
                    
                    logger.info(f"Downloaded gs://{bucket_name}/{blob_name} to {destination_path}")
                    return True
                except Exception as e:
                    logger.error(f"Error downloading from GCS client: {e}", exc_info=True)
                    # Fall through to try mediaLink if available
                    if not media_link:
                        return False
            
            # Fallback: Try using mediaLink with authenticated request
            if media_link:
                try:
                    logger.info(f"Downloading from mediaLink: {media_link}")
                    
                    # If we have credentials, use them to authenticate the request
                    if GCS_AVAILABLE and Config.GOOGLE_APPLICATION_CREDENTIALS and os.path.exists(Config.GOOGLE_APPLICATION_CREDENTIALS):
                        credentials = service_account.Credentials.from_service_account_file(
                            Config.GOOGLE_APPLICATION_CREDENTIALS,
                            scopes=['https://www.googleapis.com/auth/cloud-platform']
                        )
                        # Refresh credentials to get access token
                        credentials.refresh(requests.Request())
                        # Add authorization header
                        headers = {'Authorization': f'Bearer {credentials.token}'}
                        response = requests.get(media_link, headers=headers, timeout=30)
                    else:
                        # Try without auth (may work if bucket is public or using default credentials)
                        response = requests.get(media_link, timeout=30)
                    
                    response.raise_for_status()
                    
                    # Create directories if needed
                    os.makedirs(os.path.dirname(destination_path), exist_ok=True)
                    
                    with open(destination_path, 'wb') as f:
                        f.write(response.content)
                    
                    logger.info(f"Downloaded from mediaLink to {destination_path}")
                    return True
                except Exception as e:
                    logger.error(f"Failed to download from mediaLink: {e}", exc_info=True)
                    return False
            
            logger.error("GCS client not available and no mediaLink provided")
            return False
                
        except Exception as e:
            logger.error(f"Error downloading from GCS: {e}", exc_info=True)
            return False

