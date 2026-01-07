"""
AWS S3 object storage system implementation.
"""

from systems.base import ObjectStorageSystem
from configuration import S3_ENDPOINT, BUCKET_NAME, AWS_REGION
from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)


class AWSSystem(ObjectStorageSystem):
    """AWS S3 object storage system."""

    def __init__(self, credentials: dict = None, instance_config: Dict[str, Any] = None, verbose_init: bool = False):
        if credentials is None:
            credentials = {}

        super().__init__(
            endpoint=S3_ENDPOINT,
            bucket_name=BUCKET_NAME,
            credentials=credentials,
            instance_config=instance_config,
            verbose_init=verbose_init
        )
        if verbose_init:
            logger.info("Initialized AWS S3 system")
