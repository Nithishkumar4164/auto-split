"""Tests for Splitwise client module."""
import pytest
from unittest.mock import Mock, patch

from splitwise_client import SplitwiseClient


class TestSplitwiseClient:
    """Tests for SplitwiseClient class."""
    
    @pytest.fixture
    def mock_mcp_handler(self):
        """Create mock MCP handler."""
        return Mock()
    
    @pytest.fixture
    def client(self, mock_mcp_handler):
        """Create SplitwiseClient instance."""
        return SplitwiseClient(mock_mcp_handler)
    
    def test_initialization(self, mock_mcp_handler):
        """Test SplitwiseClient initialization."""
        client = SplitwiseClient(mock_mcp_handler)
        
        assert client.mcp_handler == mock_mcp_handler
    
    def test_create_expense_basic(self, client):
        """Test creating basic expense."""
        result = client.create_expense(
            description="Dinner",
            cost=500.0,
            participants=["John", "Jane"]
        )
        
        assert result['success'] is True
        assert 'mcp_params' in result
        assert result['mcp_params']['description'] == "Dinner"
        assert result['mcp_params']['cost'] == "500.0"
    
    def test_create_expense_with_group(self, client):
        """Test creating expense with group."""
        result = client.create_expense(
            description="Groceries",
            cost=1000.0,
            participants=["Alice", "Bob"],
            group_id="group_123"
        )
        
        assert result['success'] is True
        assert result['mcp_params']['group_id'] == "group_123"
    
    def test_create_expense_with_image(self, client):
        """Test creating expense with image."""
        result = client.create_expense(
            description="Shopping",
            cost=750.0,
            participants=["User1"],
            image_path="/path/to/image.jpg"
        )
        
        assert result['success'] is True
        assert 'mcp_params' in result
    
    def test_build_instructions_basic(self, client):
        """Test building instructions for basic expense."""
        instructions = client._build_instructions(
            description="Lunch",
            cost=300.0,
            participants=["Alice", "Bob"]
        )
        
        assert "Lunch" in instructions
        assert "₹300" in instructions
        assert "Alice" in instructions
        assert "Bob" in instructions
        assert "outside of any group" in instructions
    
    def test_build_instructions_with_group(self, client):
        """Test building instructions with group."""
        instructions = client._build_instructions(
            description="Dinner",
            cost=500.0,
            participants=["John"],
            group_id="group_456"
        )
        
        assert "group ID group_456" in instructions
        assert "outside of any group" not in instructions
    
    def test_build_instructions_with_image(self, client):
        """Test building instructions with image path."""
        instructions = client._build_instructions(
            description="Event",
            cost=1000.0,
            participants=["User1"],
            image_path="/path/to/receipt.jpg"
        )
        
        assert "Attach the image" in instructions
        assert "/path/to/receipt.jpg" in instructions
    
    def test_get_groups(self, client):
        """Test getting groups list."""
        groups = client.get_groups()
        
        # Currently returns empty list as placeholder
        assert isinstance(groups, list)
    
    def test_find_group_by_name_found(self, client):
        """Test finding group by name when it exists."""
        with patch.object(client, 'get_groups', return_value=[
            {'id': 'g1', 'name': 'Roommates'},
            {'id': 'g2', 'name': 'Friends'}
        ]):
            group_id = client.find_group_by_name('Roommates')
            
            assert group_id == 'g1'
    
    def test_find_group_by_name_not_found(self, client):
        """Test finding group by name when it doesn't exist."""
        with patch.object(client, 'get_groups', return_value=[
            {'id': 'g1', 'name': 'Roommates'}
        ]):
            group_id = client.find_group_by_name('NonExistent')
            
            assert group_id is None
    
    def test_find_group_by_name_case_insensitive(self, client):
        """Test finding group by name is case insensitive."""
        with patch.object(client, 'get_groups', return_value=[
            {'id': 'g1', 'name': 'Roommates'}
        ]):
            group_id = client.find_group_by_name('roommates')
            
            assert group_id == 'g1'
    
    def test_upload_image_success(self, client, tmp_path):
        """Test uploading image successfully."""
        # Create a temporary image file
        image_file = tmp_path / "test_image.jpg"
        image_file.write_bytes(b"fake image data")
        
        result = client.upload_image(str(image_file))
        
        assert result is not None
    
    def test_upload_image_not_found(self, client):
        """Test uploading non-existent image."""
        result = client.upload_image("/nonexistent/image.jpg")
        
        assert result is None
    
    def test_prepare_expense_with_image(self, client, tmp_path):
        """Test preparing expense with image attachment."""
        # Create a temporary image file
        image_file = tmp_path / "transaction.jpg"
        image_file.write_bytes(b"fake transaction image")
        
        with patch.object(client, 'upload_image', return_value=str(image_file)):
            result = client.prepare_expense_with_image(
                description="Payment",
                cost=460.0,
                participants=["Alex"],
                image_path=str(image_file)
            )
            
            assert 'success' in result
    
    def test_prepare_expense_with_image_and_group(self, client, tmp_path):
        """Test preparing expense with image and group."""
        # Create a temporary image file
        image_file = tmp_path / "transaction.jpg"
        image_file.write_bytes(b"fake transaction image")
        
        with patch.object(client, 'upload_image', return_value=str(image_file)):
            result = client.prepare_expense_with_image(
                description="Group expense",
                cost=1000.0,
                participants=["User1", "User2"],
                image_path=str(image_file),
                group_id="group_789"
            )
            
            assert 'success' in result
    
    def test_create_expense_exception_handling(self, client):
        """Test exception handling in create_expense."""
        with patch.object(client, '_build_instructions', side_effect=Exception("Test error")):
            result = client.create_expense(
                description="Test",
                cost=100.0,
                participants=["User"]
            )
            
            assert result['success'] is False
            assert 'error' in result

