"""
Async base classes for object storage systems with high-performance optimizations.
"""

import logging

# CRITICAL: Suppress boto3/botocore logging BEFORE importing aioboto3/botocore
logging.getLogger('botocore').setLevel(logging.CRITICAL)
logging.getLogger('botocore.credentials').setLevel(logging.CRITICAL)
logging.getLogger('boto3').setLevel(logging.CRITICAL)
logging.getLogger('aioboto3').setLevel(logging.CRITICAL)
logging.getLogger('urllib3').setLevel(logging.CRITICAL)
logging.getLogger('s3transfer').setLevel(logging.CRITICAL)

import aioboto3
import botocore
from botocore.config import Config
from botocore.exceptions import ClientError
import time
import asyncio
import os
from typing import Tuple, Optional, Dict, Any, AsyncGenerator
from urllib3.exceptions import IncompleteRead
from botocore.exceptions import ReadTimeoutError
from configuration import RANGE_SIZE_MB, REQUEST_TIMEOUT_SECONDS

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

    def __init__(
        self,
        endpoint: str,
        bucket_name: str,
        credentials: dict,
        verbose_init: bool = False,
        workers_per_core: int = None
    ):
        self.endpoint = endpoint
        self.bucket_name = bucket_name
        self.credentials = credentials
        self.workers_per_core = workers_per_core  # Store for config calculation

        # Verify CRT is actually available (only log if verbose_init=True to reduce duplication)
        self._has_crt = False
        try:
            import awscrt
            if verbose_init:
                logger.info(f"✓ AWS CRT available: version {awscrt.__version__}")
            self._has_crt = True
        except ImportError:
            if verbose_init:
                logger.warning(
                    "⚠️ AWS CRT not installed - performance will be severely limited!\n"
                    "Install with: pip install awscrt 'botocore[crt]'"
                )

        # Note about CRT and aiobotocore
        # IMPORTANT: aiobotocore uses aiohttp, NOT AWS CRT, even if awscrt is installed
        # CRT is only used by synchronous boto3, not by aiobotocore's async client
        if self._has_crt and verbose_init:
            try:
                import botocore
                logger.info(f"✓ botocore version: {botocore.__version__}")
                logger.info(f"✓ awscrt is installed (version {awscrt.__version__})")
                logger.warning(
                    "⚠️  NOTE: aiobotocore uses aiohttp (not CRT) for HTTP transport.\n"
                    "    Performance depends on aiohttp.TCPConnector limits, which we configure below."
                )
            except Exception:
                pass

        # Single source of truth for config (includes aiohttp connector config)
        self._config = self._create_config(verbose=verbose_init)

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
            'incomplete_payload_errors': 0,  # Track incomplete payloads specifically
            'timeout_errors': 0,
            'throttle_errors': 0,
        }
        self._metrics_lock = asyncio.Lock()

        # Connection monitoring
        self._download_count = 0
        self._last_conn_check = 0

        if verbose_init:
            logger.info(
                f"Initialized async storage for {endpoint} "
                f"(max_pool_connections={self._config.max_pool_connections})"
            )
    
    def _create_config(self, verbose: bool = False):
        """Create optimized config for multiprocessing + async architecture."""
        from configuration import INITIAL_WORKERS_PER_CORE, MAX_WORKERS_PER_CORE, PIPELINE_DEPTH, CONNECTION_POOL_SAFETY_FACTOR
        from botocore.config import Config

        # Calculate connection pool size based on ACTUAL workers_per_core if provided
        # Otherwise use MAX_WORKERS_PER_CORE for safety (handles ramp-up)
        # In multiprocessing architecture, each process has its own connection pool
        workers_per_core = self.workers_per_core if self.workers_per_core else MAX_WORKERS_PER_CORE

        # IMPORTANT: This is PER PROCESS concurrency, not system-wide
        max_concurrency = workers_per_core * PIPELINE_DEPTH
        total_pool_size = min(
            int(max_concurrency * CONNECTION_POOL_SAFETY_FACTOR),
            3000  # Hard cap (increased from 2000)
        )

        # Store max_concurrency for connector creation in __aenter__
        self._max_concurrency = max_concurrency

        if verbose:
            logger.info(
                f"boto3 config (per process): max_pool_connections={total_pool_size} "
                f"(workers_per_core={workers_per_core}, max_concurrency={max_concurrency}, safety_factor={CONNECTION_POOL_SAFETY_FACTOR})"
            )
            logger.info(
                f"✓ aiohttp connector will be configured: limit={max_concurrency + 200} "
                f"(workers_per_core={workers_per_core} × pipeline={PIPELINE_DEPTH} + buffer)"
            )

        config = Config(
            # Scale connection pool to actual concurrency
            max_pool_connections=total_pool_size,

            # Connection timeouts
            connect_timeout=30,  # Increased from 5s - at high concurrency, establishing connections takes time
            read_timeout=120,  # Longer timeout for 100MB chunks

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

        return config

    async def __aenter__(self) -> 'ObjectStorageSystem':
        """Async context manager entry.

        Returns:
            Self for use in 'async with' statements
        """
        import aiohttp
        from functools import wraps
        from configuration import DISABLE_SSL_VERIFICATION

        # CRITICAL FIX: Monkey-patch aiohttp.TCPConnector to use high connection limits
        # aiobotocore creates its own connector internally with default limit=100
        # We need to intercept connector creation and inject our custom limits
        connector_limit = self._max_concurrency + 200  # Increased buffer for safety

        # Store original TCPConnector __init__
        original_tcp_connector_init = aiohttp.TCPConnector.__init__

        @wraps(original_tcp_connector_init)
        def patched_tcp_connector_init(self_connector, *args, **kwargs):
            # Override limit and limit_per_host if not explicitly set
            if 'limit' not in kwargs:
                kwargs['limit'] = connector_limit
            if 'limit_per_host' not in kwargs:
                kwargs['limit_per_host'] = 0  # Unlimited per host
            # CRITICAL: Disable SSL verification for maximum throughput
            # At 50 Gbps, SSL/TLS encryption overhead is the primary bottleneck
            # This is safe for capacity discovery testing (not for production)
            if 'ssl' not in kwargs and DISABLE_SSL_VERIFICATION:
                kwargs['ssl'] = False
            # Call original __init__ with modified kwargs
            return original_tcp_connector_init(self_connector, *args, **kwargs)

        # Apply monkey patch
        aiohttp.TCPConnector.__init__ = patched_tcp_connector_init

        ssl_status = "SSL disabled" if DISABLE_SSL_VERIFICATION else "SSL enabled"
        logger.info(
            f"✓ aiohttp.TCPConnector patched: limit={connector_limit} connections, {ssl_status}"
        )

        # Create client - it will now use our patched connector
        self.client = await self.session.client(
            "s3",
            endpoint_url=self.endpoint,
            config=self._config,
        ).__aenter__()

        # Restore original TCPConnector __init__ (clean up monkey patch)
        aiohttp.TCPConnector.__init__ = original_tcp_connector_init

        ssl_info = " (SSL disabled for max throughput)" if DISABLE_SSL_VERIFICATION else " (SSL enabled)"
        logger.info(f"✓ Client created with high-performance connector{ssl_info}")

        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit.

        Ensures proper cleanup of the S3 client connection.
        aiobotocore will automatically clean up the aiohttp connector.
        """
        if self.client:
            try:
                await self.client.__aexit__(exc_type, exc_val, exc_tb)
            except Exception as e:
                logger.warning(f"Error closing S3 client: {e}")
            finally:
                self.client = None

        logger.debug("Storage system cleanup complete")
    
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

        response = None
        body = None

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
            async with self._metrics_lock:
                self._metrics['total_downloads'] += 1
                self._metrics['failed_downloads'] += 1
                self._metrics['timeout_errors'] += 1
                timeout_count = self._metrics['timeout_errors']

            logger.warning(
                f"[TIMEOUT #{timeout_count}] Request timeout for {key} range {start}-{start+length-1} "
                f"after {REQUEST_TIMEOUT_SECONDS}s (likely R2 overload)"
            )
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

            async with self._metrics_lock:
                self._metrics['total_downloads'] += 1
                self._metrics['failed_downloads'] += 1

                # Track throttling specifically
                if status_code in (429, 503):
                    self._metrics['throttle_errors'] += 1
                    throttle_count = self._metrics['throttle_errors']

                    logger.error(
                        f"🚨 [THROTTLE #{throttle_count}] R2 THROTTLING: {error_code} (HTTP {status_code}) "
                        f"for {key} range {start}-{start+length-1} - REDUCE CONCURRENCY!"
                    )
                else:
                    logger.error(
                        f"S3 error {error_code} (HTTP {status_code}) for {key} "
                        f"range {start}-{start+length-1}"
                    )
            return None, 0, 0
        
        except Exception as e:
            # Check if this is a ClientPayloadError (incomplete payload from aiohttp)
            # This happens when connection closes before all data is received
            error_type = type(e).__name__
            error_msg = str(e)

            if isinstance(e, ClientPayloadError):
                # Log ALL incomplete payloads to track R2 throttling
                async with self._metrics_lock:
                    self._metrics['incomplete_payload_errors'] += 1
                    incomplete_count = self._metrics['incomplete_payload_errors']

                logger.warning(
                    f"[#{incomplete_count}] Incomplete payload for {key} range {start}-{start+length-1}: "
                    f"Connection closed mid-transfer (network issue or throttling). Will retry."
                )
            elif "ContentLengthError" in error_type or "Not enough data to satisfy content length" in error_msg:
                # Log ALL content length errors
                async with self._metrics_lock:
                    self._metrics['incomplete_payload_errors'] += 1
                    incomplete_count = self._metrics['incomplete_payload_errors']

                logger.warning(
                    f"[#{incomplete_count}] Incomplete payload for {key} range {start}-{start+length-1}: "
                    f"Content length mismatch. Will retry."
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

        finally:
            # Always close the body stream to prevent connection leaks
            if body is not None:
                try:
                    await body.close()
                except Exception as e:
                    logger.debug(f"Error closing response body: {e}")

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
        """Get performance metrics with error breakdown."""
        metrics = self._metrics.copy()

        if metrics['successful_downloads'] > 0:
            metrics['avg_latency_ms'] = (
                metrics['total_latency_ms'] / metrics['successful_downloads']
            )
        else:
            metrics['avg_latency_ms'] = 0

        if metrics['total_downloads'] > 0:
            metrics['success_rate'] = (
                metrics['successful_downloads'] / metrics['total_downloads']
            )
            metrics['incomplete_payload_rate'] = (
                metrics['incomplete_payload_errors'] / metrics['total_downloads']
            )
            metrics['timeout_rate'] = (
                metrics['timeout_errors'] / metrics['total_downloads']
            )
            metrics['throttle_rate'] = (
                metrics['throttle_errors'] / metrics['total_downloads']
            )
        else:
            metrics['success_rate'] = 0
            metrics['incomplete_payload_rate'] = 0
            metrics['timeout_rate'] = 0
            metrics['throttle_rate'] = 0

        return metrics

    async def upload_object_streaming(
        self, key: str, data_generator: AsyncGenerator[bytes, None], total_size: int, max_workers: int = 4
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
            except Exception:
                # Silently ignore cleanup errors
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
