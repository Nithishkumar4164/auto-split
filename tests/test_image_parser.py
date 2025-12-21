"""Tests for image parser module."""
import pytest
from unittest.mock import Mock, patch, MagicMock
import numpy as np

from image_parser import ImageParser, TransactionDetails


class TestTransactionDetails:
    """Tests for TransactionDetails class."""
    
    def test_initialization(self):
        """Test TransactionDetails initialization."""
        details = TransactionDetails()
        
        assert details.amount is None
        assert details.recipient is None
        assert details.message is None
        assert details.utr is None
        assert details.participants == []
    
    def test_is_valid_true(self):
        """Test is_valid returns True when amount and UTR present."""
        details = TransactionDetails()
        details.amount = 460.0
        details.utr = "987654321098"
        
        assert details.is_valid() is True
    
    def test_is_valid_false_no_amount(self):
        """Test is_valid returns False when amount missing."""
        details = TransactionDetails()
        details.utr = "987654321098"
        
        assert details.is_valid() is False
    
    def test_is_valid_false_no_utr(self):
        """Test is_valid returns False when UTR missing."""
        details = TransactionDetails()
        details.amount = 460.0
        
        assert details.is_valid() is False


class TestImageParser:
    """Tests for ImageParser class."""
    
    def test_initialization(self):
        """Test ImageParser initialization."""
        parser = ImageParser()
        assert parser is not None
    
    def test_initialization_with_tesseract_cmd(self):
        """Test ImageParser initialization with custom tesseract command."""
        parser = ImageParser(tesseract_cmd='/usr/local/bin/tesseract')
        assert parser is not None
    
    @patch('image_parser.cv2.imread')
    @patch('image_parser.cv2.cvtColor')
    @patch('image_parser.cv2.threshold')
    @patch('image_parser.cv2.fastNlMeansDenoising')
    def test_preprocess_image(self, mock_denoise, mock_threshold, mock_cvt, mock_imread):
        """Test image preprocessing."""
        # Setup mocks
        mock_img = np.zeros((100, 100, 3), dtype=np.uint8)
        mock_imread.return_value = mock_img
        mock_cvt.return_value = np.zeros((100, 100), dtype=np.uint8)
        mock_threshold.return_value = (None, np.zeros((100, 100), dtype=np.uint8))
        mock_denoise.return_value = np.zeros((100, 100), dtype=np.uint8)
        
        parser = ImageParser()
        result = parser.preprocess_image('test_image.jpg')
        
        assert result is not None
        mock_imread.assert_called_once_with('test_image.jpg')
    
    def test_parse_amount_rupee_symbol(self):
        """Test parsing amount with rupee symbol."""
        parser = ImageParser()
        text = "Paid to DILAWAR ₹460"
        
        amount = parser.parse_amount(text)
        
        assert amount == 460.0
    
    def test_parse_amount_with_comma(self):
        """Test parsing amount with comma separator."""
        parser = ImageParser()
        text = "Total: ₹1,234.56"
        
        amount = parser.parse_amount(text)
        
        assert amount == 1234.56
    
    def test_parse_amount_rs(self):
        """Test parsing amount with Rs."""
        parser = ImageParser()
        text = "Amount: Rs. 999"
        
        amount = parser.parse_amount(text)
        
        assert amount == 999.0
    
    def test_parse_amount_inr(self):
        """Test parsing amount with INR."""
        parser = ImageParser()
        text = "Total: INR 2500.50"
        
        amount = parser.parse_amount(text)
        
        assert amount == 2500.50
    
    def test_parse_amount_not_found(self):
        """Test parsing amount when not present."""
        parser = ImageParser()
        text = "Some random text without amount"
        
        amount = parser.parse_amount(text)
        
        assert amount is None
    
    def test_parse_utr_with_label(self):
        """Test parsing UTR with label."""
        parser = ImageParser()
        text = "UTR: 987654321098"
        
        utr = parser.parse_utr(text)
        
        assert utr == "987654321098"
    
    def test_parse_utr_transaction_id(self):
        """Test parsing transaction ID."""
        parser = ImageParser()
        text = "Transaction ID T25121915175444655282221"
        
        utr = parser.parse_utr(text)
        
        assert utr == "T25121915175444655282221"
    
    def test_parse_utr_standalone(self):
        """Test parsing standalone 12-digit UTR."""
        parser = ImageParser()
        text = "987654321098"
        
        utr = parser.parse_utr(text)
        
        assert utr == "987654321098"
    
    def test_parse_recipient(self):
        """Test parsing recipient name."""
        parser = ImageParser()
        text = "Paid to DILAWAR"
        
        recipient = parser.parse_recipient(text)
        
        assert recipient == "DILAWAR"
    
    def test_parse_upi_id(self):
        """Test parsing UPI ID."""
        parser = ImageParser()
        text = "paytmqr6na2mo@ptys"
        
        upi_id = parser.parse_upi_id(text)
        
        assert upi_id == "paytmqr6na2mo@ptys"
    
    def test_parse_message(self):
        """Test parsing message."""
        parser = ImageParser()
        text = "Message\nDilawar 7 spices me alex boops"
        
        message = parser.parse_message(text)
        
        assert message == "Dilawar 7 spices me alex boops"
    
    def test_parse_participants_simple(self):
        """Test parsing participants from simple message."""
        parser = ImageParser()
        message = "alex boops"
        
        participants = parser.parse_participants(message)
        
        assert "alex boops" in participants
    
    def test_parse_participants_multiple(self):
        """Test parsing multiple participants."""
        parser = ImageParser()
        message = "for John, Jane and Bob"
        
        participants = parser.parse_participants(message)
        
        assert len(participants) >= 2
    
    def test_parse_participants_with_stop_words(self):
        """Test parsing participants filters stop words."""
        parser = ImageParser()
        message = "split with Alice and Bob"
        
        participants = parser.parse_participants(message)
        
        # Should not contain 'split' or 'with' or 'and'
        assert all(word not in ['split', 'with', 'and'] for word in participants)
    
    def test_parse_account_number(self):
        """Test parsing masked account number."""
        parser = ImageParser()
        text = "XXXXXXXXXXXX9362"
        
        account = parser.parse_account_number(text)
        
        assert account == "XXXX9362"
    
    def test_parse_timestamp(self):
        """Test parsing timestamp."""
        parser = ImageParser()
        text = "03:17 pm on 19 Dec 2025"
        
        timestamp = parser.parse_timestamp(text)
        
        assert timestamp == "03:17 pm on 19 Dec 2025"
    
    @patch.object(ImageParser, 'extract_text')
    def test_parse_image_full_transaction(self, mock_extract):
        """Test parsing complete transaction image."""
        mock_extract.return_value = """
        Transaction Successful
        03:17 pm on 19 Dec 2025
        
        Paid to
        DILAWAR
        paytmqr6na2mo@ptys
        ₹460
        
        Message
        Dilawar 7 spices me alex boops
        
        Transaction ID
        T25121915175444655282221
        
        Debited from
        XXXXXXXXXXXX9362
        UTR: 987654321098
        """
        
        parser = ImageParser()
        details = parser.parse_image('test_image.jpg')
        
        assert details.amount == 460.0
        assert details.recipient == "DILAWAR"
        assert details.message == "Dilawar 7 spices me alex boops"
        assert "alex boops" in details.participants
        assert details.is_valid()
    
    @patch.object(ImageParser, 'extract_text')
    def test_parse_image_empty_text(self, mock_extract):
        """Test parsing image with no extracted text."""
        mock_extract.return_value = ""
        
        parser = ImageParser()
        details = parser.parse_image('test_image.jpg')
        
        assert not details.is_valid()
    
    @patch.object(ImageParser, 'extract_text')
    def test_parse_image_exception(self, mock_extract):
        """Test parsing image handles exceptions."""
        mock_extract.side_effect = Exception("OCR error")
        
        parser = ImageParser()
        details = parser.parse_image('test_image.jpg')
        
        assert not details.is_valid()

