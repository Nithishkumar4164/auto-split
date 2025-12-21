"""Tests for Google Drive handler module."""
import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path

from drive_handler import DriveHandler


class TestDriveHandler:
    """Tests for DriveHandler class."""
    
    @pytest.fixture
    def handler_without_credentials(self):
        """Create handler without credentials."""
        return DriveHandler(credentials_path=None)
    
    @pytest.fixture
    def mock_service(self):
        """Create mock Google Drive service."""
        return Mock()
    
    def test_initialization_no_credentials(self):
        """Test initialization without credentials."""
        handler = DriveHandler(credentials_path=None)
        
        assert handler.service is None
    
    @patch('drive_handler.service_account.Credentials.from_service_account_file')
    @patch('drive_handler.build')
    def test_initialization_with_credentials(self, mock_build, mock_creds, tmp_path):
        """Test initialization with credentials."""
        # Create temp credentials file
        creds_file = tmp_path / "creds.json"
        creds_file.write_text('{"type": "service_account"}')
        
        mock_build.return_value = Mock()
        
        handler = DriveHandler(credentials_path=str(creds_file))
        
        assert handler.service is not None
    
    def test_parse_file_path_with_group(self, handler_without_credentials):
        """Test parsing file path with group."""
        file_path = "Splitwise/Roommates/transaction.jpeg"
        
        group_name, file_name = handler_without_credentials.parse_file_path(file_path)
        
        assert group_name == "Roommates"
        assert file_name == "transaction.jpeg"
    
    def test_parse_file_path_without_group(self, handler_without_credentials):
        """Test parsing file path without group."""
        file_path = "Splitwise/transaction.jpeg"
        
        group_name, file_name = handler_without_credentials.parse_file_path(file_path)
        
        assert group_name is None
        assert file_name == "transaction.jpeg"
    
    def test_parse_file_path_invalid_format(self, handler_without_credentials):
        """Test parsing file path with invalid format."""
        file_path = "InvalidFolder/transaction.jpeg"
        
        group_name, file_name = handler_without_credentials.parse_file_path(file_path)
        
        assert group_name is None
        assert file_name is None
    
    def test_parse_file_path_nested_too_deep(self, handler_without_credentials):
        """Test parsing file path that's nested too deep."""
        file_path = "Splitwise/Group/Subfolder/transaction.jpeg"
        
        group_name, file_name = handler_without_credentials.parse_file_path(file_path)
        
        assert group_name is None
        assert file_name is None
    
    def test_is_image_file_jpeg(self, handler_without_credentials):
        """Test checking JPEG file."""
        assert handler_without_credentials.is_image_file("photo.jpeg") is True
        assert handler_without_credentials.is_image_file("photo.jpg") is True
    
    def test_is_image_file_png(self, handler_without_credentials):
        """Test checking PNG file."""
        assert handler_without_credentials.is_image_file("image.png") is True
    
    def test_is_image_file_not_image(self, handler_without_credentials):
        """Test checking non-image file."""
        assert handler_without_credentials.is_image_file("document.pdf") is False
        assert handler_without_credentials.is_image_file("data.json") is False
    
    def test_is_image_file_case_insensitive(self, handler_without_credentials):
        """Test checking image file is case insensitive."""
        assert handler_without_credentials.is_image_file("PHOTO.JPEG") is True
        assert handler_without_credentials.is_image_file("Image.PNG") is True
    
    @patch.object(DriveHandler, 'get_file_path')
    def test_process_drive_event_success(self, mock_get_path, handler_without_credentials):
        """Test processing drive event successfully."""
        mock_get_path.return_value = "Splitwise/TestGroup/transaction.jpeg"
        
        event_data = {
            'id': 'file123',
            'name': 'transaction.jpeg'
        }
        
        result = handler_without_credentials.process_drive_event(event_data)
        
        assert result is not None
        assert result['file_id'] == 'file123'
        assert result['file_name'] == 'transaction.jpeg'
        assert result['group_name'] == 'TestGroup'
    
    def test_process_drive_event_missing_id(self, handler_without_credentials):
        """Test processing event with missing file ID."""
        event_data = {
            'name': 'transaction.jpeg'
        }
        
        result = handler_without_credentials.process_drive_event(event_data)
        
        assert result is None
    
    def test_process_drive_event_missing_name(self, handler_without_credentials):
        """Test processing event with missing file name."""
        event_data = {
            'id': 'file123'
        }
        
        result = handler_without_credentials.process_drive_event(event_data)
        
        assert result is None
    
    @patch.object(DriveHandler, 'get_file_path')
    @patch.object(DriveHandler, 'is_image_file')
    def test_process_drive_event_not_image(self, mock_is_image, mock_get_path, handler_without_credentials):
        """Test processing event for non-image file."""
        mock_is_image.return_value = False
        
        event_data = {
            'id': 'file123',
            'name': 'document.pdf'
        }
        
        result = handler_without_credentials.process_drive_event(event_data)
        
        assert result is None
    
    @patch.object(DriveHandler, 'get_file_path')
    def test_process_drive_event_no_group(self, mock_get_path, handler_without_credentials):
        """Test processing event for file without group."""
        mock_get_path.return_value = "Splitwise/transaction.jpeg"
        
        event_data = {
            'id': 'file123',
            'name': 'transaction.jpeg'
        }
        
        result = handler_without_credentials.process_drive_event(event_data)
        
        assert result is not None
        assert result['group_name'] is None
    
    def test_download_file_no_service(self, handler_without_credentials, tmp_path):
        """Test downloading file without service initialized."""
        dest_path = tmp_path / "download.jpg"
        
        result = handler_without_credentials.download_file('file123', str(dest_path))
        
        assert result is False
    
    @patch.object(DriveHandler, '_initialize_service')
    def test_get_file_info_no_service(self, mock_init, handler_without_credentials):
        """Test getting file info without service."""
        handler_without_credentials.service = None
        
        result = handler_without_credentials.get_file_info('file123')
        
        assert result is None
    
    def test_get_file_path_no_service(self, handler_without_credentials):
        """Test getting file path without service."""
        handler_without_credentials.service = None
        
        result = handler_without_credentials.get_file_path('file123')
        
        assert result is None

