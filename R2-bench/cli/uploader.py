"""
Phase 0: Upload test objects to object storage.
"""

import os
import sys
import logging
import argparse
import time

# Add the current directory to Python path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from configuration import (
    OBJECT_SIZE_GB, R2_ENDPOINT, S3_ENDPOINT, RANGE_SIZE_MB,
    AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_REGION, DEFAULT_OBJECT_KEY,
    BYTES_PER_GB, BYTES_PER_MB
)
from systems.r2 import R2System
from systems.aws import AWSSystem

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class Uploader:
    """Simple uploader for test objects."""
    
    def __init__(self, storage_type: str):
        self.storage_type = storage_type.lower()
        self.storage_system = None
        
        # Initialize storage system
        self._initialize_storage()
        
        logger.info(f"Initialized uploader for {storage_type.upper()}")
    
    def _initialize_storage(self):
        """Initialize the appropriate storage system."""
        try:
            if self.storage_type == "r2":
                credentials = {
                    'aws_access_key_id': AWS_ACCESS_KEY_ID,
                    'aws_secret_access_key': AWS_SECRET_ACCESS_KEY,
                    'region_name': 'auto'
                }
                self.storage_system = R2System(credentials)
                
            elif self.storage_type == "s3":
                credentials = {
                    'aws_access_key_id': AWS_ACCESS_KEY_ID,
                    'aws_secret_access_key': AWS_SECRET_ACCESS_KEY,
                    'region_name': AWS_REGION
                }
                self.storage_system = AWSSystem(credentials)
                
            else:
                raise ValueError(f"Unsupported storage type: {self.storage_type}")
                
        except Exception as e:
            logger.error(f"Failed to initialize {self.storage_type.upper()} storage: {e}")
            raise
    
    def generate_test_data(self, size_gb: int):
        """Generate test data of specified size as a generator to avoid memory issues."""
        logger.info(f"Generating {size_gb} GB of test data in chunks")
        
        # Generate data in chunks to manage memory
        chunk_size = RANGE_SIZE_MB * BYTES_PER_MB  # Use configured chunk size
        total_size = size_gb * BYTES_PER_GB
        
        for i in range(0, total_size, chunk_size):
            chunk = f"chunk_{i//chunk_size:06d}".encode() + b'0' * (chunk_size - len(f"chunk_{i//chunk_size:06d}"))
            yield chunk[:min(chunk_size, total_size - i)]
        
        logger.info(f"Generated {size_gb} GB of test data in chunks")

    def upload_test_object(self, size_gb: int = None, object_key: str = None) -> bool:
        """Upload test object for benchmarking using streaming."""
        if size_gb is None:
            size_gb = OBJECT_SIZE_GB
        if object_key is None:
            object_key = f"test-object-{size_gb}gb"
        
        try:
            # Upload main test object using streaming
            logger.info(f"Uploading {object_key} ({size_gb} GB) using streaming")
            
            start_time = time.time()
            
            # Use streaming upload with the generator
            success = self.storage_system.upload_object_streaming(
                object_key, 
                self.generate_test_data(size_gb),
                size_gb * BYTES_PER_GB  # Total size in bytes
            )
            
            upload_time = time.time() - start_time
            
            if success:
                logger.info(f"Successfully uploaded {object_key} in {upload_time:.2f} seconds")
                logger.info(f"Upload speed: {size_gb / upload_time:.2f} GB/s")
                return True
            else:
                logger.error(f"Failed to upload {object_key}")
                return False
                
        except Exception as e:
            logger.error(f"Error during upload: {e}")
            return False
