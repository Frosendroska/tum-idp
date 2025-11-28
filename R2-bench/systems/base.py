"""
Async base classes for object storage systems with high-performance optimizations.
"""

import aioboto3
import botocore
from botocore.config import Config
from botocore.exceptions import ClientError
import logging
import time
import asyncio
import os
from typing import Tuple, Optional, Dict, Any
from urllib3.exceptions import IncompleteRead
from botocore.exceptions import ReadTimeoutError
from configuration import RANGE_SIZE_MB, MAX_CONCURRENCY, REQUEST_TIMEOUT_SECONDS

# Import aiohttp exceptions for payload error handling
# aiohttp is a required dependency of aioboto3, so it's always available
from aiohttp.client_exceptions import ClientPayloadError

logger = logging.getLogger(__name__)

# Try to import psutil for connection monitoring (optional)
try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False
    logger.warning("psutil not available - connection monitoring will be limited")


class ObjectStorageSystem:
    """Async base class for object storage systems with CRT and connection pooling."""

    def __init__(self, endpoint: str, bucket_name: str, credentials: dict):
        self.endpoint = endpoint
        self.bucket_name = bucket_name
        self.credentials = credentials
        
        # Verify CRT is actually available
        self._has_crt = False
        try:
            import awscrt
            logger.info(f"✓ AWS CRT available: version {awscrt.__version__}")
            self._has_crt = True
        except ImportError:
            logger.warning(
                "⚠️ AWS CRT not installed - performance will be severely limited!\n"
                "Install with: pip install awscrt 'botocore[crt]'"
            )
        
        # Verify botocore CRT support (optional check)
        # Note: CRT support in botocore is automatically enabled if awscrt is installed
        if self._has_crt:
            try:
                # Try to verify CRT is actually being used
                # This is a best-effort check - CRT may still work even if this fails
                import botocore
                logger.info(f"✓ botocore version: {botocore.__version__}")
                logger.info("✓ CRT should be enabled (awscrt is installed)")
            except Exception:
                pass
        
        # Single source of truth for config
        self._config = self._create_config()
        
        # Setup session
        self.session = aioboto3.Session(
            aws_access_key_id=credentials.get("access_key_id"),
            aws_secret_access_key=credentials.get("secret_access_key"),
            region_name=credentials.get("region_name", "auto"),
        )
        
        self.client = None
        
        # Performance metrics
        self._metrics = {
            'total_downloads': 0,
            'successful_downloads': 0,
            'failed_downloads': 0,
            'total_bytes': 0,
            'total_latency_ms': 0,
        }
        self._metrics_lock = asyncio.Lock()
        
        # Connection monitoring
        self._download_count = 0
        self._last_conn_check = 0
        
        logger.info(
            f"Initialized async storage for {endpoint} "
            f"(max_pool_connections={self._config.max_pool_connections})"
        )
    
    def _create_config(self) -> Config:
        """Create optimized boto3 config with CRT support."""
        # Calculate required connections
        # With MAX_CONCURRENCY workers × 3 pipeline depth = potential concurrent requests
        optimal_pool_size = MAX_CONCURRENCY * 3 + 100
        actual_pool_size = min(optimal_pool_size, 2000)  # Cap at 2000
        
        if optimal_pool_size > 2000:
            logger.warning(
                f"Requested pool size ({optimal_pool_size}) exceeds maximum (2000). "
                f"Consider reducing MAX_CONCURRENCY from {MAX_CONCURRENCY} to ~600"
            )
        
        config = Config(
            # Scale connection pool to actual concurrency
            max_pool_connections=actual_pool_size,
            
            # Connection timeouts
            connect_timeout=5,
            read_timeout=60,  # Longer timeout for 100MB chunks
            
            # Adaptive retry strategy
            retries={
                'max_attempts': 3,
                'mode': 'adaptive',
            },
            
            # S3-specific optimizations
            s3={
                'use_accelerate_endpoint': False,
                'payload_signing_enabled': False,  # Skip signing overhead
                'addressing_style': 'virtual',  # or 'path' for R2
            },
            
            # TCP keep-alive
            tcp_keepalive=True,
        )
        
        logger.info(f"Configured connection pool: {config.max_pool_connections} connections")
        return config

    async def __aenter__(self):
        """Async context manager entry."""
        # Reuse the single config instance
        self.client = await self.session.client(
            "s3",
            endpoint_url=self.endpoint,
            config=self._config,  # Use existing config
        ).__aenter__()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self.client:
            await self.client.__aexit__(exc_type, exc_val, exc_tb)
            self.client = None
    
    def get_connection_count(self) -> int:
        """Get number of established connections for this process."""
        if not HAS_PSUTIL:
            return -1
        
        try:
            process = psutil.Process(os.getpid())
            connections = process.connections(kind='inet')
            established = [c for c in connections if c.status == 'ESTABLISHED']
            return len(established)
        except Exception as e:
            logger.debug(f"Failed to get connection count: {e}")
            return -1

    async def download_range(
        self, key: str, start: int, length: int
    ) -> Tuple[Optional[bytes], float, float]:
        """Download a range of an object asynchronously with request-level timeouts.
        
        Returns (data, latency_ms, rtt_ms). Data is None on failure.
        - latency_ms: Total time from request start to data fully received
        - rtt_ms: Round Trip Time (Time To First Byte) - time from request start to response received

        Args:
            key: Object key
            start: Start byte position
            length: Length in bytes

        Returns:
            Tuple of (data bytes or None, latency_ms, rtt_ms)
        """
        if not self.client:
            raise RuntimeError("Storage client not initialized. Use async context manager.")

        # Monitor connections every 100 downloads
        self._download_count += 1
        if self._download_count % 100 == 0:
            conn_count = self.get_connection_count()
            logger.info(
                f"Downloads: {self._download_count}, "
                f"Active connections: {conn_count}"
            )

        try:
            start_time = time.time()
            range_header = f"bytes={start}-{start + length - 1}"
            
            # Add timeout wrapper around entire request
            response = await asyncio.wait_for(
                self.client.get_object(
                    Bucket=self.bucket_name,
                    Key=key,
                    Range=range_header,
                ),
                timeout=REQUEST_TIMEOUT_SECONDS  # Configurable timeout for request
            )
            
            # Measure RTT (Time To First Byte) - time until response is received
            rtt_ms = (time.time() - start_time) * 1000
            
            # Read body with timeout
            body = response["Body"]
            data = await asyncio.wait_for(
                body.read(),
                timeout=REQUEST_TIMEOUT_SECONDS  # Configurable timeout for reading body
            )
            
            # Total latency includes both RTT and data transfer time
            latency_ms = (time.time() - start_time) * 1000
            
            # Validate we got expected amount of data
            if len(data) != length:
                logger.warning(
                    f"Incomplete read: expected {length} bytes, got {len(data)} bytes"
                )
            
            # Update metrics
            async with self._metrics_lock:
                self._metrics['total_downloads'] += 1
                self._metrics['successful_downloads'] += 1
                self._metrics['total_bytes'] += len(data)
                self._metrics['total_latency_ms'] += latency_ms
            
            return data, latency_ms, rtt_ms

        except asyncio.TimeoutError:
            logger.warning(
                f"Timeout downloading {key} range {start}-{start+length-1} "
                f"(download #{self._download_count})"
            )
            async with self._metrics_lock:
                self._metrics['total_downloads'] += 1
                self._metrics['failed_downloads'] += 1
            return None, 0, 0
        
        except IncompleteRead as e:
            logger.debug(f"IncompleteRead for {key} range {start}-{start + length - 1}: {e}")
            async with self._metrics_lock:
                self._metrics['total_downloads'] += 1
                self._metrics['failed_downloads'] += 1
            return None, 0, 0
        
        except ReadTimeoutError as e:
            logger.debug(f"Read timeout for {key} range {start}-{start + length - 1}: {e}")
            async with self._metrics_lock:
                self._metrics['total_downloads'] += 1
                self._metrics['failed_downloads'] += 1
            return None, 0, 0
        
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', 'Unknown')
            status_code = e.response.get('ResponseMetadata', {}).get('HTTPStatusCode', 0)
            
            # Highlight throttling errors
            if status_code in (429, 503):
                logger.error(
                    f"🚨 R2 THROTTLING DETECTED: {error_code} (HTTP {status_code}) "
                    f"for {key} range {start}-{start+length-1}"
                )
            else:
                logger.error(
                    f"S3 error {error_code} (HTTP {status_code}) for {key} "
                    f"range {start}-{start+length-1}"
                )
            async with self._metrics_lock:
                self._metrics['total_downloads'] += 1
                self._metrics['failed_downloads'] += 1
            return None, 0, 0
        
        except Exception as e:
            # Check if this is a ClientPayloadError (incomplete payload from aiohttp)
            # This happens when connection closes before all data is received
            error_type = type(e).__name__
            error_msg = str(e)
            
            if isinstance(e, ClientPayloadError):
                logger.warning(
                    f"Incomplete payload for {key} range {start}-{start+length-1}: "
                    f"Connection closed before all data received. This is retryable."
                )
            elif "ContentLengthError" in error_type or "Not enough data to satisfy content length" in error_msg:
                logger.warning(
                    f"Incomplete payload for {key} range {start}-{start+length-1}: "
                    f"Content length mismatch. This is retryable."
                )
            else:
                logger.error(
                    f"Unexpected error downloading {key} range {start}-{start+length-1}: {e}",
                    exc_info=True
                )
            
            async with self._metrics_lock:
                self._metrics['total_downloads'] += 1
                self._metrics['failed_downloads'] += 1
            return None, 0, 0
    
    async def verify_connection(self) -> bool:
        """Verify storage connection and configuration."""
        if not self.client:
            logger.error("Client not initialized. Use async context manager.")
            return False
        
        try:
            logger.info("Verifying storage connection...")
            
            # Test bucket access
            await self.client.head_bucket(Bucket=self.bucket_name)
            logger.info(f"✓ Successfully connected to bucket: {self.bucket_name}")
            
            # Log configuration
            logger.info(f"✓ Endpoint: {self.endpoint}")
            logger.info(f"✓ Max pool connections: {self._config.max_pool_connections}")
            logger.info(f"✓ CRT support: {'enabled' if self._has_crt else 'DISABLED (performance limited!)'}")
            
            # Check current connections
            conn_count = self.get_connection_count()
            if conn_count >= 0:
                logger.info(f"✓ Current established connections: {conn_count}")
            else:
                logger.info("✓ Connection monitoring: unavailable (psutil not installed)")
            
            return True
            
        except Exception as e:
            logger.error(f"✗ Connection verification failed: {e}")
            return False
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get performance metrics."""
        metrics = self._metrics.copy()
        if metrics['successful_downloads'] > 0:
            metrics['avg_latency_ms'] = (
                metrics['total_latency_ms'] / metrics['successful_downloads']
            )
            metrics['success_rate'] = (
                metrics['successful_downloads'] / metrics['total_downloads']
            )
        else:
            metrics['avg_latency_ms'] = 0
            metrics['success_rate'] = 0
        return metrics

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


def verify_setup() -> bool:
    """Verify CRT and configuration before benchmark.
    
    Returns:
        True if setup is correct, False otherwise
    """
    print("=" * 60)
    print("PERFORMANCE SETUP VERIFICATION")
    print("=" * 60)
    
    all_ok = True
    
    # 1. Check CRT
    try:
        import awscrt
        print(f"✓ AWS CRT installed: version {awscrt.__version__}")
    except ImportError:
        print("✗ AWS CRT NOT INSTALLED - CRITICAL PERFORMANCE ISSUE!")
        print("  Install with: pip install awscrt 'botocore[crt]'")
        all_ok = False
    
    # 2. Check botocore version
    try:
        import botocore
        print(f"✓ botocore version: {botocore.__version__}")
        # CRT support is automatically enabled if awscrt is installed
        if all_ok:  # Only show this if CRT is installed
            print("✓ botocore CRT support: should be enabled (awscrt is installed)")
    except ImportError:
        print("✗ botocore not installed")
        all_ok = False
    
    # 3. Check aioboto3
    try:
        import aioboto3
        print(f"✓ aioboto3 installed")
    except ImportError:
        print("✗ aioboto3 not installed")
        all_ok = False
    
    # 4. Check psutil for monitoring
    try:
        import psutil
        print(f"✓ psutil available for connection monitoring")
    except ImportError:
        print("⚠ psutil not available (optional, for monitoring)")
        print("  Install with: pip install psutil")
    
    # 5. Configuration check
    try:
        from configuration import MAX_CONCURRENCY
        optimal_pool = MAX_CONCURRENCY * 3 + 100
        actual_pool = min(optimal_pool, 2000)
        print(f"✓ MAX_CONCURRENCY: {MAX_CONCURRENCY}")
        print(f"✓ Optimal pool size: {actual_pool}")
        if optimal_pool > 2000:
            print(f"⚠ Pool size capped at 2000 (requested {optimal_pool})")
    except ImportError as e:
        print(f"⚠ Could not import configuration: {e}")
    
    print("=" * 60)
    
    if not all_ok:
        print("\n⚠️ Setup verification failed. Fix issues before benchmarking.")
    else:
        print("\n✓ Setup verification passed. Ready for benchmarking.")
    
    return all_ok
