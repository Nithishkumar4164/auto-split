"""Base class for Splitwise integrations."""
from abc import ABC, abstractmethod
from typing import Dict, List, Optional


class SplitwiseBase(ABC):
    """Abstract base class for Splitwise integrations."""
    
    @abstractmethod
    def create_expense(
        self,
        description: str,
        cost: float,
        participants: List[str],
        group_id: Optional[str] = None,
        image_path: Optional[str] = None,
        all_aliases: Optional[Dict[str, List[str]]] = None,
        date: Optional[str] = None
    ) -> Dict:
        """Create a Splitwise expense.
        
        Args:
            description: Expense description
            cost: Total cost of expense
            participants: List of participant names detected from transaction
            group_id: Splitwise group ID (optional)
            image_path: Path to image file to attach (optional)
            all_aliases: Dictionary mapping canonical names to aliases (optional)
            date: ISO 8601 formatted date string (optional, e.g., "2025-12-21T19:12:00Z")
            
        Returns:
            Response dict with success status and expense details
        """
        pass
    
    @abstractmethod
    def get_groups(self) -> List[Dict]:
        """Get list of Splitwise groups.
        
        Returns:
            List of groups
        """
        pass
    
    @abstractmethod
    def find_group_by_name(self, group_name: str) -> Optional[str]:
        """Find group ID by name.
        
        Args:
            group_name: Name of the group
            
        Returns:
            Group ID or None
        """
        pass
    
    @abstractmethod
    def prepare_expense_with_image(
        self,
        description: str,
        cost: float,
        participants: List[str],
        image_path: str,
        group_id: Optional[str] = None,
        all_aliases: Optional[Dict[str, List[str]]] = None,
        date: Optional[str] = None
    ) -> Dict:
        """Prepare expense creation with image attachment.
        
        Args:
            description: Expense description
            cost: Total cost
            participants: List of participants detected from transaction
            image_path: Path to transaction image
            group_id: Group ID (optional)
            all_aliases: Dictionary mapping canonical names to aliases (optional)
            date: ISO 8601 formatted date string (optional, e.g., "2025-12-21T19:12:00Z")
            
        Returns:
            Response dict
        """
        pass
