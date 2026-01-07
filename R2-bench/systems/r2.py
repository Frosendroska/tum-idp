"""
Cloudflare R2 object storage system implementation.
"""

from systems.base import ObjectStorageSystem
from configuration import R2_ENDPOINT, BUCKET_NAME
from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)


class R2System(ObjectStorageSystem):
    """Cloudflare R2 object storage system."""

    def __init__(self, credentials: dict = None, instance_config: Dict[str, Any] = None, verbose_init: bool = False):
        if credentials is None:
            credentials = {}

        super().__init__(
            endpoint=R2_ENDPOINT,
            bucket_name=BUCKET_NAME,
            credentials=credentials,
            instance_config=instance_config,
            verbose_init=verbose_init
        )
        if verbose_init:
            logger.info("Initialized R2 system")
