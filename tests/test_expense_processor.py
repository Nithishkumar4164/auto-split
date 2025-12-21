"""Tests for expense processor module."""
import pytest
from unittest.mock import Mock, patch
from pathlib import Path

from expense_processor import ExpenseProcessor
from image_parser import TransactionDetails


class TestExpenseProcessor:
    """Tests for ExpenseProcessor class."""
    
    @pytest.fixture
    def mock_components(self):
        """Create mock components for processor."""
        return {
            'image_parser': Mock(),
            'alias_manager': Mock(),
            'utr_tracker': Mock(),
            'splitwise_client': Mock(),
            'drive_handler': Mock()
        }
    
    @pytest.fixture
    def processor(self, mock_components):
        """Create ExpenseProcessor instance with mocks."""
        return ExpenseProcessor(
            image_parser=mock_components['image_parser'],
            alias_manager=mock_components['alias_manager'],
            utr_tracker=mock_components['utr_tracker'],
            splitwise_client=mock_components['splitwise_client'],
            drive_handler=mock_components['drive_handler']
        )
    
    @pytest.fixture
    def valid_transaction(self):
        """Create valid transaction details."""
        transaction = TransactionDetails()
        transaction.amount = 460.0
        transaction.utr = "987654321098"
        transaction.recipient = "DILAWAR"
        transaction.message = "Dilawar 7 spices me alex boops"
        transaction.participants = ["alex boops"]
        return transaction
    
    def test_initialization(self, mock_components):
        """Test processor initialization."""
        processor = ExpenseProcessor(**mock_components)
        
        assert processor.image_parser == mock_components['image_parser']
        assert processor.alias_manager == mock_components['alias_manager']
    
    def test_process_image_success(self, processor, mock_components, valid_transaction):
        """Test processing image successfully."""
        # Setup mocks
        mock_components['image_parser'].parse_image.return_value = valid_transaction
        mock_components['utr_tracker'].is_processed.return_value = False
        mock_components['alias_manager'].match_participants.return_value = ["Alex Boops"]
        mock_components['splitwise_client'].find_group_by_name.return_value = "group_123"
        mock_components['splitwise_client'].prepare_expense_with_image.return_value = {
            'success': True,
            'expense_id': 'exp_456'
        }
        
        result = processor.process_image("test_image.jpg", group_name="Roommates")
        
        assert result['success'] is True
        assert result['expense_id'] == 'exp_456'
        mock_components['utr_tracker'].add_utr.assert_called_once()
    
    def test_process_image_invalid_transaction(self, processor, mock_components):
        """Test processing image with invalid transaction."""
        # Create invalid transaction
        invalid_transaction = TransactionDetails()
        invalid_transaction.amount = None
        
        mock_components['image_parser'].parse_image.return_value = invalid_transaction
        
        result = processor.process_image("test_image.jpg")
        
        assert result['success'] is False
        assert 'Invalid transaction details' in result['error']
    
    def test_process_image_duplicate_utr(self, processor, mock_components, valid_transaction):
        """Test processing image with duplicate UTR."""
        mock_components['image_parser'].parse_image.return_value = valid_transaction
        mock_components['utr_tracker'].is_processed.return_value = True
        mock_components['utr_tracker'].get_utr_info.return_value = {
            'expense_id': 'exp_old',
            'amount': 460.0
        }
        
        result = processor.process_image("test_image.jpg")
        
        assert result['success'] is False
        assert 'Duplicate transaction' in result['error']
        assert 'existing_expense' in result
    
    def test_process_image_no_participants(self, processor, mock_components, valid_transaction):
        """Test processing image with no participants."""
        valid_transaction.participants = []
        mock_components['image_parser'].parse_image.return_value = valid_transaction
        mock_components['utr_tracker'].is_processed.return_value = False
        mock_components['splitwise_client'].prepare_expense_with_image.return_value = {
            'success': True
        }
        
        result = processor.process_image("test_image.jpg")
        
        assert result['success'] is True
        assert result['matched_participants'] == []
    
    def test_process_image_with_group(self, processor, mock_components, valid_transaction):
        """Test processing image with group name."""
        mock_components['image_parser'].parse_image.return_value = valid_transaction
        mock_components['utr_tracker'].is_processed.return_value = False
        mock_components['alias_manager'].match_participants.return_value = ["User1"]
        mock_components['splitwise_client'].find_group_by_name.return_value = "group_789"
        mock_components['splitwise_client'].prepare_expense_with_image.return_value = {
            'success': True
        }
        
        result = processor.process_image("test_image.jpg", group_name="TestGroup")
        
        assert result['success'] is True
        assert result['group_name'] == "TestGroup"
        mock_components['splitwise_client'].find_group_by_name.assert_called_with("TestGroup")
    
    def test_process_image_group_not_found(self, processor, mock_components, valid_transaction):
        """Test processing image when group not found."""
        mock_components['image_parser'].parse_image.return_value = valid_transaction
        mock_components['utr_tracker'].is_processed.return_value = False
        mock_components['alias_manager'].match_participants.return_value = ["User1"]
        mock_components['splitwise_client'].find_group_by_name.return_value = None
        mock_components['splitwise_client'].prepare_expense_with_image.return_value = {
            'success': True
        }
        
        result = processor.process_image("test_image.jpg", group_name="NonExistent")
        
        # Should still succeed but without group
        assert result['success'] is True
    
    def test_process_image_expense_creation_failed(self, processor, mock_components, valid_transaction):
        """Test processing image when expense creation fails."""
        mock_components['image_parser'].parse_image.return_value = valid_transaction
        mock_components['utr_tracker'].is_processed.return_value = False
        mock_components['alias_manager'].match_participants.return_value = ["User1"]
        mock_components['splitwise_client'].prepare_expense_with_image.return_value = {
            'success': False,
            'error': 'API error'
        }
        
        result = processor.process_image("test_image.jpg")
        
        assert result['success'] is False
        assert 'Failed to create Splitwise expense' in result['error']
    
    def test_build_expense_description_with_message(self, processor, valid_transaction):
        """Test building expense description from message."""
        description = processor._build_expense_description(valid_transaction)
        
        assert description == "Dilawar 7 spices me alex boops"
    
    def test_build_expense_description_with_message_containing_dash(self, processor):
        """Test building expense description from message with dash separator."""
        transaction = TransactionDetails()
        transaction.message = "Dilawar 7 spices- me alex boops"
        transaction.amount = 460.0
        
        description = processor._build_expense_description(transaction)
        
        assert description == "Dilawar 7 spices"
    
    def test_build_expense_description_with_recipient(self, processor):
        """Test building expense description from recipient."""
        transaction = TransactionDetails()
        transaction.recipient = "DILAWAR"
        transaction.amount = 460.0
        
        description = processor._build_expense_description(transaction)
        
        assert description == "Payment to DILAWAR"
    
    def test_build_expense_description_fallback(self, processor):
        """Test building expense description fallback."""
        transaction = TransactionDetails()
        transaction.amount = 460.0
        
        description = processor._build_expense_description(transaction)
        
        assert description == "Transaction - ₹460.0"
    
    def test_process_drive_event_success(self, processor, mock_components, tmp_path):
        """Test processing drive event successfully."""
        # Create temp image file
        image_file = tmp_path / "transaction.jpeg"
        image_file.write_bytes(b"fake image")
        
        mock_components['drive_handler'].process_drive_event.return_value = {
            'file_id': 'file123',
            'file_name': 'transaction.jpeg',
            'file_path': 'Splitwise/Group/transaction.jpeg',
            'group_name': 'Group'
        }
        mock_components['drive_handler'].download_file.return_value = True
        
        # Mock process_image to return success
        with patch.object(processor, 'process_image', return_value={'success': True}):
            event_data = {'id': 'file123', 'name': 'transaction.jpeg'}
            result = processor.process_drive_event(event_data)
            
            assert result['success'] is True
    
    def test_process_drive_event_failed_processing(self, processor, mock_components):
        """Test processing drive event with failed event processing."""
        mock_components['drive_handler'].process_drive_event.return_value = None
        
        event_data = {'id': 'file123', 'name': 'document.pdf'}
        result = processor.process_drive_event(event_data)
        
        assert result['success'] is False
        assert 'Failed to process drive event' in result['error']
    
    def test_process_drive_event_download_failed(self, processor, mock_components):
        """Test processing drive event with failed download."""
        mock_components['drive_handler'].process_drive_event.return_value = {
            'file_id': 'file123',
            'file_name': 'transaction.jpeg',
            'file_path': 'Splitwise/Group/transaction.jpeg',
            'group_name': 'Group'
        }
        mock_components['drive_handler'].download_file.return_value = False
        
        event_data = {'id': 'file123', 'name': 'transaction.jpeg'}
        result = processor.process_drive_event(event_data)
        
        assert result['success'] is False
        assert 'Failed to download file' in result['error']
    
    def test_process_image_exception_handling(self, processor, mock_components):
        """Test exception handling in process_image."""
        mock_components['image_parser'].parse_image.side_effect = Exception("Parse error")
        
        result = processor.process_image("test_image.jpg")
        
        assert result['success'] is False
        assert 'error' in result

