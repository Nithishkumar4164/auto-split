"""UTR tracker for maintaining uniqueness of processed transactions."""
import json
import logging
from typing import Dict, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class UTRTracker:
    """Tracker for managing processed UTR numbers to prevent duplicates."""
    
    def __init__(self, tracking_file: str = 'processed_utrs.json'):
        """Initialize UTR tracker.
        
        Args:
            tracking_file: Path to UTR tracking JSON file
        """
        self.tracking_file = tracking_file
        self.processed_utrs: Dict[str, Dict] = {}
        self.load_utrs()
    
    def load_utrs(self) -> None:
        """Load processed UTRs from JSON file."""
        try:
            with open(self.tracking_file, 'r') as f:
                self.processed_utrs = json.load(f)
            logger.info(f"Loaded {len(self.processed_utrs)} processed UTRs")
        except FileNotFoundError:
            logger.info(f"UTR tracking file not found, creating new: {self.tracking_file}")
            self.processed_utrs = {}
        except json.JSONDecodeError as e:
            logger.error(f"Error parsing UTR tracking file: {e}")
            self.processed_utrs = {}
    
    def save_utrs(self) -> None:
        """Save processed UTRs to JSON file."""
        try:
            with open(self.tracking_file, 'w') as f:
                json.dump(self.processed_utrs, f, indent=2)
            logger.info(f"Saved {len(self.processed_utrs)} processed UTRs")
        except Exception as e:
            logger.error(f"Error saving UTR tracking file: {e}")
    
    def is_processed(self, utr: str) -> bool:
        """Check if UTR has been processed.
        
        Args:
            utr: UTR number to check
            
        Returns:
            True if already processed, False otherwise
        """
        return utr in self.processed_utrs
    
    def add_utr(self, utr: str, amount: float, expense_id: Optional[str] = None,
                group_name: Optional[str] = None, participants: Optional[list] = None) -> None:
        """Add a processed UTR to tracking.
        
        Args:
            utr: UTR number
            amount: Transaction amount
            expense_id: Splitwise expense ID
            group_name: Group name
            participants: List of participants
        """
        self.processed_utrs[utr] = {
            'amount': amount,
            'expense_id': expense_id,
            'group_name': group_name,
            'participants': participants or [],
            'processed_at': datetime.now().isoformat()
        }
        self.save_utrs()
        logger.info(f"Added UTR {utr} to tracking")
    
    def get_utr_info(self, utr: str) -> Optional[Dict]:
        """Get information about a processed UTR.
        
        Args:
            utr: UTR number
            
        Returns:
            Dictionary with UTR information or None
        """
        return self.processed_utrs.get(utr)
    
    def remove_utr(self, utr: str) -> bool:
        """Remove a UTR from tracking (for reprocessing).
        
        Args:
            utr: UTR number to remove
            
        Returns:
            True if removed, False if not found
        """
        if utr in self.processed_utrs:
            del self.processed_utrs[utr]
            self.save_utrs()
            logger.info(f"Removed UTR {utr} from tracking")
            return True
        
        return False
    
    def get_all_utrs(self) -> Dict[str, Dict]:
        """Get all processed UTRs.
        
        Returns:
            Dictionary of all processed UTRs
        """
        return self.processed_utrs.copy()

