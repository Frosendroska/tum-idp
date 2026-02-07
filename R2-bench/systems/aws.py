"""
AWS S3 object storage system implementation.
"""

from systems.base import ObjectStorageSystem
from configuration import S3_ENDPOINT, BUCKET_NAME
import logging

logger = logging.getLogger(__name__)


class AWSSystem(ObjectStorageSystem):
    """AWS S3 object storage system."""

    def __init__(self, credentials: dict = None, verbose_init: bool = False, workers_per_core: int = None):
        if credentials is None:
            credentials = {}

        super().__init__(
            endpoint=S3_ENDPOINT,
            bucket_name=BUCKET_NAME,
            credentials=credentials,
            verbose_init=verbose_init,
            workers_per_core=workers_per_core
        )
        if verbose_init:
            logger.info("Initialized AWS S3 system")
