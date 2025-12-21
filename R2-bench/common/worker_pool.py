"""
High-performance async worker pool for S3/R2 benchmarking with request pipelining.
"""

import asyncio
import time
import logging
import random
import pandas as pd
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, Any, List, Optional
from persistence.record import BenchmarkRecord
from persistence.parquet import ParquetPersistence
from configuration import (
    RANGE_SIZE_MB,
    BYTES_PER_MB,
    BYTES_PER_GB,
    MAX_RETRIES,
    MAX_CONSECUTIVE_ERRORS,
    PROGRESS_INTERVAL,
    OBJECT_SIZE_GB,
    BITS_PER_BYTE,
    GIGABITS_PER_GB,
    DEFAULT_MAX_WORKERS,
    DEFAULT_PERSISTENCE_BATCH_SIZE,
    PERSISTENCE_FLUSH_INTERVAL_SECONDS,
)
from common.metrics_utils import (
    calculate_phase_throughput_with_prorating,
    calculate_latency_stats
)

logger = logging.getLogger(__name__)


class WorkerPool:
    """High-performance async worker pool with request pipelining and async persistence."""

    def __init__(
        self,
        storage_system,
        persistence: ParquetPersistence,
        max_workers: int = None,
        pipeline_depth: int = 3,
        persistence_batch_size: int = None,
    ):
        """Initialize the async worker pool.

        Args:
            storage_system: Async storage system to use for downloads
            persistence: Persistence object to store benchmark records
            max_workers: Maximum number of concurrent workers (default: from configuration)
            pipeline_depth: Number of in-flight requests per worker (pipelining)
            persistence_batch_size: Number of records to batch before writing (default: from configuration)
        """
        self.storage_system = storage_system
        self.persistence = persistence
        self.max_workers = max_workers or DEFAULT_MAX_WORKERS
        self.pipeline_depth = pipeline_depth
        self.persistence_batch_size = persistence_batch_size or DEFAULT_PERSISTENCE_BATCH_SIZE

        # Worker management
        self.worker_tasks: List[asyncio.Task] = []
        self.stop_event = asyncio.Event()
        self.active_workers = 0
        self.is_running = False

        # Phase management
        self.current_phase_id: str = ""

        # Worker state (thread-safe with asyncio)
        self.worker_states: Dict[int, Dict[str, Any]] = {}

        # Async persistence queue
        self.persistence_queue: asyncio.Queue = asyncio.Queue(maxsize=10000)
        self.persistence_task: Optional[asyncio.Task] = None

        # Dedicated executor for persistence I/O (scaled with workers to prevent bottleneck)
        self._persistence_executor = ThreadPoolExecutor(
            max_workers=max(20, self.max_workers // 2),  # Scale with workers, min 20
            thread_name_prefix="persistence"
        )
        
        # Executor monitoring
        self._executor_queue_warnings = 0
        
        # Pre-computed range cache for better performance (eliminates random.randint overhead)
        self._range_cache_size = max(
            10000,  # Minimum 10k ranges
            (OBJECT_SIZE_GB * BYTES_PER_GB // (RANGE_SIZE_MB * BYTES_PER_MB)) * 100  # 100x original
        )
        self._range_cache = self._precompute_ranges()
        self._range_index = 0

        logger.info(
            f"Initialized WorkerPool with max {self.max_workers} workers, "
            f"pipeline_depth={pipeline_depth}, batch_size={persistence_batch_size}, "
            f"persistence_threads={self._persistence_executor._max_workers}, "
            f"range_cache_size={self._range_cache_size}"
        )

    def _precompute_ranges(self) -> List[int]:
        """Pre-compute random range starts to avoid random.randint overhead during requests."""
        range_length = RANGE_SIZE_MB * BYTES_PER_MB
        max_start = (OBJECT_SIZE_GB * BYTES_PER_GB) - range_length
        
        # Generate pre-computed random ranges
        ranges = [random.randint(0, max_start) for _ in range(self._range_cache_size)]
        logger.info(f"Pre-computed {len(ranges)} range starts (0 to {max_start})")
        return ranges

    def _get_next_range_start(self) -> int:
        """Get next pre-computed range start (thread-safe with asyncio)."""
        range_start = self._range_cache[self._range_index]
        self._range_index = (self._range_index + 1) % self._range_cache_size
        return range_start

    async def start_workers(
        self, concurrency: int, object_key: str, phase_id: str
    ):
        """Start workers for a specific concurrency level and optionally begin a phase.

        Args:
            concurrency: Number of concurrent workers to start
            object_key: Object key to download
            phase_id: Phase identifier
        """
        self.current_phase_id = phase_id
        logger.info(f"Began phase: {phase_id}")

        if self.is_running:
            logger.info(
                f"Adjusting worker pool from {self.active_workers} to {concurrency} workers"
            )
            await self._adjust_worker_count(concurrency, object_key)
        else:
            logger.info(f"Starting worker pool with {concurrency} workers")
            await self._start_initial_workers(concurrency, object_key)

        logger.info(f"Worker pool ready: {self.active_workers} workers")

    async def _start_initial_workers(self, concurrency: int, object_key: str):
        """Start the initial set of async workers."""
        self.stop_event.clear()
        self.is_running = True

        workers_needed = min(concurrency, self.max_workers)

        # Set active_workers BEFORE starting workers
        self.active_workers = workers_needed

        # Initialize worker states with object key BEFORE starting workers
        for i in range(workers_needed):
            self.worker_states[i] = {
                "object_key": object_key,
                "consecutive_errors": 0,
                "requests_completed": 0,
                "total_errors": 0,
            }

        # Start persistence task if not already running
        if self.persistence_task is None or self.persistence_task.done():
            self.persistence_task = asyncio.create_task(self._persistence_task())

        # Start worker tasks
        for i in range(workers_needed):
            task = asyncio.create_task(self._worker_task(i))
            self.worker_tasks.append(task)

        logger.info(f"Started {workers_needed} initial workers")

    async def _adjust_worker_count(self, target_concurrency: int, object_key: str):
        """Adjust the number of active workers without stopping the pool."""
        current_workers = self.active_workers
        target_workers = min(target_concurrency, self.max_workers)

        if target_workers > current_workers:
            # Set active_workers BEFORE starting new workers
            self.active_workers = target_workers
            # Initialize worker states for new workers BEFORE starting them
            for i in range(current_workers, target_workers):
                self.worker_states[i] = {
                    "object_key": object_key,
                    "consecutive_errors": 0,
                    "requests_completed": 0,
                    "total_errors": 0,
                }
            # Start additional workers
            for i in range(current_workers, target_workers):
                task = asyncio.create_task(self._worker_task(i))
                self.worker_tasks.append(task)
            logger.info(f"Added {target_workers - current_workers} workers")
        elif target_workers < current_workers:
            # Mark excess workers for stopping
            logger.info(f"Reducing workers from {current_workers} to {target_workers}")
            self.active_workers = target_workers
        else:
            # No change needed, but update object key for existing workers
            for worker_id in range(target_workers):
                if worker_id in self.worker_states:
                    self.worker_states[worker_id]["object_key"] = object_key

    async def _worker_task(self, worker_id: int):
        """Async worker task that pipelines requests."""
        worker_state = self.worker_states.get(worker_id, {})
        in_flight_tasks: List[asyncio.Task] = []

        try:
            while not self.stop_event.is_set():
                # Check if this worker should still be active
                if worker_id >= self.active_workers:
                    logger.info(
                        f"Worker {worker_id} stopping due to reduced concurrency"
                    )
                    break

                # Get worker state
                worker_state = self.worker_states.get(worker_id, {})
                object_key = worker_state.get("object_key")

                if not object_key:
                    await asyncio.sleep(0.1)  # Brief wait before retry
                    continue

                # Maintain pipeline depth: keep multiple requests in flight
                while (
                    len(in_flight_tasks) < self.pipeline_depth
                    and not self.stop_event.is_set()
                ):
                    if worker_id >= self.active_workers:
                        break

                    # Create new download task
                    task = asyncio.create_task(
                        self._download_and_record(worker_id, object_key)
                    )
                    in_flight_tasks.append(task)

                # Wait for at least one task to complete
                if in_flight_tasks:
                    done, pending = await asyncio.wait(
                        in_flight_tasks,
                        return_when=asyncio.FIRST_COMPLETED,
                        timeout=60.0  # 60s timeout to detect hangs
                    )
                    in_flight_tasks = list(pending)
                    
                    # Warn if timeout with no completions
                    if not done and in_flight_tasks:
                        logger.warning(
                            f"Worker {worker_id} timeout: {len(in_flight_tasks)} tasks still pending"
                        )

                    # Process completed tasks
                    for task in done:
                        try:
                            success = await task
                            worker_state["requests_completed"] = (
                                worker_state.get("requests_completed", 0) + 1
                            )
                            
                            if not success:
                                worker_state["consecutive_errors"] = (
                                    worker_state.get("consecutive_errors", 0) + 1
                                )
                                worker_state["total_errors"] = (
                                    worker_state.get("total_errors", 0) + 1
                                )
                                if (
                                    worker_state["consecutive_errors"]
                                    >= MAX_CONSECUTIVE_ERRORS
                                ):
                                    logger.error(
                                        f"Worker {worker_id} stopping due to "
                                        f"{worker_state['consecutive_errors']} consecutive errors"
                                    )
                                    return
                            else:
                                worker_state["consecutive_errors"] = 0

                                # Log progress less frequently
                                if (
                                    worker_state["requests_completed"]
                                    % PROGRESS_INTERVAL
                                    == 0
                                ):
                                    logger.debug(
                                        f"Worker {worker_id}: "
                                        f"{worker_state['requests_completed']} requests completed"
                                    )
                            
                            # Check if error rate is too high (after sufficient requests)
                            requests_completed = worker_state.get("requests_completed", 0)
                            if requests_completed > 50:
                                total_errors = worker_state.get("total_errors", 0)
                                error_rate = total_errors / requests_completed if requests_completed > 0 else 0
                                if error_rate > 0.3:  # 30% error rate
                                    logger.error(
                                        f"Worker {worker_id} stopping: error rate too high "
                                        f"({error_rate:.1%}, {total_errors}/{requests_completed})"
                                    )
                                    return
                        except Exception as e:
                            logger.warning(f"Worker {worker_id} task error: {e}")
                            worker_state["consecutive_errors"] = (
                                worker_state.get("consecutive_errors", 0) + 1
                            )
                            worker_state["total_errors"] = (
                                worker_state.get("total_errors", 0) + 1
                            )
                            worker_state["requests_completed"] = (
                                worker_state.get("requests_completed", 0) + 1
                            )

        except Exception as e:
            logger.error(f"Worker {worker_id} fatal error: {e}")
        finally:
            # Wait for any remaining in-flight tasks
            if in_flight_tasks:
                await asyncio.gather(*in_flight_tasks, return_exceptions=True)

    async def _download_and_record(
        self, worker_id: int, object_key: str
    ) -> bool:
        """Download a range and record the result asynchronously.

        Returns:
            True if successful, False otherwise
        """
        try:
            # Calculate range for this request (using pre-computed ranges for performance)
            range_length = RANGE_SIZE_MB * BYTES_PER_MB
            range_start = self._get_next_range_start()

            # Record request start time
            request_start_ts = time.time()

            # Get current phase ID
            phase_id = self.current_phase_id

            # Download range with retry logic
            data = None
            latency_ms = 0
            rtt_ms = 0
            http_status = 500
            retry_count = 0

            while retry_count < MAX_RETRIES:
                try:
                    data, latency_ms, rtt_ms = await self.storage_system.download_range(
                        object_key, range_start, range_length
                    )
                    if data and len(data) > 0:
                        http_status = 200
                        break
                    else:
                        retry_count += 1
                        if retry_count < MAX_RETRIES:
                            # Exponential backoff: 2^retry_count seconds, max 30s
                            backoff_time = min(2 ** retry_count, 30)
                            await asyncio.sleep(backoff_time)
                except Exception as e:
                    retry_count += 1
                    logger.warning(
                        f"Worker {worker_id} retry {retry_count}/{MAX_RETRIES}: {e}"
                    )
                    if retry_count < MAX_RETRIES:
                        # Exponential backoff: 2^retry_count seconds, max 30s
                        backoff_time = min(2 ** retry_count, 30)
                        await asyncio.sleep(backoff_time)

            # Record request end time
            request_end_ts = time.time()

            # Determine bytes downloaded
            bytes_downloaded = len(data) if data else 0

            # Create benchmark record
            record = BenchmarkRecord(
                thread_id=worker_id,
                conn_id=worker_id,
                object_key=object_key,
                range_start=range_start,
                range_len=range_length,
                bytes=bytes_downloaded,
                latency_ms=latency_ms,
                rtt_ms=rtt_ms,
                http_status=http_status,
                concurrency=self.active_workers,
                phase_id=phase_id,
                start_ts=request_start_ts,
                end_ts=request_end_ts,
            )

            # Queue record for async persistence (non-blocking)
            try:
                self.persistence_queue.put_nowait(record)
            except asyncio.QueueFull:
                logger.warning(
                    f"Persistence queue full, dropping record from worker {worker_id}"
                )

            return http_status == 200

        except Exception as e:
            logger.error(f"Worker {worker_id} download error: {e}")
            return False

    async def _persistence_task(self):
        """Background task that processes persistence queue with batching."""
        batch = []
        last_flush = time.time()
        flush_interval = PERSISTENCE_FLUSH_INTERVAL_SECONDS

        try:
            while not self.stop_event.is_set() or not self.persistence_queue.empty():
                try:
                    # Wait for record with timeout to allow periodic flushing
                    record = await asyncio.wait_for(
                        self.persistence_queue.get(), timeout=0.1
                    )
                    batch.append(record)

                    # Flush if batch is full
                    if len(batch) >= self.persistence_batch_size:
                        await self._flush_batch(batch)
                        batch = []
                        last_flush = time.time()

                except asyncio.TimeoutError:
                    # Periodic flush even if batch not full
                    current_time = time.time()
                    if batch and (current_time - last_flush) >= flush_interval:
                        await self._flush_batch(batch)
                        batch = []
                        last_flush = current_time

            # Flush any remaining records
            if batch:
                await self._flush_batch(batch)

        except Exception as e:
            logger.error(f"Persistence task error: {e}")

    async def _flush_batch(self, batch: List[BenchmarkRecord]):
        """Flush a batch of records to persistence (non-blocking with timeout)."""
        if not batch:
            return

        # Check executor health
        if hasattr(self._persistence_executor, '_work_queue'):
            queue_size = self._persistence_executor._work_queue.qsize()
            if queue_size > 10:
                self._executor_queue_warnings += 1
                if self._executor_queue_warnings % 100 == 0:
                    logger.warning(
                        f"Executor queue backing up: {queue_size} items queued, "
                        f"{self._persistence_executor._max_workers} threads"
                    )

        loop = asyncio.get_event_loop()
        
        try:
            # Wrap in wait_for to prevent infinite blocking
            await asyncio.wait_for(
                loop.run_in_executor(
                    self._persistence_executor,
                    self._sync_flush_batch,
                    batch
                ),
                timeout=5.0  # 5 second timeout
            )
        except asyncio.TimeoutError:
            # Executor is overloaded, just drop this batch
            logger.warning(
                f"Persistence executor overloaded, dropping batch of {len(batch)} records"
            )
        except Exception as e:
            logger.error(f"Persistence flush error: {e}")

    def _sync_flush_batch(self, batch: List[BenchmarkRecord]):
        """Synchronously flush batch to persistence (called from executor)."""
        for record in batch:
            self.persistence.store_record(record)

    def get_step_stats(self, phase_id: str) -> Optional[Dict[str, Any]]:
        """Get step statistics for a phase from persistence records with proper prorating across phases."""
        # Get all records from persistence
        all_records = self.persistence.records

        if not all_records:
            return None

        # Convert records to DataFrame FIRST - this is our single source of truth
        # Both throughput and latency/RTT stats will use the same DataFrame
        records_data = []
        for record in all_records:
            records_data.append({
                'thread_id': record.thread_id,
                'conn_id': record.conn_id,
                'object_key': record.object_key,
                'range_start': record.range_start,
                'range_len': record.range_len,
                'bytes': record.bytes,
                'latency_ms': record.latency_ms,
                'rtt_ms': record.rtt_ms,
                'http_status': record.http_status,
                'concurrency': record.concurrency,
                'phase_id': record.phase_id,
                'start_ts': record.start_ts,
                'end_ts': record.end_ts
            })
        
        records_df = pd.DataFrame(records_data)
        
        # Get records that started in this phase (for basic stats and latency/RTT)
        phase_data = records_df[records_df['phase_id'] == phase_id]
        
        # Calculate basic statistics from records that started in this phase
        total_requests = len(phase_data)
        successful_requests = len(phase_data[phase_data['http_status'] == 200])
        error_requests = total_requests - successful_requests
        error_rate = error_requests / total_requests if total_requests > 0 else 0
        
        # Calculate latency statistics using shared utility (DataFrame-based)
        latency_stats = calculate_latency_stats(phase_data, latency_col='latency_ms')
        avg_latency = latency_stats['avg']
        p50_latency = latency_stats['p50']
        p95_latency = latency_stats['p95']
        p99_latency = latency_stats['p99']
        
        # Calculate RTT statistics using shared utility (DataFrame-based)
        rtt_stats = calculate_latency_stats(phase_data, latency_col='rtt_ms')
        avg_rtt = rtt_stats['avg']
        p50_rtt = rtt_stats['p50']
        p95_rtt = rtt_stats['p95']
        p99_rtt = rtt_stats['p99']
        
        # Use shared throughput calculation utility with prorating
        # This handles requests that span phase boundaries correctly
        throughput_result = calculate_phase_throughput_with_prorating(
            records_df,
            phase_id=phase_id
        )
        
        throughput_gbps = throughput_result['throughput_gbps']
        total_bytes = throughput_result['total_bytes']
        prorated_request_count = throughput_result['request_count']
        phase_start = throughput_result['phase_start']
        phase_end = throughput_result['phase_end']
        phase_duration = throughput_result['duration_seconds']

        return {
            "phase_id": phase_id,
            "concurrency": phase_data['concurrency'].iloc[0] if len(phase_data) > 0 else 0,
            "total_requests": total_requests,
            "successful_requests": successful_requests,
            "error_requests": error_requests,
            "error_rate": error_rate,
            "throughput_gbps": throughput_gbps,
            "avg_latency_ms": avg_latency,
            "p50_latency_ms": p50_latency,
            "p95_latency_ms": p95_latency,
            "p99_latency_ms": p99_latency,
            "avg_rtt_ms": avg_rtt,
            "p50_rtt_ms": p50_rtt,
            "p95_rtt_ms": p95_rtt,
            "p99_rtt_ms": p99_rtt,
            "total_bytes": total_bytes,
            "prorated_request_count": prorated_request_count,
            "phase_start": phase_start,
            "phase_end": phase_end,
            "duration_seconds": phase_duration,
        }

    async def stop_workers(self):
        """Stop all worker tasks."""
        if not self.is_running:
            return

        logger.info("Stopping worker pool...")
        self.stop_event.set()

        # Wait for all worker tasks to complete
        if self.worker_tasks:
            await asyncio.gather(*self.worker_tasks, return_exceptions=True)

        # Wait for persistence task to finish
        if self.persistence_task and not self.persistence_task.done():
            await self.persistence_task

        self.worker_tasks.clear()
        self.active_workers = 0
        self.is_running = False
        self.worker_states.clear()

        logger.info("Worker pool stopped")

    async def cleanup(self):
        """Clean up the worker pool."""
        await self.stop_workers()
        
        # Shutdown persistence executor
        if hasattr(self, '_persistence_executor'):
            self._persistence_executor.shutdown(wait=True)
        
        logger.info("Worker pool cleaned up")
