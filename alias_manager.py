"""Alias manager for mapping participant names to Splitwise users."""
import json
import logging
from typing import Dict, List, Optional
from fuzzywuzzy import fuzz, process

logger = logging.getLogger(__name__)


class AliasManager:
    """Manager for handling participant name aliases and fuzzy matching."""
    
    def __init__(self, aliases_file: str = 'aliases.json'):
        """Initialize alias manager.
        
        Args:
            aliases_file: Path to aliases JSON file
        """
        self.aliases_file = aliases_file
        self.aliases: Dict[str, List[str]] = {}
        self.load_aliases()
    
    def load_aliases(self) -> None:
        """Load aliases from JSON file."""
        try:
            with open(self.aliases_file, 'r') as f:
                self.aliases = json.load(f)
            logger.info(f"Loaded {len(self.aliases)} alias mappings")
        except FileNotFoundError:
            logger.warning(f"Aliases file not found: {self.aliases_file}")
            self.aliases = {}
        except json.JSONDecodeError as e:
            logger.error(f"Error parsing aliases file: {e}")
            self.aliases = {}
    
    def save_aliases(self) -> None:
        """Save aliases to JSON file."""
        try:
            with open(self.aliases_file, 'w') as f:
                json.dump(self.aliases, f, indent=2)
            logger.info(f"Saved {len(self.aliases)} alias mappings")
        except Exception as e:
            logger.error(f"Error saving aliases file: {e}")
    
    def add_alias(self, canonical_name: str, alias: str) -> None:
        """Add a new alias mapping.
        
        Args:
            canonical_name: The official name in Splitwise
            alias: An alias for the canonical name
        """
        if canonical_name not in self.aliases:
            self.aliases[canonical_name] = []
        
        if alias not in self.aliases[canonical_name]:
            self.aliases[canonical_name].append(alias)
            self.save_aliases()
            logger.info(f"Added alias '{alias}' for '{canonical_name}'")
    
    def get_canonical_name(self, name: str, threshold: int = 80) -> Optional[str]:
        """Get canonical name for a given name or alias using fuzzy matching.
        
        Args:
            name: Name to look up
            threshold: Minimum similarity score (0-100)
            
        Returns:
            Canonical name or None if no match found
        """
        if not name:
            return None
        
        name_lower = name.lower().strip()
        
        # First, check for exact matches
        for canonical_name, aliases in self.aliases.items():
            if canonical_name.lower() == name_lower:
                return canonical_name
            
            for alias in aliases:
                if alias.lower() == name_lower:
                    return canonical_name
        
        # If no exact match, use fuzzy matching
        all_names = []
        name_to_canonical = {}
        
        for canonical_name, aliases in self.aliases.items():
            all_names.append(canonical_name)
            name_to_canonical[canonical_name.lower()] = canonical_name
            
            for alias in aliases:
                all_names.append(alias)
                name_to_canonical[alias.lower()] = canonical_name
        
        if not all_names:
            return None
        
        # Find best match
        best_match, score = process.extractOne(name, all_names, scorer=fuzz.ratio)
        
        if score >= threshold:
            canonical = name_to_canonical.get(best_match.lower())
            logger.info(f"Fuzzy matched '{name}' to '{canonical}' (score: {score})")
            return canonical
        
        logger.warning(f"No match found for '{name}' (best score: {score})")
        return None
    
    def match_participants(self, names: List[str], threshold: int = 80) -> List[str]:
        """Match a list of names to canonical names.
        
        Args:
            names: List of names to match
            threshold: Minimum similarity score (0-100)
            
        Returns:
            List of matched canonical names
        """
        matched = []
        
        for name in names:
            canonical = self.get_canonical_name(name, threshold)
            if canonical and canonical not in matched:
                matched.append(canonical)
        
        return matched
    
    def get_all_canonical_names(self) -> List[str]:
        """Get all canonical names.
        
        Returns:
            List of canonical names
        """
        return list(self.aliases.keys())
    
    def remove_alias(self, canonical_name: str, alias: str) -> bool:
        """Remove an alias mapping.
        
        Args:
            canonical_name: The canonical name
            alias: The alias to remove
            
        Returns:
            True if removed, False if not found
        """
        if canonical_name in self.aliases and alias in self.aliases[canonical_name]:
            self.aliases[canonical_name].remove(alias)
            self.save_aliases()
            logger.info(f"Removed alias '{alias}' for '{canonical_name}'")
            return True
        
        return False

