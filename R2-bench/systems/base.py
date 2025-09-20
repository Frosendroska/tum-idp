"""
Base classes for object storage systems.
"""

import boto3
import botocore
from botocore.exceptions import ClientError
from io import BytesIO
import logging
from configuration import RANGE_SIZE_MB, MAX_CONCURRENCY

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
                aws_access_key_id=self.credentials.get("aws_access_key_id"),
                aws_secret_access_key=self.credentials.get("aws_secret_access_key"),
                region_name=self.credentials.get("region_name", "auto"),
            )

            self.client = session.client(
                "s3",
                endpoint_url=self.endpoint,
                config=botocore.config.Config(
                    retries={"max_attempts": 3}, 
                    # Increase connection pool for concurrent operations
                    max_pool_connections=MAX_CONCURRENCY,
                    # Add connection timeout settings - increased for large downloads
                    connect_timeout=30,
                    read_timeout=300  # 5 minutes to handle 100MB downloads at 10 Mbps
                ),
            )
            logger.info(f"Initialized client for {self.endpoint}")
        except Exception as e:
            logger.error(f"Failed to initialize client: {e}")
            raise

    def upload_object_streaming(
        self, key: str, data_generator, total_size: int, max_workers: int = 4
    ) -> bool:
        """Upload an object using streaming concurrent multipart upload.
        
        Args:
            key: Object key
            data_generator: Generator yielding data chunks
            total_size: Total size of the object
            max_workers: Maximum number of concurrent workers
        """
        try:
            return self._multipart_upload_streaming_concurrent(key, data_generator, total_size, max_workers)
        except Exception as e:
            logger.error(f"Failed to upload {key} with streaming: {e}")
            return False

    def _multipart_upload_streaming_concurrent(
        self, key: str, data_generator, total_size: int, max_workers: int = 4
    ) -> bool:
        """Upload large object using multipart upload with streaming concurrent part uploads."""
        try:
            # Start multipart upload
            response = self.client.create_multipart_upload(
                Bucket=self.bucket_name, Key=key
            )
            upload_id = response["UploadId"]

            # Use a queue to manage concurrent uploads while streaming
            from queue import Queue
            import threading
            
            parts_queue = Queue()
            parts_results = {}
            parts_lock = threading.Lock()
            part_number = 1
            chunk_size = RANGE_SIZE_MB * 1024 * 1024
            current_part = BytesIO()
            current_size = 0
            upload_errors = []
            error_lock = threading.Lock()

            def upload_worker():
                """Worker thread that processes parts from the queue."""
                while True:
                    try:
                        part_data = parts_queue.get(timeout=1)
                        if part_data is None:  # Shutdown signal
                            break
                        
                        part_num, part_bytes = part_data
                        etag = self._upload_single_part(key, upload_id, part_num, part_bytes)
                        
                        with parts_lock:
                            if etag:
                                parts_results[part_num] = {"ETag": etag, "PartNumber": part_num}
                            else:
                                with error_lock:
                                    upload_errors.append(f"Failed to upload part {part_num}")
                        
                        parts_queue.task_done()
                    except Exception as e:
                        with error_lock:
                            upload_errors.append(f"Worker error: {e}")
                        parts_queue.task_done()

            # Start worker threads
            workers = []
            for _ in range(max_workers):
                worker = threading.Thread(target=upload_worker)
                worker.daemon = True
                worker.start()
                workers.append(worker)

            # Stream data and queue parts for upload
            try:
                for chunk in data_generator:
                    current_part.write(chunk)
                    current_size += len(chunk)

                    if current_size >= chunk_size:
                        current_part.seek(0)
                        parts_queue.put((part_number, current_part.getvalue()))
                        part_number += 1
                        current_part = BytesIO()
                        current_size = 0

                # Upload final part if there's remaining data
                if current_size > 0:
                    current_part.seek(0)
                    parts_queue.put((part_number, current_part.getvalue()))

                # Wait for all parts to be processed
                parts_queue.join()

            finally:
                # Shutdown workers
                for _ in range(max_workers):
                    parts_queue.put(None)
                for worker in workers:
                    worker.join(timeout=5)

            # Check for upload errors
            with error_lock:
                if upload_errors:
                    raise Exception(f"Upload errors: {'; '.join(upload_errors)}")

            # Collect and sort parts
            parts = []
            with parts_lock:
                parts = [parts_results[part_num] for part_num in sorted(parts_results.keys())]

            # Complete multipart upload
            self.client.complete_multipart_upload(
                Bucket=self.bucket_name,
                Key=key,
                UploadId=upload_id,
                MultipartUpload={"Parts": parts},
            )

            logger.info(f"Successfully uploaded {key} with streaming concurrent multipart upload")
            return True

        except Exception as e:
            logger.error(f"Failed to upload {key} with streaming concurrent multipart upload: {e}")
            # Try to abort multipart upload if it exists
            try:
                if "upload_id" in locals():
                    self.client.abort_multipart_upload(
                        Bucket=self.bucket_name, Key=key, UploadId=upload_id
                    )
            except:
                pass
            return False

    def _upload_single_part(self, key: str, upload_id: str, part_number: int, part_data: bytes) -> str:
        """Upload a single part and return its ETag."""
        try:
            response = self.client.upload_part(
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

    def download_range(self, key: str, start: int, length: int) -> tuple:
        """Download a range of an object and return (data, latency_ms)."""
        import time
        from botocore.exceptions import ReadTimeoutError, IncompleteReadError

        try:
            start_time = time.time()
            response = self.client.get_object(
                Bucket=self.bucket_name,
                Key=key,
                Range=f"bytes={start}-{start + length - 1}",
            )
            data = response["Body"].read()
            latency_ms = (time.time() - start_time) * 1000

            return data, latency_ms
        except ReadTimeoutError as e:
            logger.warning(f"Read timeout downloading range {start}-{start + length - 1} from {key}: {e}")
            return None, 0
        except IncompleteReadError as e:
            logger.warning(f"Incomplete read downloading range {start}-{start + length - 1} from {key}: {e}")
            return None, 0
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', 'Unknown')
            logger.warning(f"Client error downloading range {start}-{start + length - 1} from {key} ({error_code}): {e}")
            return None, 0
        except Exception as e:
            logger.warning(f"Unexpected error downloading range {start}-{start + length - 1} from {key}: {e}")
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
