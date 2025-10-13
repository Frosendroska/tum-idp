"""
Sophisticated ramp-up algorithm for finding optimal concurrency with advanced architecture.
"""

import time
import logging
import threading
from typing import Dict, Any, List
from persistence.base import BenchmarkRecord
from persistence.metrics_aggregator import MetricsAggregator
from persistence.parquet import ParquetPersistence
from common import ResizableSemaphore, PhaseManager
from configuration import (
    RANGE_SIZE_MB, DEFAULT_OBJECT_KEY, RAMP_STEP_MINUTES, RAMP_STEP_CONCURRENCY, SYSTEM_BANDWIDTH_MBPS,
    PLATEAU_THRESHOLD, DEFAULT_OUTPUT_DIR, MEGABITS_PER_MB, BYTES_PER_MB, BYTES_PER_GB,
    MAX_ERROR_RATE, MIN_REQUESTS_FOR_ERROR_CHECK, MAX_CONSECUTIVE_ERRORS, PROGRESS_INTERVAL, MAX_RETRIES, MAX_CONCURRENCY
)
from algorithms.plateau_check import PlateauCheck

logger = logging.getLogger(__name__)


class Ramp:
    """Sophisticated algorithm to find optimal concurrency with advanced architecture."""
    
    def __init__(self, storage_system, initial_concurrency: int = 8, 
                 ramp_step: int = None, step_duration_seconds: int = None, object_key: str = None,
                 plateau_threshold: float = None, worker_bandwidth_mbps: float = None, output_dir: str = None):
        self.storage_system = storage_system
        self.initial_concurrency = initial_concurrency
        self.ramp_step = ramp_step or RAMP_STEP_CONCURRENCY
        self.step_duration_seconds = step_duration_seconds or (RAMP_STEP_MINUTES * 60)
        self.object_key = object_key or DEFAULT_OBJECT_KEY
        self.system_bandwidth_mbps = worker_bandwidth_mbps if worker_bandwidth_mbps is not None else SYSTEM_BANDWIDTH_MBPS
        
        # Initialize sophisticated components
        self.semaphore = ResizableSemaphore(initial_concurrency)
        self.phase_manager = PhaseManager()
        self.metrics_aggregator = MetricsAggregator()
        self.persistence = ParquetPersistence(output_dir=output_dir or DEFAULT_OUTPUT_DIR)
        self.plateau_checker = PlateauCheck(
            threshold=plateau_threshold or PLATEAU_THRESHOLD, 
            system_bandwidth_mbps=self.system_bandwidth_mbps
        )
        
        # Worker management
        self.workers: List[threading.Thread] = []
        self.stop_event = threading.Event()
        self.active_workers = 0
        self.max_workers = MAX_CONCURRENCY  # Maximum workers we'll ever need
        
        logger.info(f"Initialized sophisticated ramp with plateau detection and system bandwidth limit: {initial_concurrency} -> ?, step {self.ramp_step} every {self.step_duration_seconds}s, system limit: {self.system_bandwidth_mbps} Mbps")
    
    def _start_workers_for_phase(self, concurrency: int):
        """Start workers for a specific phase based on concurrency requirements."""
        # Stop any existing workers first
        self._stop_workers()

        # Clear the stop event so new workers can run
        self.stop_event.clear()

        # Calculate how many workers we need
        workers_needed = min(concurrency, self.max_workers)

        logger.info(f"Starting {workers_needed} workers for ramp concurrency {concurrency}")

        # Start new workers
        for i in range(workers_needed):
            worker = threading.Thread(
                target=self._worker_loop, args=(i,), name=f"Ramp-Worker-{i}"
            )
            worker.daemon = True
            worker.start()
            self.workers.append(worker)
            self.active_workers += 1
            logger.debug(f"Started ramp worker {i}")

        # Resize semaphore to match worker count
        self.semaphore.resize(workers_needed)

        logger.info(
            f"Started {len(self.workers)} ramp workers, semaphore permits: {self.semaphore.available_permits()}"
        )

    def _stop_workers(self):
        """Stop all worker threads."""
        if not self.workers:
            return

        logger.info("Stopping ramp worker threads...")
        self.stop_event.set()

        for worker in self.workers:
            worker.join(timeout=5)

        self.workers.clear()
        self.active_workers = 0
        logger.info("All ramp worker threads stopped")

    def _worker_loop(self, worker_id: int):
        """Worker thread loop that processes requests using the semaphore."""
        consecutive_errors = 0
        logger.info(f"Ramp worker {worker_id} started")

        while not self.stop_event.is_set():
            try:
                if not self.semaphore.acquire(timeout=1.0):
                    logger.warning(
                        f"Ramp worker {worker_id} failed to acquire semaphore permit (available: {self.semaphore.available_permits()})"
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
                                f"Ramp worker {worker_id} successful download: {len(data)} bytes in {latency_ms:.1f}ms"
                            )
                            break
                        else:
                            retry_count += 1
                            logger.warning(
                                f"Ramp worker {worker_id} empty data on retry {retry_count}/{max_retries}"
                            )
                            if retry_count < max_retries:
                                time.sleep(1.0)
                    except Exception as e:
                        retry_count += 1
                        logger.warning(
                            f"Ramp worker {worker_id} retry {retry_count}/{max_retries}: {e}"
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
                self.persistence.store_record(record)

                # Handle errors
                if http_status != 200:
                    consecutive_errors += 1
                    if consecutive_errors >= MAX_CONSECUTIVE_ERRORS:
                        logger.error(
                            f"Ramp worker {worker_id} stopping due to {consecutive_errors} consecutive errors"
                        )
                        break
                else:
                    consecutive_errors = 0

                # Log progress periodically
                if self.metrics_aggregator.get_total_records() % PROGRESS_INTERVAL == 0:
                    logger.info(
                        f"Ramp progress: {self.metrics_aggregator.get_total_records()} requests completed "
                        f"(phase: {phase_id}, in_flight: {self.semaphore.in_flight()})"
                    )

            except Exception as e:
                logger.warning(f"Ramp worker {worker_id} error: {e}")
                consecutive_errors += 1
                if consecutive_errors >= MAX_CONSECUTIVE_ERRORS:
                    logger.error(
                        f"Ramp worker {worker_id} stopping due to {consecutive_errors} consecutive errors"
                    )
                    break
                time.sleep(1)

            finally:
                # Always release the semaphore
                self.semaphore.release()

    def execute_step(self, concurrency: int, step_id: str):
        """Execute one ramp step at the given concurrency level."""
        logger.info(f"Starting ramp step: {concurrency} connections for {self.step_duration_seconds} seconds")
        
        # Begin new ramp step
        self.phase_manager.begin_phase(step_id, concurrency)
        
        # Start workers for this concurrency level
        self._start_workers_for_phase(concurrency)
        
        # Give workers a moment to start making requests before recording step start time
        time.sleep(2)  # Allow workers to initialize and start making requests
        
        # Set step start time after workers are actually running
        self.metrics_aggregator.set_phase_step_time(step_id, time.time())
        
        start_time = time.time()
        end_time = start_time + self.step_duration_seconds
        
        # Wait for the step duration
        while time.time() < end_time and not self.stop_event.is_set():
            time.sleep(0.1)
            
            # Check if we should start measuring
            phase_info = self.phase_manager.get_phase_info()
            if not phase_info.get("step_started", False):
                self.phase_manager.should_start_measuring(self.semaphore.in_flight())
        
        # Get step statistics
        step_stats = self.metrics_aggregator.get_step_stats(step_id)
        
        # Debug: Check total records and phase attribution
        total_records = self.metrics_aggregator.get_total_records()
        logger.info(f"Debug: Total records in ramp aggregator: {total_records}")
        
        if step_stats:
            logger.info(
                f"Ramp step completed: {step_stats['throughput_mbps']:.1f} Mbps, "
                f"{step_stats['successful_requests']}/{step_stats['total_requests']} requests"
            )
        else:
            logger.warning(f"No step statistics available for ramp step {step_id}")
            # Create fallback statistics
            step_stats = {
                "phase_id": step_id,
                "concurrency": concurrency,
                "throughput_mbps": 0.0,
                "total_requests": 0,
                "successful_requests": 0,
                "error_requests": 0,
                "error_rate": 1.0,
                "duration_seconds": self.step_duration_seconds,
                "avg_latency_ms": 0.0,
                "p50_latency_ms": 0.0,
                "p95_latency_ms": 0.0,
                "p99_latency_ms": 0.0,
                "total_bytes": 0,
            }
        
        return step_stats
    def find_optimal_concurrency(self, max_concurrency: int = 100):
        """Find optimal concurrency by ramping up until plateau is reached."""
        current_concurrency = self.initial_concurrency
        best_throughput = 0
        best_concurrency = current_concurrency
        step_results = []
        step_count = 0
        
        logger.info(f"Starting sophisticated concurrency optimization: {current_concurrency} -> {max_concurrency}")
        
        try:
            while current_concurrency <= max_concurrency and not self.stop_event.is_set():
                step_count += 1
                phase_id = f"ramp_{step_count}"
                
                logger.info(f"Executing ramp step {step_count} at {current_concurrency} connections...")
                
                # Execute step using sophisticated architecture
                step_result = self.execute_step(current_concurrency, phase_id)
                step_results.append(step_result)
                
                # Check error rate
                total_requests = step_result["total_requests"]
                error_rate = step_result["error_rate"]
                
                logger.info(f"Step completed: {step_result['throughput_mbps']:.1f} Mbps, "
                           f"{total_requests} requests, error rate: {error_rate:.1%}")
                
                # Check for high error rate
                if (
                    total_requests >= MIN_REQUESTS_FOR_ERROR_CHECK
                    and error_rate > MAX_ERROR_RATE
                ):
                    logger.warning(f"High error rate detected: {error_rate:.1%}")
                    break
                
                # Add measurement to plateau checker
                self.plateau_checker.add_measurement(
                    current_concurrency,
                    step_result["throughput_mbps"],
                    step_result["duration_seconds"],
                )
                
                # Check if we found better throughput
                if step_result["throughput_mbps"] > best_throughput:
                    best_throughput = step_result["throughput_mbps"]
                    best_concurrency = current_concurrency
                    logger.info(f"New best: {best_concurrency} conn, {best_throughput:.1f} Mbps")
                
                # Check for plateau using plateau detection algorithm
                plateau_reached, reason = self.plateau_checker.is_plateau_reached()
                if plateau_reached:
                    logger.info(f"Plateau detected: {reason}")
                    logger.info(f"Stopping ramp at {current_concurrency} connections")
                    break
                
                # Increase concurrency
                current_concurrency += self.ramp_step
            
            # Get plateau summary
            plateau_summary = self.plateau_checker.get_plateau_summary()
            
            # Save collected records to parquet file
            parquet_file = self.persistence.save_to_file("ramp_benchmark")
            
            return {
                'best_concurrency': best_concurrency,
                'best_throughput_mbps': best_throughput,
                'step_results': step_results,
                'plateau_detected': plateau_reached if 'plateau_reached' in locals() else False,
                'plateau_reason': reason if 'reason' in locals() else "Max concurrency reached",
                'plateau_summary': plateau_summary,
                'parquet_file': parquet_file
            }
            
        except Exception as e:
            logger.error(f"Error during ramp optimization: {e}")
            raise
        finally:
            # Always stop workers
            self._stop_workers()
