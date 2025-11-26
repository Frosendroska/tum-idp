"""
High-performance async worker pool for S3/R2 benchmarking with request pipelining.
"""

import asyncio
import time
import logging
import random
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
)

logger = logging.getLogger(__name__)


class WorkerPool:
    """High-performance async worker pool with request pipelining and async persistence."""

    def __init__(
        self,
        storage_system,
        persistence: ParquetPersistence,
        max_workers: int = 500,
        pipeline_depth: int = 3,
        persistence_batch_size: int = 100,
    ):
        """Initialize the async worker pool.

        Args:
            storage_system: Async storage system to use for downloads
            persistence: Persistence object to store benchmark records
            max_workers: Maximum number of concurrent workers
            pipeline_depth: Number of in-flight requests per worker (pipelining)
            persistence_batch_size: Number of records to batch before writing
        """
        self.storage_system = storage_system
        self.persistence = persistence
        self.max_workers = max_workers
        self.pipeline_depth = pipeline_depth
        self.persistence_batch_size = persistence_batch_size

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

        # Dedicated executor for persistence I/O (prevents bottleneck)
        self._persistence_executor = ThreadPoolExecutor(
            max_workers=4,
            thread_name_prefix="persistence"
        )

        logger.info(
            f"Initialized WorkerPool with max {max_workers} workers, "
            f"pipeline_depth={pipeline_depth}, batch_size={persistence_batch_size}"
        )

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
                            if not success:
                                worker_state["consecutive_errors"] = (
                                    worker_state.get("consecutive_errors", 0) + 1
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
                                worker_state["requests_completed"] = (
                                    worker_state.get("requests_completed", 0) + 1
                                )

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
                        except Exception as e:
                            logger.warning(f"Worker {worker_id} task error: {e}")
                            worker_state["consecutive_errors"] = (
                                worker_state.get("consecutive_errors", 0) + 1
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
            # Calculate range for this request
            range_length = RANGE_SIZE_MB * BYTES_PER_MB
            max_start = (OBJECT_SIZE_GB * BYTES_PER_GB) - range_length
            range_start = random.randint(0, max_start)

            # Record request start time
            request_start_ts = time.time()

            # Get current phase ID
            phase_id = self.current_phase_id

            # Download range with retry logic
            data = None
            latency_ms = 0
            http_status = 500
            retry_count = 0

            while retry_count < MAX_RETRIES:
                try:
                    data, latency_ms = await self.storage_system.download_range(
                        object_key, range_start, range_length
                    )
                    if data and len(data) > 0:
                        http_status = 200
                        break
                    else:
                        retry_count += 1
                        if retry_count < MAX_RETRIES:
                            await asyncio.sleep(1.0)
                except Exception as e:
                    retry_count += 1
                    logger.warning(
                        f"Worker {worker_id} retry {retry_count}/{MAX_RETRIES}: {e}"
                    )
                    if retry_count < MAX_RETRIES:
                        await asyncio.sleep(1.0)

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
                bytes_downloaded=bytes_downloaded,
                latency_ms=latency_ms,
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
        flush_interval = 1.0  # Flush every second even if batch not full

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
        """Flush a batch of records to persistence (runs in executor to avoid blocking)."""
        if not batch:
            return

        # Run synchronous persistence in dedicated executor to avoid blocking event loop
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            self._persistence_executor,
            self._sync_flush_batch,
            batch  # No copy needed - executor handles thread safety
        )

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

        # Get records that started in this phase (for latency/concurrency stats)
        phase_records = [r for r in all_records if r.phase_id == phase_id]

        # Calculate basic statistics from records that started in this phase
        total_requests = len(phase_records)
        successful_requests = len(
            [r for r in phase_records if r.http_status == 200]
        )
        error_requests = total_requests - successful_requests
        error_rate = error_requests / total_requests if total_requests > 0 else 0

        # Calculate latency statistics from records that started in this phase
        latencies = [r.latency_ms for r in phase_records if r.http_status == 200]
        avg_latency = sum(latencies) / len(latencies) if latencies else 0

        # Calculate percentile latencies
        if latencies:
            sorted_latencies = sorted(latencies)
            n = len(sorted_latencies)
            p50_latency = sorted_latencies[int(0.5 * n)] if n > 0 else 0
            p95_latency = sorted_latencies[int(0.95 * n)] if n > 0 else 0
            p99_latency = sorted_latencies[int(0.99 * n)] if n > 0 else 0
        else:
            p50_latency = p95_latency = p99_latency = 0

        # Calculate phase boundaries for prorating
        if phase_records:
            phase_start = min(r.start_ts for r in phase_records)
            phase_end = max(r.end_ts for r in phase_records)
            phase_duration = phase_end - phase_start
        else:
            phase_start = phase_end = phase_duration = 0

        # Prorate bytes from ALL successful requests that overlap with this phase
        total_bytes = 0.0
        prorated_request_count = 0

        for record in all_records:
            if record.http_status != 200:
                continue

            # Check if request overlaps with this phase
            if record.start_ts < phase_end and record.end_ts > phase_start:
                # Calculate overlap
                overlap_start = max(record.start_ts, phase_start)
                overlap_end = min(record.end_ts, phase_end)
                overlap_duration = max(0, overlap_end - overlap_start)

                # Calculate total request duration
                request_duration = record.end_ts - record.start_ts

                if request_duration > 0:
                    # Prorate bytes based on overlap
                    prorated_bytes = (record.bytes * overlap_duration) / request_duration
                    total_bytes += prorated_bytes
                    prorated_request_count += 1

        # Calculate throughput using prorated bytes
        throughput_mbps = (
            (total_bytes * 8) / (phase_duration * 1_000_000)
            if phase_duration > 0
            else 0
        )

        return {
            "phase_id": phase_id,
            "concurrency": phase_records[0].concurrency if phase_records else 0,
            "total_requests": total_requests,
            "successful_requests": successful_requests,
            "error_requests": error_requests,
            "error_rate": error_rate,
            "throughput_mbps": throughput_mbps,
            "avg_latency_ms": avg_latency,
            "p50_latency_ms": p50_latency,
            "p95_latency_ms": p95_latency,
            "p99_latency_ms": p99_latency,
            "total_bytes": total_bytes,
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
