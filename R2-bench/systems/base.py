"""
Async base classes for object storage systems with high-performance optimizations.
"""

import aioboto3
import botocore
from botocore.config import Config
from botocore.exceptions import ClientError
import logging
import time
from typing import Tuple, Optional
from urllib3.exceptions import IncompleteRead
from botocore.exceptions import ReadTimeoutError
from configuration import RANGE_SIZE_MB, MAX_CONCURRENCY

logger = logging.getLogger(__name__)


class ObjectStorageSystem:
    """Async base class for object storage systems with CRT and connection pooling."""

    def __init__(self, endpoint: str, bucket_name: str, credentials: dict):
        self.endpoint = endpoint
        self.bucket_name = bucket_name
        self.credentials = credentials
        self.session = None
        self.client = None
        self._setup_session()

    def _setup_session(self):
        """Set up the async boto3 session with CRT and optimized configuration."""
        try:
            # Create aioboto3 session
            self.session = aioboto3.Session(
                aws_access_key_id=self.credentials.get("access_key_id"),
                aws_secret_access_key=self.credentials.get("secret_access_key"),
                region_name=self.credentials.get("region_name", "auto"),
            )

            # Configure for maximum performance
            # CRT is required and enabled by default in aioboto3
            config = Config(
                # Aggressive connection pooling
                max_pool_connections=500,
                # Retry configuration
                retries={
                    "max_attempts": 3,
                    "mode": "adaptive",  # Adaptive retry mode
                },
                # S3-specific optimizations
                s3={
                    "use_accelerate_endpoint": False,
                    "payload_signing_enabled": False,  # Disable for better performance
                },
                # TCP settings (if supported)
                tcp_keepalive=True,
            )

            logger.info(
                f"Initialized async session for {self.endpoint} with max_pool_connections=500"
            )
            logger.info("CRT support: enabled (awscrt required)")

        except Exception as e:
            logger.error(f"Failed to initialize async session: {e}")
            raise

    async def __aenter__(self):
        """Async context manager entry."""
        config = Config(
            max_pool_connections=500,
            retries={"max_attempts": 3, "mode": "adaptive"},
            s3={"use_accelerate_endpoint": False, "payload_signing_enabled": False},
            tcp_keepalive=True,
        )
        self.client = await self.session.client(
            "s3",
            endpoint_url=self.endpoint,
            config=config,
        ).__aenter__()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self.client:
            await self.client.__aexit__(exc_type, exc_val, exc_tb)
            self.client = None

    async def download_range(
        self, key: str, start: int, length: int
    ) -> Tuple[Optional[bytes], float]:
        """Download a range of an object asynchronously and return (data, latency_ms).

        Args:
            key: Object key
            start: Start byte position
            length: Length in bytes

        Returns:
            Tuple of (data bytes or None, latency_ms)
        """
        if not self.client:
            raise RuntimeError("Storage client not initialized. Use async context manager.")

        try:
            start_time = time.time()
            range_header = f"bytes={start}-{start + length - 1}"

            response = await self.client.get_object(
                Bucket=self.bucket_name,
                Key=key,
                Range=range_header,
            )

            # Read body asynchronously
            body = response["Body"]
            data = await body.read()
            latency_ms = (time.time() - start_time) * 1000

            return data, latency_ms

        except IncompleteRead as e:
            logger.debug(f"IncompleteRead for {key} range {start}-{start + length - 1}: {e}")
            return None, 0
        except ReadTimeoutError as e:
            logger.debug(f"Read timeout for {key} range {start}-{start + length - 1}: {e}")
            return None, 0
        except ClientError as e:
            logger.error(
                f"Failed to download range {start}-{start + length - 1} from {key}: {e}"
            )
            return None, 0
        except Exception as e:
            logger.error(f"Unexpected error downloading range from {key}: {e}")
            return None, 0

    async def upload_object_streaming(
        self, key: str, data_generator, total_size: int, max_workers: int = 4
    ) -> bool:
        """Upload an object using async streaming concurrent multipart upload.

        Args:
            key: Object key
            data_generator: Generator yielding data chunks (can be sync or async)
            total_size: Total size of the object
            max_workers: Maximum number of concurrent workers

        Returns:
            True if successful, False otherwise
        """
        if not self.client:
            raise RuntimeError("Storage client not initialized. Use async context manager.")

        try:
            # Start multipart upload
            response = await self.client.create_multipart_upload(
                Bucket=self.bucket_name, Key=key
            )
            upload_id = response["UploadId"]

            import asyncio
            from io import BytesIO

            parts_queue = asyncio.Queue()
            parts_results = {}
            parts_lock = asyncio.Lock()
            part_number = 1
            chunk_size = RANGE_SIZE_MB * 1024 * 1024
            current_part = BytesIO()
            current_size = 0
            upload_errors = []
            error_lock = asyncio.Lock()

            async def upload_worker():
                """Async worker that processes parts from the queue."""
                while True:
                    try:
                        part_data = await asyncio.wait_for(parts_queue.get(), timeout=1.0)
                        if part_data is None:  # Shutdown signal
                            break

                        part_num, part_bytes = part_data
                        etag = await self._upload_single_part(
                            key, upload_id, part_num, part_bytes
                        )

                        async with parts_lock:
                            if etag:
                                parts_results[part_num] = {
                                    "ETag": etag,
                                    "PartNumber": part_num,
                                }
                            else:
                                async with error_lock:
                                    upload_errors.append(f"Failed to upload part {part_num}")

                        parts_queue.task_done()
                    except asyncio.TimeoutError:
                        break
                    except Exception as e:
                        async with error_lock:
                            upload_errors.append(f"Worker error: {e}")
                        parts_queue.task_done()

            # Start worker tasks
            workers = []
            for _ in range(max_workers):
                worker = asyncio.create_task(upload_worker())
                workers.append(worker)

            # Stream data and queue parts for upload
            # Handle both sync and async generators
            try:
                if hasattr(data_generator, '__aiter__'):
                    # Async generator
                    async for chunk in data_generator:
                        current_part.write(chunk)
                        current_size += len(chunk)

                        if current_size >= chunk_size:
                            current_part.seek(0)
                            await parts_queue.put((part_number, current_part.getvalue()))
                            part_number += 1
                            current_part = BytesIO()
                            current_size = 0
                else:
                    # Sync generator - run in executor
                    loop = asyncio.get_event_loop()
                    for chunk in data_generator:
                        current_part.write(chunk)
                        current_size += len(chunk)

                        if current_size >= chunk_size:
                            current_part.seek(0)
                            await parts_queue.put((part_number, current_part.getvalue()))
                            part_number += 1
                            current_part = BytesIO()
                            current_size = 0

                # Upload final part if there's remaining data
                if current_size > 0:
                    current_part.seek(0)
                    await parts_queue.put((part_number, current_part.getvalue()))

                # Wait for all parts to be processed
                await parts_queue.join()

            finally:
                # Shutdown workers
                for _ in range(max_workers):
                    await parts_queue.put(None)
                await asyncio.gather(*workers, return_exceptions=True)

            # Check for upload errors
            async with error_lock:
                if upload_errors:
                    raise Exception(f"Upload errors: {'; '.join(upload_errors)}")

            # Collect and sort parts
            parts = []
            async with parts_lock:
                parts = [
                    parts_results[part_num] for part_num in sorted(parts_results.keys())
                ]

            # Complete multipart upload
            await self.client.complete_multipart_upload(
                Bucket=self.bucket_name,
                Key=key,
                UploadId=upload_id,
                MultipartUpload={"Parts": parts},
            )

            logger.info(
                f"Successfully uploaded {key} with async streaming concurrent multipart upload"
            )
            return True

        except Exception as e:
            logger.error(
                f"Failed to upload {key} with async streaming concurrent multipart upload: {e}"
            )
            # Try to abort multipart upload if it exists
            try:
                if "upload_id" in locals():
                    await self.client.abort_multipart_upload(
                        Bucket=self.bucket_name, Key=key, UploadId=upload_id
                    )
            except:
                pass
            return False

    async def _upload_single_part(
        self, key: str, upload_id: str, part_number: int, part_data: bytes
    ) -> Optional[str]:
        """Upload a single part asynchronously and return its ETag."""
        try:
            response = await self.client.upload_part(
                Bucket=self.bucket_name,
                Key=key,
                PartNumber=part_number,
                UploadId=upload_id,
                Body=part_data,
            )
            return response["ETag"]
        except Exception as e:
            logger.error(f"Failed to upload part {part_number}: {e}")
            return None
