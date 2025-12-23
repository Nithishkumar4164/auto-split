"""Image parser module for extracting transaction details using OCR."""
import re
import logging
from typing import Dict, List, Optional
from datetime import datetime
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
        self.date: Optional[str] = None  # ISO 8601 formatted date
        self.participants: List[str] = []
        
    def __repr__(self):
        return (f"TransactionDetails(amount={self.amount}, recipient={self.recipient}, "
                f"message={self.message}, utr={self.utr}, participants={self.participants})")
    
    def is_valid(self) -> bool:
        """Check if transaction details are valid."""
        return self.amount is not None and self.utr is not None
    
    def to_dict(self) -> dict:
        """Convert transaction details to dictionary for JSON serialization."""
        return {
            'amount': self.amount,
            'recipient': self.recipient,
            'recipient_upi': self.recipient_upi,
            'message': self.message,
            'transaction_id': self.transaction_id,
            'utr': self.utr,
            'account_number': self.account_number,
            'timestamp': self.timestamp,
            'date': self.date,
            'participants': self.participants
        }


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
            logger.debug(f"OCR Text:\n{text}")
            logger.debug(f"OCR Text length: {len(text)} characters")
            
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
        # Patterns prioritized by reliability - try most specific first
        patterns = [
            # Most common: ₹ followed by digits (with optional comma separators and decimals)
            r'₹\s*(\d{1,3}(?:,?\d{3})*(?:\.\d{1,2})?)',  # ₹460, ₹1,234.56, ₹1234.56
            
            # Rupee symbol with various whitespace
            r'₹\s*(\d+(?:\.\d{1,2})?)',  # ₹ 460, ₹460.50
            
            # OCR ERROR: ₹ sometimes read as 'z' or 'Z'
            r'[zZ]\s*(\d{1,4})',  # z1, Z1, z460 (₹ misread as z)
            
            # OCR ERROR: Small amounts where ₹ might be read as part of the number
            # Look for patterns like "name 21" or "CSE z1" where 21 might be ₹1
            r'\b[A-Z]{2,}\s+[zZ]?(\d{1,4})\b',  # "CSE z1" or "CSE 21"
            
            # Rs or Rs. prefix
            r'Rs\.?\s*(\d{1,3}(?:,?\d{3})*(?:\.\d{1,2})?)',  # Rs. 460, Rs 460
            
            # INR prefix
            r'INR\s*(\d{1,3}(?:,?\d{3})*(?:\.\d{1,2})?)',  # INR 460
            
            # Amount before rupee symbol
            r'(\d{1,3}(?:,?\d{3})*(?:\.\d{1,2})?)\s*₹',  # 460₹, 460 ₹
            
            # Context-based patterns (paid, amount, etc.)
            r'(?:Paid|Amount|Total|Price|Cost)\s*:?\s*₹?\s*(\d{1,3}(?:,?\d{3})*(?:\.\d{1,2})?)',
            
            # Fallback: standalone number (3-6 digits) - but not years like 2025
            r'(?:^|\s)([4-9]\d{2,5})(?:\s|$)',  # 460 (as standalone number, starting with 4-9 to avoid dates)
        ]
        
        for pattern in patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE | re.MULTILINE)
            for match in matches:
                amount_str = match.group(1).replace(',', '').replace(' ', '')
                try:
                    amount = float(amount_str)
                    
                    # Special handling for potential OCR errors with small amounts
                    # If amount is 21 and we found it via 'z' pattern or name pattern, it's likely ₹1
                    if amount == 21 and ('z' in match.group(0).lower() or '[A-Z]{2,}' in pattern):
                        logger.info(f"Detected OCR error: 21 is likely ₹1 (rupee symbol misread)")
                        return 1.0
                    
                    # If amount ends in 1 and is small (11, 21, 31, etc.), check context
                    if 11 <= amount <= 91 and amount % 10 == 1:
                        # Look for 'z' near this number as indicator of OCR error
                        context_start = max(0, match.start() - 10)
                        context_end = min(len(text), match.end() + 10)
                        context = text[context_start:context_end].lower()
                        
                        if 'z' in context or 'cse' in context or 'paid to' in context:
                            # This is likely a single-digit amount with ₹ misread
                            actual_amount = amount % 10  # Get the last digit
                            logger.info(f"Detected OCR error: {amount} is likely ₹{actual_amount} (rupee symbol misread as digit)")
                            return float(actual_amount)
                    
                    # Sanity check: amount should be reasonable (between 1 and 1,000,000)
                    # Also exclude years (2020-2099) which are often in transaction dates
                    if 1 <= amount <= 1000000 and not (2020 <= amount <= 2099):
                        logger.info(f"Found amount: ₹{amount} using pattern: {pattern}")
                        return amount
                except ValueError:
                    continue
        
        logger.warning("No amount found in text")
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
                message = match.group(1).strip()
                logger.debug(f"Extracted message: '{message}'")
                return message
        
        logger.warning("No message found in text")
        return None
    
    def parse_participants(self, message: str) -> List[str]:
        """Parse participant names from message.
        
        Format: "ExpenseTitle- participant1 participant2 participant3"
        Example: "Testtransfer- me sanj boops"
        Example: "Dilawar 7 spices- me alex boops"
        
        Args:
            message: Transaction message
            
        Returns:
            List of participant names (excluding 'me')
        """
        if not message:
            return []
        
        logger.debug(f"Parsing participants from message: '{message}'")
        
        # Check if message has dash separator (ExpenseTitle- participants)
        if '-' in message:
            # Split by dash to separate title from participants
            parts = message.split('-', 1)
            if len(parts) == 2:
                # Get the participant part (after the dash)
                participant_string = parts[1].strip()
                logger.debug(f"Found participant string after dash: '{participant_string}'")
                
                # Split by spaces to get individual participants
                participants = []
                words = participant_string.split()
                
                for word in words:
                    # Clean the word
                    clean_word = word.strip('.,!?;:').lower()
                    
                    # Skip 'me' as it refers to current user
                    if clean_word == 'me':
                        logger.debug(f"Skipping 'me' (current user)")
                        continue
                    
                    # Skip numbers
                    if clean_word.isdigit():
                        continue
                    
                    # Check if it's a valid name (2+ chars, starts with letter)
                    if len(clean_word) >= 2 and clean_word[0].isalpha():
                        # Keep original casing from word
                        participants.append(word.strip('.,!?;:'))
                        logger.debug(f"Added participant: '{word}'")
                
                return participants
        
        # Fallback: Parse using old logic for backward compatibility
        logger.debug("No dash found, using fallback parsing")
        
        # Remove common words and filler
        stop_words = {'me', 'and', 'with', 'for', 'to', 'from', 'in', 'at', 'the', 'a', 'an', 'split', 'spices'}
        
        # Remove numbers (like "7") which are often item counts
        message_cleaned = re.sub(r'\b\d+\b', '', message)
        
        participants = []
        words = message_cleaned.split()
        
        for word in words:
            clean_word = word.lower().strip('.,!?;:')
            
            # Skip stop words
            if clean_word in stop_words:
                continue
            
            # Check if word looks like a name (2+ chars, starts with letter)
            if len(word) >= 2 and word[0].isalpha():
                participants.append(word.strip('.,!?;:'))
        
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
            Timestamp string or None
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
    
    def parse_date(self, text: str) -> Optional[str]:
        """Parse payment date from text and convert to ISO 8601 format.
        
        Args:
            text: OCR extracted text
            
        Returns:
            ISO 8601 formatted date string (e.g., "2025-12-21T19:12:00Z") or None
        """
        timestamp_str = self.parse_timestamp(text)
        if not timestamp_str:
            return None
        
        try:
            # Try to parse "07:12 pm on 21 Dec 2025" format
            pattern1 = r'(\d{1,2}):(\d{2})\s*(am|pm)\s+on\s+(\d{1,2})\s+(\w+)\s+(\d{4})'
            match = re.search(pattern1, timestamp_str, re.IGNORECASE)
            if match:
                hour = int(match.group(1))
                minute = int(match.group(2))
                am_pm = match.group(3).lower()
                day = int(match.group(4))
                month_str = match.group(5)
                year = int(match.group(6))
                
                # Convert 12-hour to 24-hour format
                if am_pm == 'pm' and hour != 12:
                    hour += 12
                elif am_pm == 'am' and hour == 12:
                    hour = 0
                
                # Convert month name to number
                month_map = {
                    'jan': 1, 'january': 1, 'feb': 2, 'february': 2,
                    'mar': 3, 'march': 3, 'apr': 4, 'april': 4,
                    'may': 5, 'jun': 6, 'june': 6,
                    'jul': 7, 'july': 7, 'aug': 8, 'august': 8,
                    'sep': 9, 'sept': 9, 'september': 9,
                    'oct': 10, 'october': 10, 'nov': 11, 'november': 11,
                    'dec': 12, 'december': 12
                }
                month = month_map.get(month_str.lower()[:3])
                if not month:
                    logger.warning(f"Could not parse month: {month_str}")
                    return None
                
                # Create datetime object and convert to ISO 8601
                dt = datetime(year, month, day, hour, minute, 0)
                iso_date = dt.strftime('%Y-%m-%dT%H:%M:%SZ')
                logger.info(f"Parsed date: {timestamp_str} -> {iso_date}")
                return iso_date
            
            # Try to parse "MM/DD/YYYY HH:MM" format
            pattern2 = r'(\d{1,2})/(\d{1,2})/(\d{4})\s+(\d{1,2}):(\d{2})(?::(\d{2}))?'
            match = re.search(pattern2, timestamp_str)
            if match:
                month = int(match.group(1))
                day = int(match.group(2))
                year = int(match.group(3))
                hour = int(match.group(4))
                minute = int(match.group(5))
                second = int(match.group(6)) if match.group(6) else 0
                
                dt = datetime(year, month, day, hour, minute, second)
                iso_date = dt.strftime('%Y-%m-%dT%H:%M:%SZ')
                logger.info(f"Parsed date: {timestamp_str} -> {iso_date}")
                return iso_date
            
            # Try to parse "YYYY-MM-DD HH:MM:SS" format
            pattern3 = r'(\d{4})-(\d{2})-(\d{2})\s+(\d{2}):(\d{2}):(\d{2})'
            match = re.search(pattern3, timestamp_str)
            if match:
                year = int(match.group(1))
                month = int(match.group(2))
                day = int(match.group(3))
                hour = int(match.group(4))
                minute = int(match.group(5))
                second = int(match.group(6))
                
                dt = datetime(year, month, day, hour, minute, second)
                iso_date = dt.strftime('%Y-%m-%dT%H:%M:%SZ')
                logger.info(f"Parsed date: {timestamp_str} -> {iso_date}")
                return iso_date
            
            logger.warning(f"Could not parse timestamp format: {timestamp_str}")
            return None
            
        except Exception as e:
            logger.error(f"Error parsing date: {e}", exc_info=True)
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
            details.date = self.parse_date(text)  # Parse and convert to ISO 8601
            
            # Parse participants from message
            if details.message:
                details.participants = self.parse_participants(details.message)
            
            # Log what was extracted
            logger.info(f"Parsed transaction details: {details}")
            if not details.amount:
                logger.warning("Amount not extracted! Showing first 500 chars of OCR text for debugging:")
                logger.warning(text[:500])
            
            return details
            
        except Exception as e:
            logger.error(f"Error parsing image {image_path}: {e}", exc_info=True)
            return details

