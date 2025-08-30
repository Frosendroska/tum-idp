"""
AWS S3 object storage system implementation.
"""

from systems.base import ObjectStorageSystem
from configuration import S3_ENDPOINT, BUCKET_NAME, AWS_REGION
import logging

logger = logging.getLogger(__name__)


class AWSSystem(ObjectStorageSystem):
    """AWS S3 object storage system."""
    
    def __init__(self, credentials: dict = None):
        if credentials is None:
            credentials = {}
        
        super().__init__(
            endpoint=S3_ENDPOINT,
            bucket_name=BUCKET_NAME,
            credentials=credentials
        )
        logger.info("Initialized AWS S3 system")
