"""Image parser module for extracting transaction details using OCR."""
import re
import logging
from typing import List, Optional
from datetime import datetime
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
        
    def _preprocess_image(self, image_path: str) -> np.ndarray:
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
        
        # Resize (Upscale 3x) - improves OCR accuracy for small text
        img = cv2.resize(img, None, fx=3, fy=3, interpolation=cv2.INTER_LINEAR)
        
        # Convert to grayscale
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        # Enhance contrast using CLAHE (helps make faint text more visible)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        enhanced = clahe.apply(gray)
        
        # Apply denoising before thresholding
        denoised = cv2.fastNlMeansDenoising(enhanced, None, 10, 7, 21)
        
        # Use OTSU's binarization for automatic threshold selection
        # This adapts to the image's brightness distribution
        _, thresh = cv2.threshold(denoised, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        
        return thresh
    
    def _extract_text(self, image_path: str) -> str:
        """Extract text from image using OCR with multiple strategies.
        
        Args:
            image_path: Path to the image file
            
        Returns:
            Extracted text
        """
        try:
            # Try BOTH preprocessed and original image
            # Sometimes preprocessing removes important symbols like ₹
            processed_img = self._preprocess_image(image_path)
            original_img = cv2.imread(image_path)
            
            images_to_try = [
                ('preprocessed', processed_img),
                ('original', original_img)
            ]
            
            # Try multiple PSM modes - different modes work better for different images
            psm_modes = [3, 6, 4, 11]  # 3=auto, 6=block, 4=single column, 11=sparse text
            best_text = ""
            best_score = 0
            best_method = ""
            
            for img_type, img in images_to_try:
                for psm in psm_modes:
                    try:
                        # Try with different OEM (OCR Engine Modes)
                        # OEM 3 = Default (Legacy + LSTM), OEM 1 = LSTM only
                        custom_config = f'--psm {psm} --oem 3'
                        data = pytesseract.image_to_data(img, config=custom_config, output_type=pytesseract.Output.DICT)
                        
                        # Filter and reconstruct text
                        n_boxes = len(data['text'])
                        lines_dict = {}
                        total_conf = 0
                        conf_count = 0
                        
                        for i in range(n_boxes):
                            word = data['text'][i]
                            conf = int(data['conf'][i]) if data['conf'][i] else 0
                            line_num = int(data['line_num'][i]) if data['line_num'][i] else 0
                            
                            # Lower confidence threshold to catch more text
                            # Use even lower threshold (10) for sparse text mode (PSM 11)
                            min_conf = 10 if psm == 11 else 15
                            if word.strip() and conf > min_conf:
                                if line_num not in lines_dict:
                                    lines_dict[line_num] = []
                                lines_dict[line_num].append(word)
                                total_conf += conf
                                conf_count += 1
                        
                        # Reconstruct text
                        sorted_lines = sorted(lines_dict.items())
                        lines = [" ".join(words) for _, words in sorted_lines]
                        text = "\n".join(lines)
                        
                        # Score this extraction
                        # Higher score = more text + higher confidence + contains rupee symbol
                        avg_conf = total_conf / conf_count if conf_count > 0 else 0
                        score = len(text) * 0.5 + avg_conf * 0.3
                        
                        # HUGE boost for rupee symbols (real or OCR errors)
                        if '₹' in text or 'Rs' in text:
                            score += 300  # Highest priority
                        
                        # Big boost for amount-like patterns (OCR errors of rupee symbol)
                        # C27, ~50, <130, =140, %3,033, Z45, c30, etc.
                        import re
                        amount_patterns = [
                            r'\b[Cc~Zz]\s*\d{2,}',  # C27, ~50, Z45, c30
                            r'[<=%]\s*\d[\d,]*',  # <130, =140, %3,033 (with commas)
                            r'\?\s*\d{2,}',  # ?27
                        ]
                        for pattern in amount_patterns:
                            if re.search(pattern, text):
                                score += 200  # Very high priority for amount patterns
                                logger.debug(f"Found amount pattern '{pattern}' in text")
                                break
                        
                        method = f"{img_type}/PSM{psm}"
                        logger.debug(f"{method}: {len(text)} chars, avg_conf={avg_conf:.1f}, score={score:.1f}, has_₹={('₹' in text or 'Rs' in text)}")
                        
                        if score > best_score:
                            best_score = score
                            best_text = text
                            best_method = method
                            
                    except Exception as e:
                        logger.debug(f"{img_type}/PSM{psm} failed: {e}")
                        continue
            
            logger.info(f"Extracted text from {image_path} using {best_method}")
            logger.debug(f"OCR Text ({len(best_text)} chars):\n{best_text}")
            
            return best_text
        except Exception as e:
            logger.error(f"Error extracting text from {image_path}: {e}")
            return ""
    
    def _parse_amount(self, text: str) -> Optional[float]:
        """Parse amount from text using prioritized pattern matching."""
        if not text:
            return None

        # 1. Clean the text to handle common OCR issues
        # Remove commas to make number parsing easier (e.g. "1,234" -> "1234")
        clean_text = text.replace(',', '')
        
        candidates = []  # Format: (amount, priority, position)

        # 2. Priority 1: Explicit Rupee Symbol (₹) near "Paid to" section
        # This handles the main amount display in UPI screenshots
        # Strategy: Split text into lines and look for rupee symbol in lines after "Paid to"
        # Stop at section boundaries like "Transfer Details", "Payment details", "Message", etc.
        lines = clean_text.split('\n')
        in_paid_to_section = False
        paid_to_section_lines = []
        
        for line in lines:
            # Start capturing after "Paid to"
            if re.search(r'Paid\s+to', line, re.IGNORECASE):
                in_paid_to_section = True
                continue
            
            # Stop at section boundaries
            if in_paid_to_section:
                # Use flexible patterns for section boundaries
                # Transaction ID might be read as "TransactionID", "Transaction 1D", etc.
                if re.search(r'(?:Transfer|Payment)\s*details?|Message|Transaction\s*I?D|Debited\s*from', line, re.IGNORECASE):
                    break
                paid_to_section_lines.append(line)
        
        # Look for rupee symbols in the captured "Paid to" section
        if paid_to_section_lines:
            paid_to_text = '\n'.join(paid_to_section_lines)
            logger.debug(f"'Paid to' section ({len(paid_to_section_lines)} lines): {paid_to_text[:100]}")
            
            # Common OCR errors: ₹ → C, z, Z, ?, 2, ~, <, =, %
            # Use word boundary \b to ensure C/c/z/Z are standalone (not part of "Dec", etc.)
            # Allow comma separators in amounts (e.g., 3,033)
            rupee_matches = re.finditer(r'(?:₹|\?|Rs\.?|INR|[~<=%]|\b[CczZ])\s*([\d,]+(?:\.\d{1,2})?)', paid_to_text, re.IGNORECASE)
            for match in rupee_matches:
                try:
                    # Remove commas from numbers (e.g., "3,033" → "3033")
                    val = float(match.group(1).replace(',', ''))
                    # Valid amount: > 0 and not a year (2020-2030)
                    if val > 0 and not (2020 <= val <= 2030):
                        # Highest priority for rupee symbol in "Paid to" section
                        candidates.append((val, 100, match.start()))
                        logger.debug(f"Found rupee symbol in 'Paid to' section: ₹{val}")
                    elif 2020 <= val <= 2030:
                        logger.debug(f"Skipping year in 'Paid to' section: {val}")
                except ValueError:
                    continue

        # 3. Priority 2: Rupee Symbol anywhere else (fallback)
        # This catches amounts in other sections if not found in "Paid to"
        if not candidates:  # Only search elsewhere if not found in paid_to section
            # Common OCR errors: ₹ → C, z, Z, ?, 2, ~, <, =, %
            # Use word boundary \b to ensure C/c/z/Z are standalone (not part of "Dec", etc.)
            # Allow comma separators in amounts (e.g., 3,033)
            rupee_matches = re.finditer(r'(?:₹|\?|Rs\.?|INR|[~<=%]|\b[CczZ])\s*([\d,]+(?:\.\d{1,2})?)', clean_text, re.IGNORECASE)
            for match in rupee_matches:
                try:
                    # Remove commas from numbers (e.g., "3,033" → "3033")
                    val = float(match.group(1).replace(',', ''))
                    # Valid amount: > 0 and not a year (2020-2030)
                    if val > 0 and not (2020 <= val <= 2030):
                        candidates.append((val, 80, match.start()))
                        logger.debug(f"Found rupee symbol elsewhere: ₹{val}")
                    elif 2020 <= val <= 2030:
                        logger.debug(f"Skipping year elsewhere: {val}")
                except ValueError:
                    continue

        # 4. Priority 3: Contextual Search (specific patterns only)
        # Look for number immediately after "Paid to" line (without matching UPI IDs)
        # This is more restrictive than before - only matches direct amounts
        if not candidates:  # Only if no rupee symbol found
            # Pattern: Match number that appears on its own line or after specific keywords
            context_patterns = [
                r'(?:Amount|Total|Price)\s*:?\s*(\d+(?:\.\d{1,2})?)',  # "Amount: 50"
                r'(?:Paid|Debited)\s*:?\s*(?:₹|Rs\.?)?\s*(\d+(?:\.\d{1,2})?)',  # "Paid: 50"
            ]
            for pattern in context_patterns:
                matches = re.finditer(pattern, clean_text, re.IGNORECASE)
                for match in matches:
                    try:
                        val = float(match.group(1))
                        if val > 0 and not (2020 <= val <= 2030):
                            candidates.append((val, 50, match.start()))
                            logger.debug(f"Found context match: {val}")
                    except ValueError:
                        continue

        # 5. Priority 4: The "2" Glitch Fix (Specific to Indian UPI)
        # If we found a candidate like 2130 but NO candidate like 130, check if 2130 -> 130 makes sense
        # Only apply this correction to high-priority matches (rupee symbols) to avoid false corrections
        ocr_correction_candidates = []
        existing_values = {c[0] for c in candidates}
        
        for val, prio, pos in candidates:
            # Only apply OCR correction to high-priority candidates (prio >= 50)
            # This avoids correcting random numbers from fallback matches
            if prio < 50:
                continue
                
            val_str = str(int(val)) if val.is_integer() else str(val)
            if val_str.startswith('2') and len(val_str) > 1:
                try:
                    corrected = float(val_str[1:])  # Strip leading '2'
                    if corrected > 0 and corrected not in existing_values:
                        ocr_correction_candidates.append((corrected, prio - 10, pos))
                        logger.debug(f"OCR correction candidate: {corrected} (from {val})")
                except ValueError:
                    pass
        
        candidates.extend(ocr_correction_candidates)

        # 6. Fallback: Find ANY standalone number (but avoid Transaction IDs, UPI IDs, timestamps)
        if not candidates:
            # Split into lines to check context
            lines = clean_text.split('\n')
            for line in lines:
                # Skip lines that look like timestamps (e.g., "06:13 pm on 24 Dec")
                if re.search(r'\d{1,2}:\d{2}\s*(am|pm)', line, re.IGNORECASE):
                    continue
                # Skip Transaction ID lines
                if re.search(r'Transaction\s*I?D', line, re.IGNORECASE):
                    continue
                # Skip UPI ID lines
                if '@' in line:
                    continue
                    
                # Look for standalone numbers in this line
                line_matches = re.finditer(r'\b(\d+(?:\.\d{1,2})?)\b', line)
                for match in line_matches:
                    try:
                        val = float(match.group(1))
                        # Must be reasonable transaction amount (10-100000), not a year
                        if 10 <= val < 100000 and not (2020 <= val <= 2030):
                             candidates.append((val, 10, match.start()))
                             logger.debug(f"Fallback found: ₹{val} in line '{line.strip()[:50]}'")
                    except ValueError:
                        continue

        if not candidates:
            logger.warning("No amount found in text")
            return None

        # Log all candidates before sorting
        if len(candidates) > 1:
            logger.debug(f"Found {len(candidates)} candidate amounts:")
            for amt, prio, pos in candidates:
                logger.debug(f"  - ₹{amt} (priority: {prio}, position: {pos})")

        # Sort by Priority (descending), then by Position (ascending to prefer earlier matches)
        candidates.sort(key=lambda x: (-x[1], x[2]))
        
        best_amount = candidates[0][0]
        logger.info(f"Final selected amount: ₹{best_amount} (priority: {candidates[0][1]}, position: {candidates[0][2]})")
        return best_amount
    
    def _parse_utr(self, text: str) -> Optional[str]:
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
    
    def _parse_recipient(self, text: str) -> Optional[str]:
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
    
    def _parse_upi_id(self, text: str) -> Optional[str]:
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
    
    def _parse_message(self, text: str) -> Optional[str]:
        """Extract transaction message using pattern matching.
        
        Looks for pattern: "Description - participant1 participant2"
        Can appear after "Message" keyword or in "Paid to" section (OCR may scramble text)
        Example: "Message Tea-me boops" → "Tea-me boops"
        Example: "Paid to Milk - me sarsan Transaction" → "Milk- me sarsan"
        
        Args:
            text: OCR extracted text
            
        Returns:
            Full message string (including description and participants) or None
        """
        # Strategy 1: Look for pattern after "Message" keyword (ideal case)
        # Try: Message on same line (PSM 11)
        pattern1 = r'Message\s+([A-Za-z0-9\s]+\s*-\s*[A-Za-z0-9\s]+?)(?=\s+(?:Transaction\s*I?D|Debited\s+from|UTR|Powered|$))'
        match = re.search(pattern1, text, re.IGNORECASE)
        
        if match:
            message = match.group(1).strip()
            message = re.sub(r'\s*-\s*', '- ', message)
            message = re.sub(r'\s+', ' ', message)
            logger.debug(f"Found message after 'Message' keyword: '{message}'")
            return message
        
        # Try: Message on separate line (PSM 3, 4, 6)
        pattern2 = r'Message\s*\n\s*([A-Za-z0-9\s]+\s*-\s*[A-Za-z0-9\s]+?)(?=\s*\n|$)'
        match = re.search(pattern2, text, re.IGNORECASE)
        
        if match:
            message = match.group(1).strip()
            message = re.sub(r'\s*-\s*', '- ', message)
            message = re.sub(r'\s+', ' ', message)
            logger.debug(f"Found message after 'Message' label: '{message}'")
            return message
        
        # Strategy 2: Look for pattern in "Paid to" section (fallback for scrambled OCR)
        # OCR sometimes puts message content in wrong place
        pattern3 = r'Paid\s+to\s+([A-Za-z0-9\s]+\s*-\s*[A-Za-z\s]+?)(?=\s+(?:Transaction\s*I?D|Debited|UTR|Payment|$))'
        match = re.search(pattern3, text, re.IGNORECASE)
        
        if match:
            message = match.group(1).strip()
            message = re.sub(r'\s*-\s*', '- ', message)
            message = re.sub(r'\s+', ' ', message)
            logger.debug(f"Found message in 'Paid to' section: '{message}'")
            return message
        
        logger.warning("No message found matching pattern 'Description- participants'")
        return None
    
    def _parse_participants(self, message: str) -> List[str]:
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
                        logger.debug("Skipping 'me' (current user)")
                        continue
                    
                    # Skip numbers (standalone digits)
                    if clean_word.isdigit():
                        continue
                    
                    # Skip common stop words and transaction-related terms
                    stop_words = {
                        'and', 'with', 'for', 'to', 'from', 'in', 'at', 'the', 'a', 'an', 'split',
                        'transaction', 'id', 'debited', 'utr', 'powered', 'by', 'bank', 
                        'transfer', 'payment', 'details', 'ves', 'lia', 'message'
                    }
                    if clean_word in stop_words:
                        continue
                    
                    # Skip if it contains many X's (account numbers like XXXXXXXXXXXYI362)
                    if clean_word.count('x') > 3:
                        continue
                    
                    # Skip if it's very long (likely transaction ID or account number)
                    if len(clean_word) > 15:
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
        
        logger.debug("No participants found - message doesn't match 'Description- participants' pattern")
        return []
    
    def _parse_account_number(self, text: str) -> Optional[str]:
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
    
    def _parse_timestamp(self, text: str) -> Optional[str]:
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
    
    def _parse_date(self, text: str) -> Optional[str]:
        """Parse payment date from text and convert to ISO 8601 format.
        
        Args:
            text: OCR extracted text
            
        Returns:
            ISO 8601 formatted date string (e.g., "2025-12-21T19:12:00Z") or None
        """
        timestamp_str = self._parse_timestamp(text)
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
            text = self._extract_text(image_path)

            if not text:
                logger.warning(f"No text extracted from {image_path}")
                return details

            # Parse individual fields
            details.amount = self._parse_amount(text)
            details.recipient = self._parse_recipient(text)
            details.recipient_upi = self._parse_upi_id(text)
            details.message = self._parse_message(text)
            details.utr = self._parse_utr(text)
            details.transaction_id = details.utr
            details.account_number = self._parse_account_number(text)
            details.timestamp = self._parse_timestamp(text)
            details.date = self._parse_date(text)

            # Parse participants from message
            if details.message:
                details.participants = self._parse_participants(details.message)
            
            # Log what was extracted
            logger.info(f"Parsed transaction details: {details}")
            if not details.amount:
                logger.warning("Amount not extracted! Showing first 500 chars of OCR text for debugging:")
                logger.warning(text[:500])
            
            return details
            
        except Exception as e:
            logger.error(f"Error parsing image {image_path}: {e}", exc_info=True)
            return details

