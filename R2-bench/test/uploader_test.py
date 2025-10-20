"""
Test script for the uploader streaming functionality.
"""

import sys
import os
import unittest
from unittest.mock import Mock, patch, MagicMock
from configuration import BYTES_PER_GB, RANGE_SIZE_MB, BYTES_PER_MB

# Mock boto3 before any imports that might use it
sys.modules['boto3'] = Mock()
sys.modules['botocore'] = Mock()
sys.modules['botocore.exceptions'] = Mock()

# Add the parent directory to Python path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cli.uploader import Uploader


class TestUploader(unittest.TestCase):
    """Test cases for Uploader class."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Mock the storage system to avoid actual connections
        with patch('cli.uploader.R2System') as mock_r2_class, \
             patch('cli.uploader.AWSSystem') as mock_aws_class:
            
            # Create mock storage system
            self.mock_storage = Mock()
            mock_r2_class.return_value = self.mock_storage
            mock_aws_class.return_value = self.mock_storage
            
            # Create uploader instance
            self.uploader = Uploader("r2")
    
    def test_generate_test_data_generator(self):
        """Test that generate_test_data returns a generator."""
        generator = self.uploader.generate_test_data(1)  # 1 GB
        
        # Check it's a generator
        self.assertTrue(hasattr(generator, '__iter__'))
        
        # Check it yields bytes
        first_chunk = next(generator)
        self.assertIsInstance(first_chunk, bytes)
        
        # Check chunk size is reasonable (100MB)
        from configuration import RANGE_SIZE_MB, BYTES_PER_MB
        self.assertLessEqual(len(first_chunk), RANGE_SIZE_MB * BYTES_PER_MB)
    
    def test_generate_test_data_size(self):
        """Test that generate_test_data generates the correct total size."""
        size_gb = 2
        generator = self.uploader.generate_test_data(size_gb)
        
        total_size = 0
        chunk_count = 0
        
        for chunk in generator:
            total_size += len(chunk)
            chunk_count += 1
        
        # Check total size is approximately correct (within 1MB tolerance)
        from configuration import BYTES_PER_GB, BYTES_PER_MB
        expected_size = size_gb * BYTES_PER_GB
        self.assertAlmostEqual(total_size, expected_size, delta=BYTES_PER_MB)
        
        # Check we have multiple chunks
        self.assertGreater(chunk_count, 1)
    
    def test_upload_test_object_streaming(self):
        """Test that upload_test_object uses streaming."""
        # Mock the storage system's streaming upload method
        self.mock_storage.upload_object_streaming.return_value = True
        
        # Test upload
        success = self.uploader.upload_test_object(1)  # 1 GB
        
        # Verify streaming method was called
        self.mock_storage.upload_object_streaming.assert_called_once()
        
        # Check the call arguments
        from configuration import BYTES_PER_GB
        call_args = self.mock_storage.upload_object_streaming.call_args
        self.assertEqual(call_args[0][0], "test-object-1gb")  # object key
        self.assertEqual(call_args[0][2], BYTES_PER_GB)  # total size in bytes
        
        # Check success
        self.assertTrue(success)
    
    def test_upload_test_object_failure(self):
        """Test upload failure handling."""
        # Mock the storage system to return failure
        self.mock_storage.upload_object_streaming.return_value = False
        
        # Test upload
        success = self.uploader.upload_test_object(1)
        
        # Check failure
        self.assertFalse(success)
    
    def test_upload_test_object_exception(self):
        """Test exception handling during upload."""
        # Mock the storage system to raise an exception
        self.mock_storage.upload_object_streaming.side_effect = Exception("Upload failed")
        
        # Test upload
        success = self.uploader.upload_test_object(1)
        
        # Check failure
        self.assertFalse(success)
    
    def test_upload_test_object_custom_key(self):
        """Test upload with custom object key."""
        # Mock the storage system's streaming upload method
        self.mock_storage.upload_object_streaming.return_value = True
        
        # Test upload with custom object key
        custom_key = "my-custom-test-object"
        success = self.uploader.upload_test_object(1, custom_key)
        
        # Verify streaming method was called
        self.mock_storage.upload_object_streaming.assert_called_once()
        
        # Check the call arguments
        call_args = self.mock_storage.upload_object_streaming.call_args
        self.assertEqual(call_args[0][0], custom_key)  # custom object key
        self.assertEqual(call_args[0][2], BYTES_PER_GB)  # total size in bytes
        
        # Check success
        self.assertTrue(success)


if __name__ == '__main__':
    unittest.main()
