"""
Factory module for creating storage system instances.
"""

import logging
from typing import Dict, Any

# CRITICAL: Suppress boto3/botocore logging BEFORE importing any boto3-related modules
logging.getLogger('botocore').setLevel(logging.CRITICAL)
logging.getLogger('botocore.credentials').setLevel(logging.CRITICAL)
logging.getLogger('boto3').setLevel(logging.CRITICAL)
logging.getLogger('aioboto3').setLevel(logging.CRITICAL)
logging.getLogger('urllib3').setLevel(logging.CRITICAL)
logging.getLogger('s3transfer').setLevel(logging.CRITICAL)

from systems.r2 import R2System
from systems.aws import AWSSystem
from configuration import (
    R2_ACCESS_KEY_ID,
    R2_SECRET_ACCESS_KEY,
    AWS_ACCESS_KEY_ID,
    AWS_SECRET_ACCESS_KEY,
    AWS_REGION,
)

logger = logging.getLogger(__name__)


def create_storage_system(storage_type: str, verbose_init: bool = False, workers_per_core: int = None):
    """Create and return the appropriate storage system based on type.

    Args:
        storage_type: Storage type ('r2' or 's3')
        verbose_init: If True, log detailed initialization info (default False to reduce log duplication)
        workers_per_core: Number of workers per core (for connection pool sizing)

    Returns:
        Storage system instance (R2System or AWSSystem)

    Raises:
        ValueError: If storage_type is not supported
    """
    storage_type = storage_type.lower()

    if storage_type == "r2":
        credentials = {
            "access_key_id": R2_ACCESS_KEY_ID,
            "secret_access_key": R2_SECRET_ACCESS_KEY,
            "region_name": "auto",
        }
        return R2System(credentials, verbose_init=verbose_init, workers_per_core=workers_per_core)

    elif storage_type == "s3":
        credentials = {
            "access_key_id": AWS_ACCESS_KEY_ID,
            "secret_access_key": AWS_SECRET_ACCESS_KEY,
            "region_name": AWS_REGION,
        }
        return AWSSystem(credentials, verbose_init=verbose_init, workers_per_core=workers_per_core)

    else:
        raise ValueError(f"Unsupported storage type: {storage_type}. Must be 'r2' or 's3'.")
