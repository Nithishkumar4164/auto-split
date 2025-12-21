"""Tests for alias manager module."""
import pytest
import json
import os
from unittest.mock import Mock, patch, mock_open

from alias_manager import AliasManager


class TestAliasManager:
    """Tests for AliasManager class."""
    
    @pytest.fixture
    def temp_aliases_file(self, tmp_path):
        """Create temporary aliases file."""
        aliases_file = tmp_path / "aliases.json"
        return str(aliases_file)
    
    @pytest.fixture
    def sample_aliases(self):
        """Sample aliases data."""
        return {
            "Alex Boops": ["alex", "alexboops", "alex boops"],
            "John Doe": ["john", "johnny", "jd"],
            "Jane Smith": ["jane", "janey"]
        }
    
    def test_initialization_no_file(self, temp_aliases_file):
        """Test initialization when aliases file doesn't exist."""
        manager = AliasManager(temp_aliases_file)
        
        assert manager.aliases == {}
    
    def test_initialization_with_file(self, temp_aliases_file, sample_aliases):
        """Test initialization with existing aliases file."""
        # Write sample aliases to file
        with open(temp_aliases_file, 'w') as f:
            json.dump(sample_aliases, f)
        
        manager = AliasManager(temp_aliases_file)
        
        assert manager.aliases == sample_aliases
    
    def test_add_alias_new_canonical(self, temp_aliases_file):
        """Test adding alias for new canonical name."""
        manager = AliasManager(temp_aliases_file)
        
        manager.add_alias("Bob Brown", "bob")
        
        assert "Bob Brown" in manager.aliases
        assert "bob" in manager.aliases["Bob Brown"]
    
    def test_add_alias_existing_canonical(self, temp_aliases_file, sample_aliases):
        """Test adding alias to existing canonical name."""
        # Write sample aliases to file
        with open(temp_aliases_file, 'w') as f:
            json.dump(sample_aliases, f)
        
        manager = AliasManager(temp_aliases_file)
        manager.add_alias("John Doe", "jonny")
        
        assert "jonny" in manager.aliases["John Doe"]
    
    def test_add_alias_duplicate(self, temp_aliases_file, sample_aliases):
        """Test adding duplicate alias doesn't create duplicates."""
        # Write sample aliases to file
        with open(temp_aliases_file, 'w') as f:
            json.dump(sample_aliases, f)
        
        manager = AliasManager(temp_aliases_file)
        manager.add_alias("John Doe", "john")
        
        # Count occurrences of 'john'
        count = manager.aliases["John Doe"].count("john")
        assert count == 1
    
    def test_get_canonical_name_exact_match(self, temp_aliases_file, sample_aliases):
        """Test getting canonical name with exact match."""
        # Write sample aliases to file
        with open(temp_aliases_file, 'w') as f:
            json.dump(sample_aliases, f)
        
        manager = AliasManager(temp_aliases_file)
        
        canonical = manager.get_canonical_name("john")
        
        assert canonical == "John Doe"
    
    def test_get_canonical_name_case_insensitive(self, temp_aliases_file, sample_aliases):
        """Test getting canonical name is case insensitive."""
        # Write sample aliases to file
        with open(temp_aliases_file, 'w') as f:
            json.dump(sample_aliases, f)
        
        manager = AliasManager(temp_aliases_file)
        
        canonical = manager.get_canonical_name("JOHN")
        
        assert canonical == "John Doe"
    
    def test_get_canonical_name_fuzzy_match(self, temp_aliases_file, sample_aliases):
        """Test getting canonical name with fuzzy matching."""
        # Write sample aliases to file
        with open(temp_aliases_file, 'w') as f:
            json.dump(sample_aliases, f)
        
        manager = AliasManager(temp_aliases_file)
        
        # "johnny" should match "johnny" alias or "john"
        canonical = manager.get_canonical_name("johny", threshold=70)
        
        assert canonical == "John Doe"
    
    def test_get_canonical_name_no_match(self, temp_aliases_file, sample_aliases):
        """Test getting canonical name with no match."""
        # Write sample aliases to file
        with open(temp_aliases_file, 'w') as f:
            json.dump(sample_aliases, f)
        
        manager = AliasManager(temp_aliases_file)
        
        canonical = manager.get_canonical_name("unknown person", threshold=80)
        
        assert canonical is None
    
    def test_get_canonical_name_empty_string(self, temp_aliases_file):
        """Test getting canonical name with empty string."""
        manager = AliasManager(temp_aliases_file)
        
        canonical = manager.get_canonical_name("")
        
        assert canonical is None
    
    def test_match_participants_single(self, temp_aliases_file, sample_aliases):
        """Test matching single participant."""
        # Write sample aliases to file
        with open(temp_aliases_file, 'w') as f:
            json.dump(sample_aliases, f)
        
        manager = AliasManager(temp_aliases_file)
        
        matched = manager.match_participants(["alex"])
        
        assert "Alex Boops" in matched
    
    def test_match_participants_multiple(self, temp_aliases_file, sample_aliases):
        """Test matching multiple participants."""
        # Write sample aliases to file
        with open(temp_aliases_file, 'w') as f:
            json.dump(sample_aliases, f)
        
        manager = AliasManager(temp_aliases_file)
        
        matched = manager.match_participants(["alex", "john", "jane"])
        
        assert "Alex Boops" in matched
        assert "John Doe" in matched
        assert "Jane Smith" in matched
    
    def test_match_participants_no_duplicates(self, temp_aliases_file, sample_aliases):
        """Test matching participants doesn't return duplicates."""
        # Write sample aliases to file
        with open(temp_aliases_file, 'w') as f:
            json.dump(sample_aliases, f)
        
        manager = AliasManager(temp_aliases_file)
        
        matched = manager.match_participants(["john", "johnny", "jd"])
        
        # All should match to "John Doe" but only appear once
        assert matched.count("John Doe") == 1
    
    def test_match_participants_partial_matches(self, temp_aliases_file, sample_aliases):
        """Test matching participants with some unknowns."""
        # Write sample aliases to file
        with open(temp_aliases_file, 'w') as f:
            json.dump(sample_aliases, f)
        
        manager = AliasManager(temp_aliases_file)
        
        matched = manager.match_participants(["john", "unknown", "jane"])
        
        assert "John Doe" in matched
        assert "Jane Smith" in matched
        # Unknown should not match
    
    def test_get_all_canonical_names(self, temp_aliases_file, sample_aliases):
        """Test getting all canonical names."""
        # Write sample aliases to file
        with open(temp_aliases_file, 'w') as f:
            json.dump(sample_aliases, f)
        
        manager = AliasManager(temp_aliases_file)
        
        names = manager.get_all_canonical_names()
        
        assert "Alex Boops" in names
        assert "John Doe" in names
        assert "Jane Smith" in names
        assert len(names) == 3
    
    def test_remove_alias_success(self, temp_aliases_file, sample_aliases):
        """Test removing an alias successfully."""
        # Write sample aliases to file
        with open(temp_aliases_file, 'w') as f:
            json.dump(sample_aliases, f)
        
        manager = AliasManager(temp_aliases_file)
        
        result = manager.remove_alias("John Doe", "johnny")
        
        assert result is True
        assert "johnny" not in manager.aliases["John Doe"]
    
    def test_remove_alias_not_found(self, temp_aliases_file, sample_aliases):
        """Test removing non-existent alias."""
        # Write sample aliases to file
        with open(temp_aliases_file, 'w') as f:
            json.dump(sample_aliases, f)
        
        manager = AliasManager(temp_aliases_file)
        
        result = manager.remove_alias("John Doe", "nonexistent")
        
        assert result is False
    
    def test_remove_alias_unknown_canonical(self, temp_aliases_file, sample_aliases):
        """Test removing alias from unknown canonical name."""
        # Write sample aliases to file
        with open(temp_aliases_file, 'w') as f:
            json.dump(sample_aliases, f)
        
        manager = AliasManager(temp_aliases_file)
        
        result = manager.remove_alias("Unknown Person", "alias")
        
        assert result is False
    
    def test_save_and_load_persistence(self, temp_aliases_file):
        """Test that aliases persist across instances."""
        # Create first manager and add alias
        manager1 = AliasManager(temp_aliases_file)
        manager1.add_alias("Test User", "test")
        
        # Create second manager and verify alias is loaded
        manager2 = AliasManager(temp_aliases_file)
        
        assert "Test User" in manager2.aliases
        assert "test" in manager2.aliases["Test User"]

