"""
Phase 0: Upload test objects to object storage.
"""

import asyncio
import os
import sys
import logging
import argparse
import time

# Required: Use uvloop for better performance
import uvloop
asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())

# Ensure project root is in path (for running as script)
# When run as module (python -m cli.uploader), this is not needed
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from configuration import (
    OBJECT_SIZE_GB,
    RANGE_SIZE_MB,
    BYTES_PER_GB,
    BYTES_PER_MB,
)
from common.storage_factory import create_storage_system

# Set up logging (only if not already configured)
if not logging.root.handlers:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
    )
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
            self.storage_system = create_storage_system(self.storage_type)
        except Exception as e:
            logger.error(
                f"Failed to initialize {self.storage_type.upper()} storage: {e}"
            )
            raise

    def generate_test_data(self, size_gb: int):
        """Generate test data of specified size as a generator to avoid memory issues."""
        logger.info(f"Generating {size_gb} GB of test data in chunks")

        # Generate data in chunks to manage memory
        chunk_size = RANGE_SIZE_MB * BYTES_PER_MB  # Use configured chunk size
        total_size = size_gb * BYTES_PER_GB

        for i in range(0, total_size, chunk_size):
            chunk = f"chunk_{i//chunk_size:06d}".encode() + b"0" * (
                chunk_size - len(f"chunk_{i//chunk_size:06d}")
            )
            yield chunk[: min(chunk_size, total_size - i)]

        logger.info(f"Generated {size_gb} GB of test data in chunks")

    async def upload_test_object(self, size_gb: int = None, object_key: str = None) -> bool:
        """Upload test object for benchmarking using streaming."""
        if size_gb is None:
            size_gb = OBJECT_SIZE_GB
        if object_key is None:
            object_key = f"test-object-{size_gb}gb"

        # Use storage system as async context manager
        async with self.storage_system:
            try:
                # Upload main test object using streaming
                logger.info(f"Uploading {object_key} ({size_gb} GB) using streaming")

                start_time = time.time()

                # Use streaming upload with the generator
                success = await self.storage_system.upload_object_streaming(
                    object_key,
                    self.generate_test_data(size_gb),
                    size_gb * BYTES_PER_GB,  # Total size in bytes
                )

                upload_time = time.time() - start_time

                if success:
                    logger.info(
                        f"Successfully uploaded {object_key} in {upload_time:.2f} seconds"
                    )
                    logger.info(f"Upload speed: {size_gb / upload_time:.2f} GB/s")
                    return True
                else:
                    logger.error(f"Failed to upload {object_key}")
                    return False

            except Exception as e:
                logger.error(f"Error during upload: {e}")
                return False


async def main_async():
    """Main async entry point."""
    parser = argparse.ArgumentParser(description="Upload test objects")
    parser.add_argument(
        "--storage", choices=["r2", "s3"], default="r2", help="Storage type"
    )
    parser.add_argument("--size-gb", type=int, help="Size in GB")
    parser.add_argument("--object-key", help="Object key")

    args = parser.parse_args()

    uploader = Uploader(args.storage)
    success = await uploader.upload_test_object(
        size_gb=args.size_gb, object_key=args.object_key
    )

    if success:
        logger.info("Upload completed successfully")
    else:
        logger.error("Upload failed")
        sys.exit(1)


def main():
    """Main entry point."""
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
