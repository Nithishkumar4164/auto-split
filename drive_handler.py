"""Google Drive handler for monitoring and processing uploaded images."""
import os
import logging
from typing import Dict, Optional, Tuple
from pathlib import Path
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
import io

logger = logging.getLogger(__name__)


class DriveHandler:
    """Handler for Google Drive operations."""
    
    def __init__(self, credentials_path: Optional[str] = None):
        """Initialize Drive handler.
        
        Args:
            credentials_path: Path to service account credentials JSON
        """
        self.credentials_path = credentials_path or os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
        self.service = None
        
        if self.credentials_path and os.path.exists(self.credentials_path):
            self._initialize_service()
    
    def _initialize_service(self):
        """Initialize Google Drive API service."""
        try:
            credentials = service_account.Credentials.from_service_account_file(
                self.credentials_path,
                scopes=['https://www.googleapis.com/auth/drive.readonly']
            )
            self.service = build('drive', 'v3', credentials=credentials)
            logger.info("Google Drive service initialized")
        except Exception as e:
            logger.error(f"Error initializing Drive service: {e}")
    
    def parse_file_path(self, file_path: str) -> Tuple[Optional[str], Optional[str]]:
        """Parse file path to extract group name.
        
        Expected format: Splitwise/GroupName/image.jpeg
        or: Splitwise/image.jpeg (for non-group expenses)
        
        Args:
            file_path: Full file path in Drive
            
        Returns:
            Tuple of (group_name, file_name)
        """
        parts = Path(file_path).parts
        
        # Check if path starts with Splitwise
        if not parts or parts[0] != 'Splitwise':
            logger.warning(f"Invalid path format: {file_path}")
            return None, None
        
        # If only 2 parts: Splitwise/image.jpeg (no group)
        if len(parts) == 2:
            return None, parts[1]
        
        # If 3 parts: Splitwise/GroupName/image.jpeg
        if len(parts) == 3:
            return parts[1], parts[2]
        
        logger.warning(f"Unexpected path format: {file_path}")
        return None, None
    
    def download_file(self, file_id: str, destination_path: str) -> bool:
        """Download file from Google Drive.
        
        Args:
            file_id: Google Drive file ID
            destination_path: Local path to save file
            
        Returns:
            True if successful, False otherwise
        """
        if not self.service:
            logger.error("Drive service not initialized")
            return False
        
        try:
            request = self.service.files().get_media(fileId=file_id)
            
            # Create directories if needed
            os.makedirs(os.path.dirname(destination_path), exist_ok=True)
            
            with io.FileIO(destination_path, 'wb') as fh:
                downloader = MediaIoBaseDownload(fh, request)
                done = False
                while not done:
                    status, done = downloader.next_chunk()
                    logger.debug(f"Download {int(status.progress() * 100)}%")
            
            logger.info(f"Downloaded file to {destination_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error downloading file {file_id}: {e}")
            return False
    
    def get_file_info(self, file_id: str) -> Optional[Dict]:
        """Get file information from Drive.
        
        Args:
            file_id: Google Drive file ID
            
        Returns:
            File metadata dict or None
        """
        if not self.service:
            logger.error("Drive service not initialized")
            return None
        
        try:
            file_info = self.service.files().get(
                fileId=file_id,
                fields='id,name,mimeType,parents,createdTime,modifiedTime'
            ).execute()
            
            logger.info(f"Retrieved file info: {file_info.get('name')}")
            return file_info
            
        except Exception as e:
            logger.error(f"Error getting file info {file_id}: {e}")
            return None
    
    def get_file_path(self, file_id: str) -> Optional[str]:
        """Get full file path in Drive.
        
        Args:
            file_id: Google Drive file ID
            
        Returns:
            Full file path or None
        """
        if not self.service:
            logger.error("Drive service not initialized")
            return None
        
        try:
            path_parts = []
            current_id = file_id
            
            while current_id:
                file_info = self.service.files().get(
                    fileId=current_id,
                    fields='id,name,parents'
                ).execute()
                
                path_parts.insert(0, file_info['name'])
                
                # Get parent
                parents = file_info.get('parents', [])
                if parents:
                    current_id = parents[0]
                else:
                    break
            
            full_path = '/'.join(path_parts)
            logger.info(f"File path: {full_path}")
            return full_path
            
        except Exception as e:
            logger.error(f"Error getting file path {file_id}: {e}")
            return None
    
    def is_image_file(self, filename: str) -> bool:
        """Check if file is an image.
        
        Args:
            filename: File name
            
        Returns:
            True if image file, False otherwise
        """
        image_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.bmp']
        ext = Path(filename).suffix.lower()
        return ext in image_extensions
    
    def process_drive_event(self, event_data: Dict) -> Optional[Dict]:
        """Process Google Drive event.
        
        Args:
            event_data: Event data from Cloud Run
            
        Returns:
            Processed event dict or None
        """
        try:
            # Extract file information from event
            file_id = event_data.get('id')
            file_name = event_data.get('name')
            
            if not file_id or not file_name:
                logger.warning("Missing file ID or name in event")
                return None
            
            # Check if it's an image file
            if not self.is_image_file(file_name):
                logger.info(f"Skipping non-image file: {file_name}")
                return None
            
            # Get full file path
            file_path = self.get_file_path(file_id)
            
            if not file_path:
                logger.warning(f"Could not determine file path for {file_id}")
                return None
            
            # Parse path to get group name
            group_name, _ = self.parse_file_path(file_path)
            
            return {
                'file_id': file_id,
                'file_name': file_name,
                'file_path': file_path,
                'group_name': group_name
            }
            
        except Exception as e:
            logger.error(f"Error processing drive event: {e}", exc_info=True)
            return None

