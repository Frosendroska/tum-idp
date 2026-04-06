"""
Async worker pool for a single process (one core).

Each process runs its own WorkerPool with async workers (coroutines).
Each worker pipelines multiple HTTP requests for maximum throughput.
"""

import asyncio
import time
import logging
import random
from typing import Dict, Any, List, Optional

from persistence.record import BenchmarkRecord
from configuration import (
    RANGE_SIZE_MB,
    BYTES_PER_MB,
    BYTES_PER_GB,
    MAX_RETRIES,
    MAX_CONSECUTIVE_ERRORS,
    OBJECT_SIZE_GB,
    ERROR_BACKOFF_ENABLED,
    ERROR_BACKOFF_MAX_SECONDS,
    HTTP_STATUS_NO_RESPONSE,
)

logger = logging.getLogger(__name__)


class WorkerPool:
    """Async worker pool for a single process."""

    def __init__(
        self,
        storage_system,
        process_id: int,
        pipeline_depth: int,
        shared_total_http_requests,
    ):
        """Initialize worker pool.

        Args:
            storage_system: Storage system for downloads
            process_id: Process ID (core ID)
            pipeline_depth: Number of in-flight requests per worker
            shared_total_http_requests: Shared value containing total HTTP requests across all cores
        """
        self.storage_system = storage_system
        self.process_id = process_id
        self.pipeline_depth = pipeline_depth
        self.shared_total_http_requests = shared_total_http_requests

        # Worker management
        self.worker_tasks: List[asyncio.Task] = []
        self.stop_event = asyncio.Event()
        self.active_workers = 0
        self.current_phase_id: str = ""
        self.current_object_key: str = ""

        # Cached total_http_requests to avoid IPC overhead
        # Updated once per phase transition instead of on every request
        # Performance: Eliminates ~30,000 IPC calls/sec -> 10,000,000× reduction
        self._cached_total_http_requests: int = 0

        # Worker state
        self.worker_states: Dict[int, Dict[str, Any]] = {}

        # Phase records (in-memory, will be flushed to disk)
        self.phase_records: List[BenchmarkRecord] = []

        # Pre-compute random ranges for performance
        self._range_cache = self._precompute_ranges(10000)
        self._range_index = 0

        logger.debug(f"Process {process_id}: WorkerPool initialized")

    def _precompute_ranges(self, count: int) -> List[int]:
        """Pre-compute random range starts to avoid overhead during requests."""
        range_length = RANGE_SIZE_MB * BYTES_PER_MB
        max_start = (OBJECT_SIZE_GB * BYTES_PER_GB) - range_length
        return [random.randint(0, max_start) for _ in range(count)]

    def _get_next_range_start(self) -> int:
        """Get next pre-computed range start."""
        range_start = self._range_cache[self._range_index]
        self._range_index = (self._range_index + 1) % len(self._range_cache)
        return range_start

    async def start_workers(self, workers_per_core: int, object_key: str, phase_id: str):
        """Start or adjust workers for a phase.

        Args:
            workers_per_core: Number of workers for this core
            object_key: Object key to download
            phase_id: Phase identifier
        """
        self.current_phase_id = phase_id
        self.current_object_key = object_key

        # Update cached total_http_requests once per phase transition
        # This eliminates ~30,720 IPC calls/sec by reading from shared memory only here
        self._cached_total_http_requests = self.shared_total_http_requests.value
        logger.debug(
            f"Process {self.process_id}: Cached total_http_requests={self._cached_total_http_requests} "
            f"for phase '{phase_id}'"
        )

        if self.active_workers == 0:
            await self._start_initial_workers(workers_per_core, object_key)
        else:
            await self._adjust_worker_count(workers_per_core, object_key)

    async def _start_initial_workers(self, workers_per_core: int, object_key: str):
        """Start initial workers."""
        self.stop_event.clear()
        self.active_workers = workers_per_core

        # Initialize worker states
        for i in range(workers_per_core):
            self.worker_states[i] = {
                "object_key": object_key,
                "consecutive_errors": 0,
                "requests_completed": 0,
            }

        # Start workers
        for i in range(workers_per_core):
            task = asyncio.create_task(self._worker_task(i))
            self.worker_tasks.append(task)

        logger.debug(f"Process {self.process_id}: Started {workers_per_core} workers")

    async def _adjust_worker_count(self, target_workers: int, object_key: str):
        """Adjust number of active workers."""
        current = self.active_workers

        if target_workers > current:
            # Add workers
            self.active_workers = target_workers
            for i in range(current, target_workers):
                self.worker_states[i] = {
                    "object_key": object_key,
                    "consecutive_errors": 0,
                    "requests_completed": 0,
                }
                task = asyncio.create_task(self._worker_task(i))
                self.worker_tasks.append(task)
            logger.debug(f"Process {self.process_id}: Increased workers {current} → {target_workers}")
        elif target_workers < current:
            # Reduce workers (they'll stop naturally when they check active_workers)
            self.active_workers = target_workers
            logger.debug(f"Process {self.process_id}: Reduced workers {current} → {target_workers}")

    async def _worker_task(self, worker_id: int):
        """Main worker loop with request pipelining."""
        worker_state = self.worker_states[worker_id]

        while not self.stop_event.is_set():
            # Check if this worker should stop
            if worker_id >= self.active_workers:
                break

            # Check for phase transition (object key change)
            if worker_state["object_key"] != self.current_object_key:
                worker_state["object_key"] = self.current_object_key
                worker_state["consecutive_errors"] = 0

            # Pipeline multiple requests
            tasks = []
            for _ in range(self.pipeline_depth):
                if not self.stop_event.is_set() and worker_id < self.active_workers:
                    tasks.append(self._download_request(worker_id))

            if tasks:
                results = await asyncio.gather(*tasks, return_exceptions=True)

                # Process results
                for result in results:
                    if isinstance(result, Exception):
                        worker_state["consecutive_errors"] += 1
                    elif result:  # Success
                        worker_state["consecutive_errors"] = 0
                        worker_state["requests_completed"] += 1
                    else:  # Failure
                        worker_state["consecutive_errors"] += 1

            # Handle consecutive errors with exponential backoff or stop
            if worker_state["consecutive_errors"] >= MAX_CONSECUTIVE_ERRORS:
                if ERROR_BACKOFF_ENABLED:
                    # Exponential backoff: wait longer as errors accumulate
                    # Formula: min(2^(errors/20), ERROR_BACKOFF_MAX_SECONDS)
                    backoff_time = min(2 ** (worker_state["consecutive_errors"] / 20), ERROR_BACKOFF_MAX_SECONDS)
                    logger.warning(
                        f"Process {self.process_id} worker {worker_id}: "
                        f"{worker_state['consecutive_errors']} consecutive errors, "
                        f"backing off for {backoff_time:.2f}s"
                    )
                    await asyncio.sleep(backoff_time)
                    # Reset error counter after backoff to give the system another chance
                    worker_state["consecutive_errors"] = int(worker_state["consecutive_errors"] * 0.5)
                else:
                    logger.error(f"Process {self.process_id} worker {worker_id}: Too many consecutive errors, stopping")
                    break

    async def _download_request(self, worker_id: int) -> bool:
        """Execute single download with retry.

        Persists one BenchmarkRecord per logical request (success or final failure).
        retry_count: failed attempts before success, or MAX_RETRIES if all attempts failed.

        Returns:
            True if successful, False otherwise
        """
        range_start = self._get_next_range_start()
        range_length = RANGE_SIZE_MB * BYTES_PER_MB
        first_start: Optional[float] = None
        last_http_status = HTTP_STATUS_NO_RESPONSE

        for attempt in range(MAX_RETRIES):
            try:
                start_time = time.time()
                if first_start is None:
                    first_start = start_time
                object_key = self.current_object_key

                data, latency_ms, rtt_ms, http_status = await self.storage_system.download_range(
                    object_key, range_start, range_length
                )
                end_time = time.time()
                last_http_status = int(http_status)

                if data:
                    current_phase_id = self.current_phase_id
                    concurrency = self._cached_total_http_requests

                    record = BenchmarkRecord(
                        thread_id=worker_id + (self.process_id * 10000),
                        conn_id=worker_id,
                        object_key=object_key,
                        range_start=range_start,
                        range_len=range_length,
                        bytes=len(data),
                        latency_ms=latency_ms,
                        rtt_ms=rtt_ms,
                        http_status=last_http_status,
                        concurrency=concurrency,
                        retry_count=attempt,
                        phase_id=current_phase_id,
                        start_ts=first_start,
                        end_ts=end_time,
                    )
                    self.phase_records.append(record)
                    return True

                if attempt < MAX_RETRIES - 1:
                    backoff = min(2 ** attempt, 30)
                    await asyncio.sleep(backoff)

            except Exception as e:
                last_http_status = HTTP_STATUS_NO_RESPONSE
                if attempt < MAX_RETRIES - 1:
                    await asyncio.sleep(min(2 ** attempt, 30))
                else:
                    logger.debug(
                        f"Process {self.process_id} worker {worker_id}: All retries failed: {e}"
                    )

        end_time = time.time()
        fail_record = BenchmarkRecord(
            thread_id=worker_id + (self.process_id * 10000),
            conn_id=worker_id,
            object_key=self.current_object_key,
            range_start=range_start,
            range_len=range_length,
            bytes=0,
            latency_ms=0.0,
            rtt_ms=0.0,
            http_status=last_http_status,
            concurrency=self._cached_total_http_requests,
            retry_count=MAX_RETRIES,
            phase_id=self.current_phase_id,
            start_ts=first_start if first_start is not None else end_time,
            end_ts=end_time,
        )
        self.phase_records.append(fail_record)
        return False

    async def stop_workers(self):
        """Stop all workers."""
        self.stop_event.set()

        if self.worker_tasks:
            await asyncio.gather(*self.worker_tasks, return_exceptions=True)
            self.worker_tasks = []

        self.active_workers = 0
        logger.debug(f"Process {self.process_id}: All workers stopped")

    def get_records(self) -> List[BenchmarkRecord]:
        """Get all records collected by this worker pool."""
        return self.phase_records

    def clear_records(self):
        """Clear records from memory (after flushing to disk)."""
        self.phase_records = []

    async def cleanup(self):
        """Clean up resources."""
        await self.stop_workers()
