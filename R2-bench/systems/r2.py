"""
Cloudflare R2 object storage system implementation.
"""

from systems.base import ObjectStorageSystem
from configuration import R2_ENDPOINT, BUCKET_NAME
import logging

logger = logging.getLogger(__name__)


class R2System(ObjectStorageSystem):
    """Cloudflare R2 object storage system."""
    
    def __init__(self, credentials: dict = None):
        if credentials is None:
            credentials = {}
        
        super().__init__(
            endpoint=R2_ENDPOINT,
            bucket_name=BUCKET_NAME,
            credentials=credentials
        )
        logger.info("Initialized R2 system")
