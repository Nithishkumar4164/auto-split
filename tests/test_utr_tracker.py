"""Tests for UTR tracker module."""
import pytest
import json
import os
from datetime import datetime

from utr_tracker import UTRTracker


class TestUTRTracker:
    """Tests for UTRTracker class."""
    
    @pytest.fixture
    def temp_tracking_file(self, tmp_path):
        """Create temporary tracking file."""
        tracking_file = tmp_path / "processed_utrs.json"
        return str(tracking_file)
    
    @pytest.fixture
    def sample_utrs(self):
        """Sample UTR data."""
        return {
            "987654321098": {
                "amount": 460.0,
                "expense_id": "exp_123",
                "group_name": "Roommates",
                "participants": ["Alex Boops"],
                "processed_at": "2025-12-19T15:17:00"
            }
        }
    
    def test_initialization_no_file(self, temp_tracking_file):
        """Test initialization when tracking file doesn't exist."""
        tracker = UTRTracker(temp_tracking_file)
        
        assert tracker.processed_utrs == {}
    
    def test_initialization_with_file(self, temp_tracking_file, sample_utrs):
        """Test initialization with existing tracking file."""
        # Write sample UTRs to file
        with open(temp_tracking_file, 'w') as f:
            json.dump(sample_utrs, f)
        
        tracker = UTRTracker(temp_tracking_file)
        
        assert tracker.processed_utrs == sample_utrs
    
    def test_is_processed_true(self, temp_tracking_file, sample_utrs):
        """Test is_processed returns True for processed UTR."""
        # Write sample UTRs to file
        with open(temp_tracking_file, 'w') as f:
            json.dump(sample_utrs, f)
        
        tracker = UTRTracker(temp_tracking_file)
        
        assert tracker.is_processed("987654321098") is True
    
    def test_is_processed_false(self, temp_tracking_file):
        """Test is_processed returns False for new UTR."""
        tracker = UTRTracker(temp_tracking_file)
        
        assert tracker.is_processed("999999999999") is False
    
    def test_add_utr_basic(self, temp_tracking_file):
        """Test adding a UTR with basic information."""
        tracker = UTRTracker(temp_tracking_file)
        
        tracker.add_utr("123456789012", 500.0)
        
        assert "123456789012" in tracker.processed_utrs
        assert tracker.processed_utrs["123456789012"]["amount"] == 500.0
    
    def test_add_utr_full_info(self, temp_tracking_file):
        """Test adding a UTR with full information."""
        tracker = UTRTracker(temp_tracking_file)
        
        tracker.add_utr(
            utr="123456789012",
            amount=500.0,
            expense_id="exp_456",
            group_name="TestGroup",
            participants=["John", "Jane"]
        )
        
        utr_info = tracker.processed_utrs["123456789012"]
        assert utr_info["amount"] == 500.0
        assert utr_info["expense_id"] == "exp_456"
        assert utr_info["group_name"] == "TestGroup"
        assert "John" in utr_info["participants"]
        assert "Jane" in utr_info["participants"]
        assert "processed_at" in utr_info
    
    def test_add_utr_timestamp(self, temp_tracking_file):
        """Test that adding UTR includes timestamp."""
        tracker = UTRTracker(temp_tracking_file)
        
        before = datetime.now()
        tracker.add_utr("123456789012", 500.0)
        after = datetime.now()
        
        utr_info = tracker.processed_utrs["123456789012"]
        processed_time = datetime.fromisoformat(utr_info["processed_at"])
        
        assert before <= processed_time <= after
    
    def test_get_utr_info_exists(self, temp_tracking_file, sample_utrs):
        """Test getting info for existing UTR."""
        # Write sample UTRs to file
        with open(temp_tracking_file, 'w') as f:
            json.dump(sample_utrs, f)
        
        tracker = UTRTracker(temp_tracking_file)
        
        info = tracker.get_utr_info("987654321098")
        
        assert info is not None
        assert info["amount"] == 460.0
        assert info["group_name"] == "Roommates"
    
    def test_get_utr_info_not_exists(self, temp_tracking_file):
        """Test getting info for non-existent UTR."""
        tracker = UTRTracker(temp_tracking_file)
        
        info = tracker.get_utr_info("999999999999")
        
        assert info is None
    
    def test_remove_utr_success(self, temp_tracking_file, sample_utrs):
        """Test removing an existing UTR."""
        # Write sample UTRs to file
        with open(temp_tracking_file, 'w') as f:
            json.dump(sample_utrs, f)
        
        tracker = UTRTracker(temp_tracking_file)
        
        result = tracker.remove_utr("987654321098")
        
        assert result is True
        assert "987654321098" not in tracker.processed_utrs
    
    def test_remove_utr_not_found(self, temp_tracking_file):
        """Test removing non-existent UTR."""
        tracker = UTRTracker(temp_tracking_file)
        
        result = tracker.remove_utr("999999999999")
        
        assert result is False
    
    def test_get_all_utrs(self, temp_tracking_file, sample_utrs):
        """Test getting all UTRs."""
        # Write sample UTRs to file
        with open(temp_tracking_file, 'w') as f:
            json.dump(sample_utrs, f)
        
        tracker = UTRTracker(temp_tracking_file)
        
        all_utrs = tracker.get_all_utrs()
        
        assert "987654321098" in all_utrs
        assert all_utrs["987654321098"]["amount"] == 460.0
    
    def test_get_all_utrs_returns_copy(self, temp_tracking_file, sample_utrs):
        """Test that get_all_utrs returns a copy, not reference."""
        # Write sample UTRs to file
        with open(temp_tracking_file, 'w') as f:
            json.dump(sample_utrs, f)
        
        tracker = UTRTracker(temp_tracking_file)
        
        all_utrs = tracker.get_all_utrs()
        all_utrs["999999999999"] = {"test": "data"}
        
        # Original should not be modified
        assert "999999999999" not in tracker.processed_utrs
    
    def test_persistence_across_instances(self, temp_tracking_file):
        """Test that UTRs persist across tracker instances."""
        # Create first tracker and add UTR
        tracker1 = UTRTracker(temp_tracking_file)
        tracker1.add_utr("123456789012", 500.0, expense_id="exp_789")
        
        # Create second tracker and verify UTR is loaded
        tracker2 = UTRTracker(temp_tracking_file)
        
        assert tracker2.is_processed("123456789012")
        assert tracker2.get_utr_info("123456789012")["expense_id"] == "exp_789"
    
    def test_add_multiple_utrs(self, temp_tracking_file):
        """Test adding multiple UTRs."""
        tracker = UTRTracker(temp_tracking_file)
        
        tracker.add_utr("111111111111", 100.0)
        tracker.add_utr("222222222222", 200.0)
        tracker.add_utr("333333333333", 300.0)
        
        assert len(tracker.processed_utrs) == 3
        assert tracker.is_processed("111111111111")
        assert tracker.is_processed("222222222222")
        assert tracker.is_processed("333333333333")

