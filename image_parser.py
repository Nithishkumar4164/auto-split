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
        
        if img is None:
            raise ValueError(f"Could not read image from {image_path}")
        
        # Resize (Upscale 2x) - improves OCR accuracy for small text
        img = cv2.resize(img, None, fx=2, fy=2, interpolation=cv2.INTER_LINEAR)
        
        # Convert to grayscale
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        # Thresholding (Binarization) to remove colored backgrounds
        # Using fixed threshold (150) instead of OTSU for more consistent results
        _, thresh = cv2.threshold(gray, 150, 255, cv2.THRESH_BINARY)
        
        return thresh
    
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
            
            # Run Tesseract with Layout Analysis (PSM 6 = assume a block of text)
            # This improves accuracy for receipt/screenshot images
            custom_config = r'--psm 6'
            
            # Use image_to_data to get confidence scores and filter low-confidence words
            data = pytesseract.image_to_data(processed_img, config=custom_config, output_type=pytesseract.Output.DICT)
            
            # Filter out low confidence words and empty text
            # Reconstruct text preserving line structure
            n_boxes = len(data['text'])
            lines_dict = {}  # Use dict to group by line_num
            
            for i in range(n_boxes):
                word = data['text'][i]
                conf = int(data['conf'][i]) if data['conf'][i] else 0
                line_num = int(data['line_num'][i]) if data['line_num'][i] else 0
                
                # Filter out empty text and low confidence words
                if word.strip() and conf > 30:
                    # Group words by line number
                    if line_num not in lines_dict:
                        lines_dict[line_num] = []
                    lines_dict[line_num].append(word)
            
            # Convert to list of lines, sorted by line number
            sorted_lines = sorted(lines_dict.items())
            lines = [" ".join(words) for _, words in sorted_lines]
            
            # Join lines with newlines to preserve structure
            text = "\n".join(lines)
            
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
        # IMPORTANT: Patterns with ₹ symbol should always take precedence
        patterns_with_rupee = [
            # Most common: ₹ or Rs followed by digits (with optional comma separators and decimals)
            # This should match ₹130, ₹460, ₹1,234.56, Rs. 460
            r'(?:₹|Rs\.?)\s*([0-9,]+\.?[0-9]*)',
            
            # Amount before rupee symbol
            r'([0-9,]+\.?[0-9]*)\s*₹',  # 460₹, 460 ₹
        ]
        
        # Context-based patterns (these often have ₹ nearby)
        context_patterns = [
            # Context-based patterns (paid, amount, etc.) - prioritize these
            r'(?:Paid|Amount|Total|Price|Cost|Debited)\s*:?\s*[₹zZ]?\s*([0-9,]+\.?[0-9]*)',
            # OCR ERROR: ₹ read as "2" in payment contexts (e.g., "Paid to: 2130" -> ₹130)
            r'(?:Paid|Amount|Total|Price|Cost|Debited)\s*:?\s*2([1-9]\d{0,3})(?:\s|$|[^\d])',  # "Paid to: 2130" -> 130
        ]
        
        # OCR error patterns (only use when no ₹ symbol found)
        ocr_error_patterns = [
            # OCR ERROR: ₹ sometimes read as 'z' or 'Z' followed by digits
            r'[zZ]\s*([0-9,]+\.?[0-9]*)',  # z1, Z1, z460 (₹ misread as z)
        ]
        
        # Other patterns
        other_patterns = [
            # INR prefix
            r'INR\s*([0-9,]+\.?[0-9]*)',  # INR 460
            
            # Fallback: standalone number (3-6 digits) - but not years like 2025
            # Only match numbers starting with 1-9 (including 130) to avoid dates and small OCR errors
            r'(?:^|\s)([1-9]\d{2,5})(?:\s|$)',  # 130, 460 (as standalone number)
        ]
        
        # Track all valid amounts found with their context
        valid_amounts = []
        
        # First, collect all amounts with ₹ symbol (highest priority)
        for pattern in patterns_with_rupee:
            matches = re.finditer(pattern, text, re.IGNORECASE | re.MULTILINE)
            for match in matches:
                amount_str = match.group(1).replace(',', '').replace(' ', '')
                try:
                    amount = float(amount_str)
                    if 1 <= amount <= 1000000 and not (2020 <= amount <= 2099):
                        context_start = max(0, match.start() - 30)
                        context_end = min(len(text), match.end() + 30)
                        context = text[context_start:context_end].lower()
                        
                        priority = 'high'  # Always high priority for ₹ amounts
                        if 'paid to' in context or 'debited from' in context:
                            priority = 'highest'  # Highest priority for amounts in transaction sections
                        
                        valid_amounts.append((amount, match.start(), priority))
                        logger.debug(f"Found ₹ amount: ₹{amount} using pattern: {pattern} (priority: {priority})")
                except ValueError:
                    continue
        
        # If we found amounts with ₹ symbol, skip OCR error patterns to avoid false positives
        has_rupee_amounts = any(p == 'high' or p == 'highest' for _, _, p in valid_amounts)
        
        # Collect context-based patterns
        for pattern in context_patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE | re.MULTILINE)
            for match in matches:
                amount_str = match.group(1).replace(',', '').replace(' ', '')
                try:
                    amount = float(amount_str)
                    if 1 <= amount <= 1000000 and not (2020 <= amount <= 2099):
                        context_start = max(0, match.start() - 30)
                        context_end = min(len(text), match.end() + 30)
                        context = text[context_start:context_end].lower()
                        
                        priority = 'normal'
                        if 'paid to' in context or 'debited from' in context:
                            priority = 'high'
                        
                        valid_amounts.append((amount, match.start(), priority))
                        logger.debug(f"Found context amount: ₹{amount} using pattern: {pattern} (priority: {priority})")
                except ValueError:
                    continue
        
        # Only use OCR error patterns if no ₹ amounts found (to avoid false positives)
        if not has_rupee_amounts:
            for pattern in ocr_error_patterns:
                matches = re.finditer(pattern, text, re.IGNORECASE | re.MULTILINE)
                for match in matches:
                    amount_str = match.group(1).replace(',', '').replace(' ', '')
                    try:
                        amount = float(amount_str)
                        match_text = match.group(0).lower()
                        
                        # Only apply OCR correction for very small amounts (1-9) when 'z' is present
                        if 1 <= amount <= 9 and 'z' in match_text:
                            logger.info(f"Detected OCR error: {amount} via z pattern")
                            valid_amounts.append((amount, match.start(), 'ocr_corrected'))
                        elif 1 <= amount <= 1000000 and not (2020 <= amount <= 2099):
                            valid_amounts.append((amount, match.start(), 'normal'))
                            logger.debug(f"Found OCR amount: ₹{amount} using pattern: {pattern}")
                    except ValueError:
                        continue
        
        # Collect other patterns
        for pattern in other_patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE | re.MULTILINE)
            for match in matches:
                amount_str = match.group(1).replace(',', '').replace(' ', '')
                try:
                    amount = float(amount_str)
                    if 1 <= amount <= 1000000 and not (2020 <= amount <= 2099):
                        valid_amounts.append((amount, match.start(), 'normal'))
                        logger.debug(f"Found other amount: ₹{amount} using pattern: {pattern}")
                except ValueError:
                    continue
        
        # OCR Error Correction: ₹ sometimes read as "2"
        # Check if any amount starts with "2" and is in a payment context
        # Examples: "2130" -> ₹130, "213" -> ₹13, "21" -> ₹1
        corrected_amounts = []
        for amount, pos, priority in valid_amounts:
            # Convert to integer string to check for leading "2"
            if amount.is_integer():
                amount_int = int(amount)
                amount_str = str(amount_int)
            else:
                # For floats, check the integer part
                amount_str = str(int(amount))
            
            # Check if amount starts with "2" and has 2-5 digits (20-29999 range)
            # This catches cases like 2130, 213, 21 where ₹ was misread as "2"
            if amount_str.startswith('2') and len(amount_str) >= 2 and 20 <= amount <= 29999:
                # Skip if it's a year (2020-2099)
                if 2020 <= amount <= 2099:
                    corrected_amounts.append((amount, pos, priority))
                    continue
                
                # Try removing the leading "2"
                corrected_str = amount_str[1:]  # Remove first character "2"
                try:
                    corrected_amount = float(corrected_str)
                    
                    # Only correct if:
                    # 1. Corrected amount is reasonable (1-1000000)
                    # 2. Corrected amount doesn't start with 0 (avoid "20" -> "0")
                    # 3. It's in a payment context
                    if 1 <= corrected_amount <= 1000000 and not corrected_str.startswith('0'):
                        # Check if it's in a payment context
                        context_start = max(0, pos - 50)
                        context_end = min(len(text), pos + 50)
                        context = text[context_start:context_end].lower()
                        
                        # If in payment context, this is likely an OCR error (₹ misread as "2")
                        if ('paid to' in context or 'debited from' in context or 
                            'amount' in context or 'total' in context or
                            'paid' in context or 'debited' in context or
                            'transfer' in context):
                            logger.info(f"Detected OCR error: {amount} is likely ₹{corrected_amount} (₹ misread as '2')")
                            # Use high priority if in payment context, otherwise keep original priority
                            new_priority = 'high' if ('paid to' in context or 'debited from' in context) else priority
                            corrected_amounts.append((corrected_amount, pos, new_priority))
                            continue
                except (ValueError, IndexError):
                    pass
            
            # Keep original amount if no correction applied
            corrected_amounts.append((amount, pos, priority))
        
        # Use corrected amounts if any corrections were made
        if corrected_amounts:
            valid_amounts = corrected_amounts
        
        # Return the best valid amount
        if valid_amounts:
            # Sort by priority (highest > high > normal > ocr_corrected), then by position
            priority_order = {'highest': 0, 'high': 1, 'normal': 2, 'ocr_corrected': 3}
            valid_amounts.sort(key=lambda x: (priority_order.get(x[2], 2), x[1]))
            amount = valid_amounts[0][0]
            logger.info(f"Found amount: ₹{amount} (from {len(valid_amounts)} potential matches, priority: {valid_amounts[0][2]})")
            return amount
        
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
        # Pattern for message section - handle both newline and colon separators
        # Try to capture everything until the next section (Transaction ID, Debited from, etc.)
        patterns = [
            # Most specific: Message label followed by content until next section
            r'Message\s*[:\n]\s*(.+?)(?=\n(?:Transaction\s+ID|Debited\s+from|UTR|Account|Powered|$))',
            r'Comment\s*[:\n]\s*(.+?)(?=\n(?:Transaction\s+ID|Debited\s+from|UTR|Account|Powered|$))',
            r'Description\s*[:\n]\s*(.+?)(?=\n(?:Transaction\s+ID|Debited\s+from|UTR|Account|Powered|$))',
            
            # Simpler patterns for cases where next section might not be detected
            r'Message\s*[:\n]\s*(.+?)(?:\n\n|\n[A-Z][A-Z\s]+:|$)',
            r'Message\s+(.+?)(?:\n|$)',  # Message followed by space
            
            # Fallback: look for text after common keywords
            r'(?:Message|Comment|Description)\s*[:\s]+\s*(.+?)(?:\n\n|\n[A-Z]|$)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE | re.DOTALL)
            if match:
                message = match.group(1).strip()
                # Clean up message - remove extra whitespace and newlines, but preserve single spaces
                message = re.sub(r'\s+', ' ', message)
                # Remove leading/trailing whitespace
                message = message.strip()
                if message and len(message) > 1:
                    logger.debug(f"Extracted message: '{message}'")
                    return message
        
        # Fallback: Try to find text that looks like a message (contains lowercase letters and spaces)
        # This handles cases where "Message" label might be misread by OCR
        lines = text.split('\n')
        for i, line in enumerate(lines):
            line_lower = line.lower().strip()
            # Look for "Message" keyword
            if ('message' in line_lower or 'comment' in line_lower) and i + 1 < len(lines):
                # Return the next line as potential message
                next_line = lines[i + 1].strip()
                # Make sure it looks like a message (has lowercase letters, not all caps)
                if next_line and len(next_line) > 2 and not next_line.isupper():
                    # Clean up
                    next_line = re.sub(r'\s+', ' ', next_line).strip()
                    logger.debug(f"Extracted message (fallback): '{next_line}'")
                    return next_line
        
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
            logger.debug("No message provided for participant parsing")
            return []
        
        logger.debug(f"Parsing participants from message: '{message}'")
        
        # Normalize message - handle OCR errors in dash (might be read as -, --, or space)
        # Replace multiple dashes or spaces with single dash
        message_normalized = re.sub(r'[-—–]+', '-', message)
        message_normalized = re.sub(r'\s+', ' ', message_normalized)
        
        # Check if message has dash separator (ExpenseTitle- participants)
        if '-' in message_normalized:
            # Split by dash to separate title from participants
            parts = message_normalized.split('-', 1)
            if len(parts) == 2:
                # Get the participant part (after the dash)
                participant_string = parts[1].strip()
                logger.debug(f"Found participant string after dash: '{participant_string}'")
                
                # Split by spaces, commas, or other separators to get individual participants
                # Handle both space-separated and comma-separated formats
                if ',' in participant_string:
                    words = [w.strip() for w in participant_string.split(',')]
                else:
                    words = participant_string.split()
                
                participants = []
                
                for word in words:
                    if not word:
                        continue
                    
                    # Clean the word - remove punctuation but preserve the word
                    clean_word = word.strip('.,!?;:').lower()
                    
                    # Skip 'me' as it refers to current user
                    if clean_word == 'me':
                        logger.debug(f"Skipping 'me' (current user)")
                        continue
                    
                    # Skip numbers (standalone digits)
                    if clean_word.isdigit():
                        continue
                    
                    # Skip common stop words
                    stop_words = {'and', 'with', 'for', 'to', 'from', 'in', 'at', 'the', 'a', 'an', 'split'}
                    if clean_word in stop_words:
                        continue
                    
                    # Check if it's a valid name (2+ chars, starts with letter)
                    # Also allow names that might have OCR errors (mixed case)
                    if len(clean_word) >= 2:
                        # Must start with a letter (not a digit or special char)
                        if clean_word[0].isalpha():
                            # Keep original casing from word (but clean punctuation)
                            clean_participant = word.strip('.,!?;:')
                            participants.append(clean_participant)
                            logger.debug(f"Added participant: '{clean_participant}'")
                        else:
                            logger.debug(f"Skipping '{word}' (doesn't start with letter)")
                
                if participants:
                    logger.info(f"Parsed {len(participants)} participants: {participants}")
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
        
        if participants:
            logger.info(f"Parsed {len(participants)} participants (fallback): {participants}")
        
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

