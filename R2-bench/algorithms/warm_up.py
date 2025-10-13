"""
Concurrent warm-up algorithm for the R2 benchmark with sophisticated architecture.
"""

import time
import logging
import threading
from typing import Dict, Any, List
from persistence.base import BenchmarkRecord
from persistence.metrics_aggregator import MetricsAggregator
from common import ResizableSemaphore, PhaseManager
from configuration import (
    RANGE_SIZE_MB, DEFAULT_OBJECT_KEY, INITIAL_CONCURRENCY, BYTES_PER_MB, BYTES_PER_GB,
    MAX_ERROR_RATE, MAX_CONSECUTIVE_ERRORS, PROGRESS_INTERVAL, MAX_RETRIES
)

logger = logging.getLogger(__name__)


class WarmUp:
    """Concurrent warm-up to stabilize connections using sophisticated architecture."""
    
    def __init__(self, storage_system, warm_up_minutes: int = 5, concurrency: int = None, 
                 object_key: str = None, system_bandwidth_mbps: float = None):
        self.storage_system = storage_system
        self.warm_up_minutes = warm_up_minutes
        self.concurrency = concurrency or INITIAL_CONCURRENCY
        self.object_key = object_key or DEFAULT_OBJECT_KEY
        self.system_bandwidth_mbps = system_bandwidth_mbps
        
        # Initialize sophisticated components
        self.semaphore = ResizableSemaphore(self.concurrency)
        self.phase_manager = PhaseManager()
        self.metrics_aggregator = MetricsAggregator()
        
        # Worker management
        self.workers: List[threading.Thread] = []
        self.stop_event = threading.Event()
        self.active_workers = 0
        self.max_workers = self.concurrency  # Maximum workers for warm-up
        
        logger.info(f"Initialized sophisticated warm-up: {warm_up_minutes} minutes, {self.concurrency} connections")
    
    def _start_workers_for_phase(self, concurrency: int):
        """Start workers for the warm-up phase based on concurrency requirements."""
        # Stop any existing workers first
        self._stop_workers()

        # Clear the stop event so new workers can run
        self.stop_event.clear()

        # Calculate how many workers we need
        workers_needed = min(concurrency, self.max_workers)

        logger.info(f"Starting {workers_needed} workers for warm-up concurrency {concurrency}")

        # Start new workers
        for i in range(workers_needed):
            worker = threading.Thread(
                target=self._worker_loop, args=(i,), name=f"WarmUp-Worker-{i}"
            )
            worker.daemon = True
            worker.start()
            self.workers.append(worker)
            self.active_workers += 1
            logger.debug(f"Started warm-up worker {i}")

        # Resize semaphore to match worker count
        self.semaphore.resize(workers_needed)

        logger.info(
            f"Started {len(self.workers)} warm-up workers, semaphore permits: {self.semaphore.available_permits()}"
        )

    def _stop_workers(self):
        """Stop all worker threads."""
        if not self.workers:
            return

        logger.info("Stopping warm-up worker threads...")
        self.stop_event.set()

        for worker in self.workers:
            worker.join(timeout=5)

        self.workers.clear()
        self.active_workers = 0
        logger.info("All warm-up worker threads stopped")

    def _worker_loop(self, worker_id: int):
        """Worker thread loop that processes requests using the semaphore."""
        consecutive_errors = 0
        logger.info(f"Warm-up worker {worker_id} started")

        while not self.stop_event.is_set():
            try:
                if not self.semaphore.acquire(timeout=1.0):
                    logger.warning(
                        f"Warm-up worker {worker_id} failed to acquire semaphore permit (available: {self.semaphore.available_permits()})"
                    )
                    continue

                # Calculate range for this worker
                range_start = (worker_id * RANGE_SIZE_MB * BYTES_PER_MB) % BYTES_PER_GB
                range_length = RANGE_SIZE_MB * BYTES_PER_MB

                # Record request start time
                request_start_ts = time.time()

                # Get current phase info right before the request
                phase_info = self.phase_manager.get_phase_info()
                phase_id = phase_info.get("phase_id", "")

                # Check if we should start measuring for this phase
                if phase_id and not phase_info.get("step_started", False):
                    self.phase_manager.should_start_measuring(
                        self.semaphore.in_flight()
                    )

                # Download range with retry logic
                data = None
                latency_ms = 0
                http_status = 500
                retry_count = 0
                max_retries = MAX_RETRIES

                while retry_count < max_retries:
                    try:
                        data, latency_ms = self.storage_system.download_range(
                            self.object_key, range_start, range_length
                        )
                        if data and len(data) > 0:
                            http_status = 200
                            logger.debug(
                                f"Warm-up worker {worker_id} successful download: {len(data)} bytes in {latency_ms:.1f}ms"
                            )
                            break
                        else:
                            retry_count += 1
                            logger.warning(
                                f"Warm-up worker {worker_id} empty data on retry {retry_count}/{max_retries}"
                            )
                            if retry_count < max_retries:
                                time.sleep(1.0)
                    except Exception as e:
                        retry_count += 1
                        logger.warning(
                            f"Warm-up worker {worker_id} retry {retry_count}/{max_retries}: {e}"
                        )
                        if retry_count < max_retries:
                            time.sleep(1.0)

                # Record request end time
                request_end_ts = time.time()

                # Determine bytes downloaded
                bytes_downloaded = len(data) if data else 0

                # Create benchmark record with phase attribution
                record = BenchmarkRecord(
                    thread_id=worker_id,
                    conn_id=worker_id,
                    object_key=self.object_key,
                    range_start=range_start,
                    range_len=range_length,
                    bytes_downloaded=bytes_downloaded,
                    latency_ms=latency_ms,
                    http_status=http_status,
                    concurrency=self.phase_manager.target_concurrency,
                    phase_id=phase_id,
                    start_ts=request_start_ts,
                    end_ts=request_end_ts,
                )

                # Record the request
                self.metrics_aggregator.record_request(record)

                # Handle errors
                if http_status != 200:
                    consecutive_errors += 1
                    if consecutive_errors >= MAX_CONSECUTIVE_ERRORS:
                        logger.error(
                            f"Warm-up worker {worker_id} stopping due to {consecutive_errors} consecutive errors"
                        )
                        break
                else:
                    consecutive_errors = 0

                # Log progress periodically
                if self.metrics_aggregator.get_total_records() % PROGRESS_INTERVAL == 0:
                    logger.info(
                        f"Warm-up progress: {self.metrics_aggregator.get_total_records()} requests completed "
                        f"(phase: {phase_id}, in_flight: {self.semaphore.in_flight()})"
                    )

            except Exception as e:
                logger.warning(f"Warm-up worker {worker_id} error: {e}")
                consecutive_errors += 1
                if consecutive_errors >= MAX_CONSECUTIVE_ERRORS:
                    logger.error(
                        f"Warm-up worker {worker_id} stopping due to {consecutive_errors} consecutive errors"
                    )
                    break
                time.sleep(1)

            finally:
                # Always release the semaphore
                self.semaphore.release()

    def execute(self):
        """Execute the sophisticated warm-up phase."""
        logger.info(f"Starting sophisticated warm-up phase with {self.concurrency} connections...")
        
        try:
            # Begin warm-up phase
            self.phase_manager.begin_phase("warmup", self.concurrency)
            
            # Start workers for this phase
            self._start_workers_for_phase(self.concurrency)
            
            # Give workers a moment to start making requests before recording step start time
            time.sleep(2)  # Allow workers to initialize and start making requests
            
            # Set step start time after workers are actually running
            self.metrics_aggregator.set_phase_step_time("warmup", time.time())
            
            warm_up_duration = self.warm_up_minutes * 60
            start_time = time.time()
            end_time = start_time + warm_up_duration
            
            # Wait for the warm-up duration
            while time.time() < end_time and not self.stop_event.is_set():
                time.sleep(0.1)
                
                # Check if we should start measuring
                phase_info = self.phase_manager.get_phase_info()
                if not phase_info.get("step_started", False):
                    self.phase_manager.should_start_measuring(self.semaphore.in_flight())
            
            # Get step statistics
            step_stats = self.metrics_aggregator.get_step_stats("warmup")
            
            # Debug: Check total records and phase attribution
            total_records = self.metrics_aggregator.get_total_records()
            logger.info(f"Debug: Total records in warm-up aggregator: {total_records}")
            
            if step_stats:
                logger.info(
                    f"Warm-up completed: {step_stats['throughput_mbps']:.1f} Mbps, "
                    f"{step_stats['successful_requests']}/{step_stats['total_requests']} requests"
                )
            else:
                logger.warning("No step statistics available for warm-up phase")
                # Create fallback statistics
                step_stats = {
                    "phase_id": "warmup",
                    "concurrency": self.concurrency,
                    "throughput_mbps": 0.0,
                    "total_requests": 0,
                    "successful_requests": 0,
                    "error_requests": 0,
                    "error_rate": 1.0,
                    "duration_seconds": warm_up_duration,
                    "avg_latency_ms": 0.0,
                    "p50_latency_ms": 0.0,
                    "p95_latency_ms": 0.0,
                    "p99_latency_ms": 0.0,
                    "total_bytes": 0,
                }
            
            return step_stats
            
        except Exception as e:
            logger.error(f"Error during warm-up: {e}")
            raise
        finally:
            # Always stop workers
            self._stop_workers()
