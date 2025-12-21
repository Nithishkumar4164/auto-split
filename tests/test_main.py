"""Tests for main application module."""
import pytest
import json
from unittest.mock import Mock, patch
from pathlib import Path

from main import app, processor


@pytest.fixture
def client():
    """Create Flask test client."""
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


class TestHealthEndpoint:
    """Tests for health check endpoint."""
    
    def test_health_check(self, client):
        """Test health check endpoint returns healthy status."""
        response = client.get('/health')
        data = json.loads(response.data)
        
        assert response.status_code == 200
        assert data['status'] == 'healthy'
        assert data['service'] == 'autosplit'


class TestProcessDriveEventEndpoint:
    """Tests for process drive event endpoint."""
    
    def test_process_drive_event_success(self, client):
        """Test processing drive event successfully."""
        with patch.object(processor, 'process_drive_event', return_value={'success': True}):
            response = client.post(
                '/process-drive-event',
                data=json.dumps({'id': 'file123', 'name': 'transaction.jpeg'}),
                content_type='application/json'
            )
            
            assert response.status_code == 200
            data = json.loads(response.data)
            assert data['success'] is True
    
    def test_process_drive_event_failure(self, client):
        """Test processing drive event with failure."""
        with patch.object(processor, 'process_drive_event', return_value={
            'success': False,
            'error': 'Processing failed'
        }):
            response = client.post(
                '/process-drive-event',
                data=json.dumps({'id': 'file123', 'name': 'transaction.jpeg'}),
                content_type='application/json'
            )
            
            assert response.status_code == 400
            data = json.loads(response.data)
            assert data['success'] is False
    
    def test_process_drive_event_no_data(self, client):
        """Test processing drive event with no data."""
        response = client.post('/process-drive-event')
        
        assert response.status_code == 400
        data = json.loads(response.data)
        assert data['success'] is False
    
    def test_process_drive_event_exception(self, client):
        """Test processing drive event with exception."""
        with patch.object(processor, 'process_drive_event', side_effect=Exception("Test error")):
            response = client.post(
                '/process-drive-event',
                data=json.dumps({'id': 'file123', 'name': 'transaction.jpeg'}),
                content_type='application/json'
            )
            
            assert response.status_code == 500


class TestProcessImageEndpoint:
    """Tests for manual image processing endpoint."""
    
    def test_process_image_success(self, client, tmp_path):
        """Test processing image successfully."""
        # Create temp image file
        image_file = tmp_path / "test.jpg"
        image_file.write_bytes(b"fake image")
        
        with patch.object(processor, 'process_image', return_value={'success': True}):
            response = client.post(
                '/process-image',
                data=json.dumps({
                    'image_path': str(image_file),
                    'group_name': 'TestGroup'
                }),
                content_type='application/json'
            )
            
            assert response.status_code == 200
            data = json.loads(response.data)
            assert data['success'] is True
    
    def test_process_image_no_image_path(self, client):
        """Test processing image without image path."""
        response = client.post(
            '/process-image',
            data=json.dumps({'group_name': 'TestGroup'}),
            content_type='application/json'
        )
        
        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'image_path is required' in data['error']
    
    def test_process_image_file_not_found(self, client):
        """Test processing image with non-existent file."""
        response = client.post(
            '/process-image',
            data=json.dumps({'image_path': '/nonexistent/image.jpg'}),
            content_type='application/json'
        )
        
        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'File not found' in data['error']
    
    def test_process_image_exception(self, client, tmp_path):
        """Test processing image with exception."""
        image_file = tmp_path / "test.jpg"
        image_file.write_bytes(b"fake image")
        
        with patch.object(processor, 'process_image', side_effect=Exception("Test error")):
            response = client.post(
                '/process-image',
                data=json.dumps({'image_path': str(image_file)}),
                content_type='application/json'
            )
            
            assert response.status_code == 500


class TestAliasesEndpoints:
    """Tests for aliases management endpoints."""
    
    def test_get_aliases(self, client):
        """Test getting all aliases."""
        from main import alias_manager
        
        with patch.object(alias_manager, 'aliases', {'User1': ['alias1']}):
            response = client.get('/aliases')
            
            assert response.status_code == 200
            data = json.loads(response.data)
            assert data['success'] is True
            assert 'aliases' in data
    
    def test_add_alias_success(self, client):
        """Test adding alias successfully."""
        from main import alias_manager
        
        with patch.object(alias_manager, 'add_alias'):
            response = client.post(
                '/aliases',
                data=json.dumps({
                    'canonical_name': 'John Doe',
                    'alias': 'john'
                }),
                content_type='application/json'
            )
            
            assert response.status_code == 200
            data = json.loads(response.data)
            assert data['success'] is True
    
    def test_add_alias_missing_data(self, client):
        """Test adding alias with missing data."""
        response = client.post(
            '/aliases',
            data=json.dumps({'canonical_name': 'John Doe'}),
            content_type='application/json'
        )
        
        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'canonical_name and alias are required' in data['error']
    
    def test_add_alias_exception(self, client):
        """Test adding alias with exception."""
        from main import alias_manager
        
        with patch.object(alias_manager, 'add_alias', side_effect=Exception("Test error")):
            response = client.post(
                '/aliases',
                data=json.dumps({
                    'canonical_name': 'John Doe',
                    'alias': 'john'
                }),
                content_type='application/json'
            )
            
            assert response.status_code == 500


class TestUTRsEndpoint:
    """Tests for UTRs endpoint."""
    
    def test_get_utrs(self, client):
        """Test getting all UTRs."""
        from main import utr_tracker
        
        with patch.object(utr_tracker, 'get_all_utrs', return_value={
            '123456789012': {'amount': 500.0}
        }):
            response = client.get('/utrs')
            
            assert response.status_code == 200
            data = json.loads(response.data)
            assert data['success'] is True
            assert 'utrs' in data
    
    def test_get_utrs_exception(self, client):
        """Test getting UTRs with exception."""
        from main import utr_tracker
        
        with patch.object(utr_tracker, 'get_all_utrs', side_effect=Exception("Test error")):
            response = client.get('/utrs')
            
            assert response.status_code == 500

