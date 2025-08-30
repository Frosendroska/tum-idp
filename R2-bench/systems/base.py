"""
Base classes for object storage systems.
"""

import boto3
import botocore
from botocore.exceptions import ClientError
import logging

logger = logging.getLogger(__name__)


class ObjectStorageSystem:
    """Base class for object storage systems."""
    
    def __init__(self, endpoint: str, bucket_name: str, credentials: dict):
        self.endpoint = endpoint
        self.bucket_name = bucket_name
        self.credentials = credentials
        self.client = None
        self._setup_client()
    
    def _setup_client(self):
        """Set up the storage client."""
        try:
            session = boto3.Session(
                aws_access_key_id=self.credentials.get('aws_access_key_id'),
                aws_secret_access_key=self.credentials.get('aws_secret_access_key'),
                region_name=self.credentials.get('region_name', 'auto')
            )
            
            self.client = session.client(
                's3',
                endpoint_url=self.endpoint,
                config=botocore.config.Config(
                    retries={'max_attempts': 3},
                    max_pool_connections=100
                )
            )
            logger.info(f"Initialized client for {self.endpoint}")
        except Exception as e:
            logger.error(f"Failed to initialize client: {e}")
            raise
    
    def upload_object(self, key: str, data: bytes) -> bool:
        """Upload an object to storage."""
        try:
            self.client.put_object(
                Bucket=self.bucket_name,
                Key=key,
                Body=data
            )
            logger.info(f"Successfully uploaded {key}")
            return True
        except ClientError as e:
            logger.error(f"Failed to upload {key}: {e}")
            return False
    
    def download_range(self, key: str, start: int, length: int) -> tuple:
        """Download a range of an object and return (data, latency_ms)."""
        import time
        
        try:
            start_time = time.time()
            response = self.client.get_object(
                Bucket=self.bucket_name,
                Key=key,
                Range=f'bytes={start}-{start + length - 1}'
            )
            data = response['Body'].read()
            latency_ms = (time.time() - start_time) * 1000
            
            return data, latency_ms
        except ClientError as e:
            logger.error(f"Failed to download range {start}-{start + length - 1} from {key}: {e}")
            return None, 0
    
    def object_exists(self, key: str) -> bool:
        """Check if an object exists."""
        try:
            self.client.head_object(Bucket=self.bucket_name, Key=key)
            return True
        except ClientError:
            return False
    
    def delete_object(self, key: str) -> bool:
        """Delete an object."""
        try:
            self.client.delete_object(Bucket=self.bucket_name, Key=key)
            logger.info(f"Successfully deleted {key}")
            return True
        except ClientError as e:
            logger.error(f"Failed to delete {key}: {e}")
            return False
