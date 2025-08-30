"""
Phase 0: Upload test objects to object storage.
"""

import os
import sys
import logging
import argparse
import time

# Add the current directory to Python path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from configuration import OBJECT_SIZE_GB, BUCKET_NAME, R2_ENDPOINT, S3_ENDPOINT
from systems.r2 import R2System
from systems.aws import AWSSystem

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class SimpleUploader:
    """Simple uploader for test objects."""
    
    def __init__(self, storage_type: str = "r2"):
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
                    'aws_access_key_id': os.getenv('AWS_ACCESS_KEY_ID'),
                    'aws_secret_access_key': os.getenv('AWS_SECRET_ACCESS_KEY'),
                    'region_name': 'auto'
                }
                self.storage_system = R2System(credentials)
                
            elif self.storage_type == "s3":
                credentials = {
                    'aws_access_key_id': os.getenv('AWS_ACCESS_KEY_ID'),
                    'aws_secret_access_key': os.getenv('AWS_SECRET_ACCESS_KEY'),
                    'region_name': os.getenv('AWS_REGION', 'eu-central-1')
                }
                self.storage_system = AWSSystem(credentials)
                
            else:
                raise ValueError(f"Unsupported storage type: {self.storage_type}")
                
        except Exception as e:
            logger.error(f"Failed to initialize {self.storage_type.upper()} storage: {e}")
            raise
    
    def generate_test_data(self, size_gb: int) -> bytes:
        """Generate test data of specified size."""
        logger.info(f"Generating {size_gb} GB of test data")
        
        # Generate data in chunks to manage memory
        chunk_size = 100 * 1024 * 1024  # 100MB chunks
        total_size = size_gb * 1024 * 1024 * 1024
        
        test_data = b''
        for i in range(0, total_size, chunk_size):
            chunk = f"chunk_{i//chunk_size:06d}".encode() + b'0' * (chunk_size - len(f"chunk_{i//chunk_size:06d}"))
            test_data += chunk[:min(chunk_size, total_size - i)]
        
        logger.info(f"Generated {len(test_data) / (1024**3):.2f} GB of test data")
        return test_data
    
    def upload_test_object(self, size_gb: int = None) -> bool:
        """Upload test object for benchmarking."""
        if size_gb is None:
            size_gb = OBJECT_SIZE_GB
        
        try:
            # Generate test data
            test_data = self.generate_test_data(size_gb)
            
            # Upload main test object
            object_key = f"test-object-{size_gb}gb"
            logger.info(f"Uploading {object_key} ({len(test_data) / (1024**3):.2f} GB)")
            
            start_time = time.time()
            success = self.storage_system.upload_object(object_key, test_data)
            upload_time = time.time() - start_time
            
            if success:
                logger.info(f"Successfully uploaded {object_key} in {upload_time:.2f} seconds")
                logger.info(f"Upload speed: {len(test_data) / (1024**3) / upload_time:.2f} GB/s")
                return True
            else:
                logger.error(f"Failed to upload {object_key}")
                return False
                
        except Exception as e:
            logger.error(f"Error during upload: {e}")
            return False


def main():
    """Main function."""
    parser = argparse.ArgumentParser(description='Upload test objects for R2 benchmark')
    parser.add_argument('--storage', choices=['r2', 's3'], default='r2',
                        help='Storage type to use (default: r2)')
    parser.add_argument('--size', type=int, default=OBJECT_SIZE_GB,
                        help=f'Object size in GB (default: {OBJECT_SIZE_GB})')
    
    args = parser.parse_args()
    
    try:
        uploader = SimpleUploader(args.storage)
        
        # Upload test object
        success = uploader.upload_test_object(args.size)
        
        if success:
            logger.info("Upload completed successfully")
            return 0
        else:
            logger.error("Upload failed")
            return 1
            
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        return 1


if __name__ == '__main__':
    exit(main())
