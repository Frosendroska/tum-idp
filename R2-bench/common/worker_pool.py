"""
Shared worker pool for reusing workers across benchmark phases.
"""

import time
import logging
import threading
import random
from typing import Dict, Any, List, Callable, Optional
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
    """Shared worker pool that can be reused across benchmark phases."""

    def __init__(
        self, storage_system, persistence: ParquetPersistence, max_workers: int = 100
    ):
        """Initialize the worker pool.

        Args:
            storage_system: Storage system to use for downloads
            persistence: Persistence object to store benchmark records
            max_workers: Maximum number of workers to create
        """
        self.storage_system = storage_system
        self.persistence = persistence
        self.max_workers = max_workers

        # Worker management
        self.workers: List[threading.Thread] = []
        self.stop_event = threading.Event()
        self.active_workers = 0
        self.is_running = False

        # Phase management
        self.current_phase_id: str = ""

        # Worker state
        self.worker_states = {}  # worker_id -> state dict

        logger.info(f"Initialized WorkerPool with max {max_workers} workers")

    def start_workers(self, concurrency: int, object_key: str, phase_id: str):
        """Start workers for a specific concurrency level and optionally begin a phase.

        Args:
            concurrency: Number of concurrent workers to start
            object_key: Object key to download
            phase_id: Optional phase identifier to begin
        """
        self.current_phase_id = phase_id
        logger.info(f"Began phase: {phase_id}")

        if self.is_running:
            logger.info(
                f"Adjusting worker pool from {self.active_workers} to {concurrency} workers"
            )
            self._adjust_worker_count(concurrency, object_key)
        else:
            logger.info(f"Starting worker pool with {concurrency} workers")
            self._start_initial_workers(concurrency, object_key)

        logger.info(f"Worker pool ready: {self.active_workers} workers")

    def _start_initial_workers(self, concurrency: int, object_key: str):
        """Start the initial set of workers."""
        self.stop_event.clear()
        self.is_running = True

        workers_needed = min(concurrency, self.max_workers)

        # Set active_workers BEFORE starting workers to avoid race condition
        self.active_workers = workers_needed

        # Initialize worker states with object key BEFORE starting workers
        for i in range(workers_needed):
            self.worker_states[i] = {
                "object_key": object_key,
                "consecutive_errors": 0,
                "requests_completed": 0,
            }

        for i in range(workers_needed):
            self._start_worker(i)

        logger.info(f"Started {workers_needed} initial workers")

    def _adjust_worker_count(self, target_concurrency: int, object_key: str):
        """Adjust the number of active workers without stopping the pool."""
        current_workers = self.active_workers
        target_workers = min(target_concurrency, self.max_workers)

        if target_workers > current_workers:
            # Set active_workers BEFORE starting new workers to avoid race condition
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
                self._start_worker(i)
            logger.info(f"Added {target_workers - current_workers} workers")
        elif target_workers < current_workers:
            # Mark excess workers for stopping (they'll stop when they finish current work)
            logger.info(f"Reducing workers from {current_workers} to {target_workers}")
            # Workers will naturally stop when not needed
            self.active_workers = target_workers
        else:
            # No change needed, but update object key for existing workers
            for worker_id in range(target_workers):
                if worker_id in self.worker_states:
                    self.worker_states[worker_id]["object_key"] = object_key

    def _start_worker(self, worker_id: int):
        """Start a single worker thread."""
        worker = threading.Thread(
            target=self._worker_loop,
            args=(worker_id,),
            name=f"WorkerPool-Worker-{worker_id}",
        )
        worker.daemon = True
        worker.start()
        self.workers.append(worker)

        # Initialize worker state only if it doesn't exist (for new workers added during adjustment)
        if worker_id not in self.worker_states:
            self.worker_states[worker_id] = {
                "object_key": None,
                "consecutive_errors": 0,
                "requests_completed": 0,
            }

    def _worker_loop(self, worker_id: int):
        """Worker thread loop that processes requests."""

        while not self.stop_event.is_set():
            try:
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
                    logger.warning(f"Worker {worker_id} has no object key, skipping")
                    continue

                # Calculate range for this worker
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
                        data, latency_ms = self.storage_system.download_range(
                            object_key, range_start, range_length
                        )
                        if data and len(data) > 0:
                            http_status = 200
                            break
                        else:
                            retry_count += 1
                            if retry_count < MAX_RETRIES:
                                time.sleep(1.0)
                    except Exception as e:
                        retry_count += 1
                        logger.warning(
                            f"Worker {worker_id} retry {retry_count}/{MAX_RETRIES}: {e}"
                        )
                        if retry_count < MAX_RETRIES:
                            time.sleep(1.0)

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

                # Record the request
                self.persistence.store_record(record)

                # Update worker state
                worker_state["requests_completed"] += 1

                # Handle errors
                if http_status != 200:
                    worker_state["consecutive_errors"] += 1
                    if worker_state["consecutive_errors"] >= MAX_CONSECUTIVE_ERRORS:
                        logger.error(
                            f"Worker {worker_id} stopping due to {worker_state['consecutive_errors']} consecutive errors"
                        )
                        break
                else:
                    worker_state["consecutive_errors"] = 0

                # Log progress less frequently to reduce noise
                if worker_state["requests_completed"] % (PROGRESS_INTERVAL) == 0:
                    logger.debug(
                        f"Worker {worker_id}: {worker_state['requests_completed']} requests completed"
                    )

            except Exception as e:
                logger.warning(f"Worker {worker_id} error: {e}")
                worker_state = self.worker_states.get(worker_id, {})
                worker_state["consecutive_errors"] = (
                    worker_state.get("consecutive_errors", 0) + 1
                )
                if worker_state["consecutive_errors"] >= MAX_CONSECUTIVE_ERRORS:
                    logger.error(
                        f"Worker {worker_id} stopping due to consecutive errors"
                    )
                    break

    def get_step_stats(self, phase_id: str) -> Optional[Dict[str, Any]]:
        """Get step statistics for a phase from persistence records."""
        # Get all records for this phase from persistence
        phase_records = [r for r in self.persistence.records if r.phase_id == phase_id]

        if not phase_records:
            return None

        # Calculate basic statistics
        total_requests = len(phase_records)
        successful_requests = len([r for r in phase_records if r.http_status == 200])
        error_requests = total_requests - successful_requests
        error_rate = error_requests / total_requests if total_requests > 0 else 0

        # Calculate latency statistics
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

        # Calculate throughput (simplified - total bytes / time)
        total_bytes = sum(r.bytes for r in phase_records if r.http_status == 200)
        if phase_records:
            duration_seconds = max(r.end_ts for r in phase_records) - min(
                r.start_ts for r in phase_records
            )
            throughput_mbps = (
                (total_bytes * 8) / (duration_seconds * 1_000_000)
                if duration_seconds > 0
                else 0
            )
        else:
            throughput_mbps = 0

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
            "duration_seconds": duration_seconds,
        }

    def stop_workers(self):
        """Stop all worker threads."""
        if not self.is_running:
            return

        logger.info("Stopping worker pool...")
        self.stop_event.set()

        # Wait for workers to finish
        for worker in self.workers:
            worker.join(timeout=5)

        self.workers.clear()
        self.active_workers = 0
        self.is_running = False
        self.worker_states.clear()

        logger.info("Worker pool stopped")

    def cleanup(self):
        """Clean up the worker pool."""
        self.stop_workers()
        logger.info("Worker pool cleaned up")
