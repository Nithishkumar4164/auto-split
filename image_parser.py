"""Image parser module for extracting transaction details using OCR."""
import re
import logging
from typing import Dict, List, Optional
from PIL import Image
import pytesseract
import cv2
import numpy as np

logger = logging.getLogger(__name__)


class TransactionDetails:
    """Data class for transaction details."""
    
    def __init__(self):
        self.amount: Optional[float] = None
        self.recipient: Optional[str] = None
        self.recipient_upi: Optional[str] = None
        self.message: Optional[str] = None
        self.transaction_id: Optional[str] = None
        self.utr: Optional[str] = None
        self.account_number: Optional[str] = None
        self.timestamp: Optional[str] = None
        self.participants: List[str] = []
        
    def __repr__(self):
        return (f"TransactionDetails(amount={self.amount}, recipient={self.recipient}, "
                f"message={self.message}, utr={self.utr}, participants={self.participants})")
    
    def is_valid(self) -> bool:
        """Check if transaction details are valid."""
        return self.amount is not None and self.utr is not None


class ImageParser:
    """Parser for extracting transaction details from payment screenshots."""
    
    def __init__(self, tesseract_cmd: Optional[str] = None):
        """Initialize the image parser.
        
        Args:
            tesseract_cmd: Path to tesseract executable
        """
        if tesseract_cmd:
            pytesseract.pytesseract.tesseract_cmd = tesseract_cmd
        
    def preprocess_image(self, image_path: str) -> np.ndarray:
        """Preprocess image for better OCR results.
        
        Args:
            image_path: Path to the image file
            
        Returns:
            Preprocessed image as numpy array
        """
        # Read image
        img = cv2.imread(image_path)
        
        # Convert to grayscale
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        # Apply thresholding
        _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        
        # Denoise
        denoised = cv2.fastNlMeansDenoising(thresh, None, 10, 7, 21)
        
        return denoised
    
    def extract_text(self, image_path: str) -> str:
        """Extract text from image using OCR.
        
        Args:
            image_path: Path to the image file
            
        Returns:
            Extracted text
        """
        try:
            # Preprocess image
            processed_img = self.preprocess_image(image_path)
            
            # Perform OCR
            text = pytesseract.image_to_string(processed_img)
            
            logger.info(f"Extracted text from {image_path}")
            logger.debug(f"OCR Text: {text}")
            
            return text
        except Exception as e:
            logger.error(f"Error extracting text from {image_path}: {e}")
            return ""
    
    def parse_amount(self, text: str) -> Optional[float]:
        """Parse amount from text.
        
        Args:
            text: OCR extracted text
            
        Returns:
            Parsed amount or None
        """
        # Pattern for Indian currency (₹460, ₹1,234.56, etc.)
        patterns = [
            r'₹\s*(\d{1,3}(?:,\d{3})*(?:\.\d{1,2})?)',  # ₹460 or ₹1,234.56
            r'Rs\.?\s*(\d{1,3}(?:,\d{3})*(?:\.\d{1,2})?)',  # Rs. 460
            r'INR\s*(\d+(?:,\d{3})*(?:\.\d{1,2})?)',  # INR 460 or INR 2500.50
            r'\b(\d{1,3}(?:,\d{3})*(?:\.\d{1,2})?)\s*(?:₹|Rs|INR)',  # 460₹
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                amount_str = match.group(1).replace(',', '')
                try:
                    return float(amount_str)
                except ValueError:
                    continue
        
        return None
    
    def parse_utr(self, text: str) -> Optional[str]:
        """Parse UTR number from text.
        
        Args:
            text: OCR extracted text
            
        Returns:
            UTR number or None
        """
        # Pattern for UTR (typically 12-digit number)
        # Also matches Transaction ID patterns
        patterns = [
            r'UTR:\s*(\d{12,})',  # UTR: 987654321098
            r'UTR\s+(\d{12,})',
            r'Transaction\s+ID[:\s]+([A-Z0-9]{10,})',  # Transaction ID T25121915175444655282221
            r'Trans(?:action)?\s+(?:ID|Ref)[:\s]+([A-Z0-9]{10,})',
            r'\b(\d{12})\b',  # 12-digit number
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1)
        
        return None
    
    def parse_recipient(self, text: str) -> Optional[str]:
        """Parse recipient name from text.
        
        Args:
            text: OCR extracted text
            
        Returns:
            Recipient name or None
        """
        # Pattern for "Paid to" section
        patterns = [
            r'Paid\s+to\s+([A-Z][A-Z\s]+?)(?:\n|$)',  # Stop at newline
            r'To:\s*([A-Z][A-Z\s]+?)(?:\n|$)',
            r'Recipient:\s*([A-Z][A-Z\s]+?)(?:\n|$)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        
        return None
    
    def parse_upi_id(self, text: str) -> Optional[str]:
        """Parse UPI ID from text.
        
        Args:
            text: OCR extracted text
            
        Returns:
            UPI ID or None
        """
        # Pattern for UPI ID (e.g., paytmqr6na2mo@ptys)
        pattern = r'([a-z0-9]+@[a-z]+)'
        match = re.search(pattern, text, re.IGNORECASE)
        
        if match:
            return match.group(1).lower()
        
        return None
    
    def parse_message(self, text: str) -> Optional[str]:
        """Parse message/comment from text.
        
        Args:
            text: OCR extracted text
            
        Returns:
            Message or None
        """
        # Pattern for message section
        patterns = [
            r'Message\s*\n\s*(.+?)(?:\n|$)',
            r'Comment\s*[:\n]\s*(.+?)(?:\n|$)',
            r'Description\s*[:\n]\s*(.+?)(?:\n|$)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
            if match:
                return match.group(1).strip()
        
        return None
    
    def parse_participants(self, message: str) -> List[str]:
        """Parse participant names from message.
        
        Args:
            message: Transaction message
            
        Returns:
            List of participant names
        """
        if not message:
            return []
        
        # Common patterns for mentioning people
        # "Dilawar 7 spices me alex boops"
        # "for John, Jane and Bob"
        # "split with Alice & Bob"
        
        # Remove common words
        stop_words = {'me', 'and', 'with', 'for', 'to', 'from', 'in', 'at', 'the', 'a', 'an', 'split'}
        
        # Split by common delimiters
        participants = []
        parts = re.split(r'[,&]|\s+and\s+|\s+with\s+|\s+for\s+', message, flags=re.IGNORECASE)
        
        for part in parts:
            # Clean and extract names
            words = part.strip().split()
            name_parts = []
            
            for word in words:
                # Skip stop words and numbers
                clean_word = word.lower().strip('.,!?;:')
                if clean_word not in stop_words and not word.isdigit():
                    # Check if word looks like a name (starts with capital or all lowercase)
                    if len(word) > 0 and (word[0].isupper() or word.islower()):
                        name_parts.append(word)
            
            if name_parts:
                # Filter out remaining stop words from final name
                filtered_parts = [p for p in name_parts if p.lower() not in stop_words]
                
                if filtered_parts:
                    # Extract all consecutive 2-word lowercase combinations (like "alex boops")
                    found_lowercase_pairs = False
                    for i in range(len(filtered_parts) - 1):
                        if filtered_parts[i][0].islower() and filtered_parts[i+1][0].islower():
                            participants.append(f"{filtered_parts[i]} {filtered_parts[i+1]}")
                            found_lowercase_pairs = True
                    
                    # If no lowercase pairs found in this part, add individual names or combined
                    if not found_lowercase_pairs:
                        # For short lists (1-3 words), join them as a single name
                        if len(filtered_parts) <= 3:
                            participants.append(' '.join(filtered_parts))
        
        return participants
    
    def parse_account_number(self, text: str) -> Optional[str]:
        """Parse account number from text.
        
        Args:
            text: OCR extracted text
            
        Returns:
            Account number or None
        """
        # Pattern for masked account numbers (e.g., XXXXXXXXXXXX9362)
        pattern = r'[X]{8,}(\d{4})'
        match = re.search(pattern, text)
        
        if match:
            return 'XXXX' + match.group(1)
        
        return None
    
    def parse_timestamp(self, text: str) -> Optional[str]:
        """Parse timestamp from text.
        
        Args:
            text: OCR extracted text
            
        Returns:
            Timestamp or None
        """
        # Pattern for timestamp (e.g., "03:17 pm on 19 Dec 2025")
        patterns = [
            r'(\d{1,2}:\d{2}\s*(?:am|pm)\s+on\s+\d{1,2}\s+\w+\s+\d{4})',
            r'(\d{1,2}/\d{1,2}/\d{4}\s+\d{1,2}:\d{2}(?::\d{2})?)',
            r'(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1)
        
        return None
    
    def parse_image(self, image_path: str) -> TransactionDetails:
        """Parse transaction details from image.
        
        Args:
            image_path: Path to the transaction image
            
        Returns:
            TransactionDetails object
        """
        details = TransactionDetails()
        
        try:
            # Extract text from image
            text = self.extract_text(image_path)
            
            if not text:
                logger.warning(f"No text extracted from {image_path}")
                return details
            
            # Parse individual fields
            details.amount = self.parse_amount(text)
            details.recipient = self.parse_recipient(text)
            details.recipient_upi = self.parse_upi_id(text)
            details.message = self.parse_message(text)
            details.utr = self.parse_utr(text)
            details.transaction_id = details.utr  # Use same for now
            details.account_number = self.parse_account_number(text)
            details.timestamp = self.parse_timestamp(text)
            
            # Parse participants from message
            if details.message:
                details.participants = self.parse_participants(details.message)
            
            logger.info(f"Parsed transaction details: {details}")
            
            return details
            
        except Exception as e:
            logger.error(f"Error parsing image {image_path}: {e}", exc_info=True)
            return details

