"""
Refactored Phase 1: Capacity discovery and plateau detection with precise concurrency control.
"""

import os
import sys
import logging
import argparse
import time
import threading
from typing import Dict, Any, List

# Add the current directory to Python path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from configuration import (
    WARM_UP_MINUTES, INITIAL_CONCURRENCY, RAMP_STEP_MINUTES, RAMP_STEP_CONCURRENCY,
    AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_REGION, DEFAULT_OBJECT_KEY, SYSTEM_BANDWIDTH_MBPS,
    MAX_CONCURRENCY, RANGE_SIZE_MB, BYTES_PER_MB, BYTES_PER_GB, MEGABITS_PER_MB,
    MAX_ERROR_RATE, MIN_REQUESTS_FOR_ERROR_CHECK, MAX_CONSECUTIVE_ERRORS, PROGRESS_INTERVAL,
    MAX_RETRIES
)
from systems.r2 import R2System
from systems.aws import AWSSystem
from common import ResizableSemaphore, PhaseManager
from persistence.base import BenchmarkRecord
from persistence.parquet import ParquetPersistence
from persistence.metrics_aggregator import MetricsAggregator
from algorithms.plateau_check import PlateauCheck

# Set up logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class CapacityChecker:
    """Refactored capacity checker with precise concurrency control and immediate phase switching."""
    
    def __init__(self, storage_type: str = "r2", object_key: str = None, worker_bandwidth_mbps: float = None):
        self.storage_type = storage_type.lower()
        self.object_key = object_key or DEFAULT_OBJECT_KEY
        self.system_bandwidth_mbps = worker_bandwidth_mbps if worker_bandwidth_mbps is not None else SYSTEM_BANDWIDTH_MBPS
        self.storage_system = None
        
        # Initialize components
        self.semaphore = ResizableSemaphore(INITIAL_CONCURRENCY)
        self.phase_manager = PhaseManager()
        self.metrics_aggregator = MetricsAggregator()
        self.persistence = ParquetPersistence()
        self.plateau_checker = PlateauCheck(system_bandwidth_mbps=self.system_bandwidth_mbps)
        
        # Worker management
        self.workers: List[threading.Thread] = []
        self.stop_event = threading.Event()
        self.active_workers = 0
        self.max_workers = MAX_CONCURRENCY  # Maximum workers we'll ever need
        
        # Initialize storage system
        self._initialize_storage()
        
        logger.info(f"Initialized capacity checker for {storage_type.upper()}")
        logger.info(f"System bandwidth limit: {self.system_bandwidth_mbps} Mbps")
        logger.info(f"Maximum workers: {self.max_workers}")
    
    def _initialize_storage(self):
        """Initialize the appropriate storage system."""
        try:
            if self.storage_type == "r2":
                credentials = {
                    'aws_access_key_id': AWS_ACCESS_KEY_ID,
                    'aws_secret_access_key': AWS_SECRET_ACCESS_KEY,
                    'region_name': 'auto'
                }
                self.storage_system = R2System(credentials)
                
            elif self.storage_type == "s3":
                credentials = {
                    'aws_access_key_id': AWS_ACCESS_KEY_ID,
                    'aws_secret_access_key': AWS_SECRET_ACCESS_KEY,
                    'region_name': AWS_REGION
                }
                self.storage_system = AWSSystem(credentials)
                
            else:
                raise ValueError(f"Unsupported storage type: {self.storage_type}")
                
        except Exception as e:
            logger.error(f"Failed to initialize {self.storage_type.upper()} storage: {e}")
            raise
    
    def _start_workers_for_phase(self, concurrency: int):
        """Start workers for a specific phase based on concurrency requirements."""
        # Stop any existing workers first
        self._stop_workers()
        
        # Clear the stop event so new workers can run
        self.stop_event.clear()
        
        # Calculate how many workers we need
        workers_needed = min(concurrency, self.max_workers)
        
        logger.info(f"Starting {workers_needed} workers for concurrency {concurrency}")
        
        # Start new workers
        for i in range(workers_needed):
            worker = threading.Thread(
                target=self._worker_loop,
                args=(i,),
                name=f"Worker-{i}"
            )
            worker.daemon = True
            worker.start()
            self.workers.append(worker)
            self.active_workers += 1
            logger.debug(f"Started worker {i}")
        
        # Resize semaphore to match worker count
        self.semaphore.resize(workers_needed)
        
        logger.info(f"Started {len(self.workers)} workers, semaphore permits: {self.semaphore.available_permits()}")
    
    def _stop_workers(self):
        """Stop all worker threads."""
        if not self.workers:
            return
            
        logger.info("Stopping worker threads...")
        self.stop_event.set()
        
        for worker in self.workers:
            worker.join(timeout=5)
        
        self.workers.clear()
        self.active_workers = 0
        logger.info("All worker threads stopped")
    
    def _worker_loop(self, worker_id: int):
        """Worker thread loop that processes requests using the semaphore."""
        consecutive_errors = 0
        logger.info(f"Worker {worker_id} started")
        
        while not self.stop_event.is_set():
            try:
                # Acquire semaphore permit
                logger.debug(f"Worker {worker_id} attempting to acquire semaphore permit (available: {self.semaphore.available_permits()})")
                if not self.semaphore.acquire(timeout=1.0):
                    logger.debug(f"Worker {worker_id} failed to acquire semaphore permit (available: {self.semaphore.available_permits()})")
                    continue
                
                logger.debug(f"Worker {worker_id} acquired semaphore permit (remaining: {self.semaphore.available_permits()})")
                
                # Calculate range for this worker
                range_start = (worker_id * RANGE_SIZE_MB * BYTES_PER_MB) % BYTES_PER_GB
                range_length = RANGE_SIZE_MB * BYTES_PER_MB
                
                # Record request start time
                request_start_ts = time.time()
                
                # Get current phase info right before the request
                phase_info = self.phase_manager.get_phase_info()
                phase_id = phase_info.get('phase_id', '')
                
                # Log phase assignment for debugging
                logger.debug(f"Worker {worker_id} assigned to phase: '{phase_id}' (target_concurrency: {phase_info.get('target_concurrency', 'N/A')})")
                
                # Check if we should start measuring for this phase
                if phase_id and not phase_info.get('step_started', False):
                    self.phase_manager.should_start_measuring(self.semaphore.in_flight())
                
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
                            break
                        else:
                            retry_count += 1
                            logger.warning(f"Worker {worker_id} empty data on retry {retry_count}/{max_retries}")
                            if retry_count < max_retries:
                                time.sleep(1.0)  # Longer delay before retry for large downloads
                    except Exception as e:
                        retry_count += 1
                        logger.warning(f"Worker {worker_id} retry {retry_count}/{max_retries}: {e}")
                        if retry_count < max_retries:
                            time.sleep(1.0)  # Longer delay before retry for large downloads
                
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
                    end_ts=request_end_ts
                )
                
                # Record the request
                self.metrics_aggregator.record_request(record)
                self.persistence.store_record(record)
                
                # Handle errors
                if http_status != 200:
                    consecutive_errors += 1
                    if consecutive_errors >= MAX_CONSECUTIVE_ERRORS:
                        logger.error(f"Worker {worker_id} stopping due to {consecutive_errors} consecutive errors")
                        break
                else:
                    consecutive_errors = 0
                
                # Log progress periodically
                if self.metrics_aggregator.get_total_records() % PROGRESS_INTERVAL == 0:
                    logger.info(f"Progress: {self.metrics_aggregator.get_total_records()} requests completed "
                              f"(phase: {phase_id}, in_flight: {self.semaphore.in_flight()})")
                
            except Exception as e:
                logger.warning(f"Worker {worker_id} error: {e}")
                consecutive_errors += 1
                if consecutive_errors >= MAX_CONSECUTIVE_ERRORS:
                    logger.error(f"Worker {worker_id} stopping due to {consecutive_errors} consecutive errors")
                    break
                time.sleep(1)
            
            finally:
                # Always release the semaphore
                self.semaphore.release()
    
    def _run_phase(self, duration_seconds: float) -> Dict[str, Any]:
        """Run a phase for the specified duration.
        
        Args:
            duration_seconds: How long to run the phase
            
        Returns:
            Phase results
        """
        phase_info = self.phase_manager.get_phase_info()
        phase_id = phase_info.get('phase_id', 'unknown')
        target_concurrency = phase_info.get('target_concurrency', 0)
        
        logger.info(f"Running phase {phase_id} for {duration_seconds:.1f}s with target concurrency {target_concurrency}")
        
        start_time = time.time()
        end_time = start_time + duration_seconds
        
        # Wait for the phase duration
        while time.time() < end_time and not self.stop_event.is_set():
            time.sleep(0.1)
            
            # Check if we should start measuring
            if not phase_info.get('step_started', False):
                self.phase_manager.should_start_measuring(self.semaphore.in_flight())
                phase_info = self.phase_manager.get_phase_info()
        
        # Get step statistics
        step_stats = self.metrics_aggregator.get_step_stats(phase_id)
        
        if step_stats:
            logger.info(f"Phase {phase_id} completed: {step_stats['throughput_mbps']:.1f} Mbps, "
                       f"{step_stats['successful_requests']}/{step_stats['total_requests']} requests")
        else:
            logger.warning(f"No step statistics available for phase {phase_id}")
            # Create fallback statistics to ensure we always have some data
            step_stats = {
                'phase_id': phase_id,
                'concurrency': target_concurrency,
                'throughput_mbps': 0.0,
                'total_requests': 0,
                'successful_requests': 0,
                'error_requests': 0,
                'error_rate': 1.0,  # 100% error rate if no successful requests
                'duration_seconds': duration_seconds,
                'avg_latency_ms': 0.0,
                'p50_latency_ms': 0.0,
                'p95_latency_ms': 0.0,
                'p99_latency_ms': 0.0,
                'total_bytes': 0
            }
        
        return step_stats
    
    def _ensure_test_object_exists(self):
        """Ensure test object exists, create if necessary."""
        try:
            logger.info("Checking if test object exists...")
            response = self.storage_system.client.head_object(Bucket=self.storage_system.bucket_name, Key=self.object_key)
            logger.info(f"Test object found: {response['ContentLength']} bytes")
        except Exception as e:
            logger.warning(f"Test object not found or error accessing it: {e}")
            logger.info("Attempting to create a smaller test object for more reliable testing...")
            
            # Try to create a smaller test object (1GB instead of 9GB)
            try:
                from cli.uploader import Uploader
                uploader = Uploader(self.storage_type)
                success = uploader.upload_test_object(size_gb=1, object_key="test-object-1gb")
                if success:
                    self.object_key = "test-object-1gb"
                    logger.info("Successfully created 1GB test object, using it for benchmarking")
                else:
                    logger.error("Failed to create test object")
                    raise
            except Exception as upload_error:
                logger.error(f"Failed to create test object: {upload_error}")
                logger.error("Please run 'python cli.py upload --storage r2' first to create the test object")
                raise

    def _run_warmup_phase(self):
        """Run the warm-up phase."""
        logger.info("=== Phase 1: Concurrent Warm-up ===")
        self.phase_manager.begin_phase("warmup", INITIAL_CONCURRENCY)
        
        # Start workers for this phase
        self._start_workers_for_phase(INITIAL_CONCURRENCY)
        
        # Give workers a moment to start making requests before recording step start time
        time.sleep(2)  # Allow workers to initialize and start making requests
        
        # Set step start time after workers are actually running
        self.metrics_aggregator.set_phase_step_time("warmup", time.time())
        
        warm_up_duration = WARM_UP_MINUTES * 60
        warm_up_results = self._run_phase(warm_up_duration)
        
        logger.info(f"Warm-up completed: {warm_up_results['throughput_mbps']:.1f} Mbps")
        return warm_up_results

    def _run_rampup_phase(self):
        """Run the ramp-up phase to find optimal concurrency."""
        logger.info("=== Phase 2: Ramp-up ===")
        logger.info(f"Starting ramp: {INITIAL_CONCURRENCY} -> {MAX_CONCURRENCY}, step {RAMP_STEP_CONCURRENCY} every {RAMP_STEP_MINUTES}m")
        
        current_concurrency = INITIAL_CONCURRENCY
        best_throughput = 0
        best_concurrency = current_concurrency
        step_results = []
        step_count = 0
        plateau_reached = False
        reason = 'Max concurrency reached'
        
        while current_concurrency <= MAX_CONCURRENCY and not self.stop_event.is_set():
            step_count += 1
            phase_id = f"ramp_{step_count}"
            
            # Begin new ramp step
            self.phase_manager.begin_phase(phase_id, current_concurrency)
            
            # Start workers for this concurrency level
            self._start_workers_for_phase(current_concurrency)
            
            # Give workers a moment to start making requests before recording step start time
            time.sleep(2)  # Allow workers to initialize and start making requests
            
            # Set step start time after workers are actually running
            self.metrics_aggregator.set_phase_step_time(phase_id, time.time())
            
            logger.info(f"Starting ramp step {step_count}: {current_concurrency} connections")
            
            # Run the step
            step_result = self._run_phase(RAMP_STEP_MINUTES * 60)
            step_results.append(step_result)
            
            # Check error rate
            total_requests = step_result['total_requests']
            error_rate = step_result['error_rate']
            
            if total_requests >= MIN_REQUESTS_FOR_ERROR_CHECK and error_rate > MAX_ERROR_RATE:
                logger.warning(f"High error rate detected: {error_rate:.1%}")
                break
            
            # Add measurement to plateau checker
            self.plateau_checker.add_measurement(
                current_concurrency, 
                step_result['throughput_mbps'], 
                step_result['duration_seconds']
            )
            
            # Check if we found better throughput
            if step_result['throughput_mbps'] > best_throughput:
                best_throughput = step_result['throughput_mbps']
                best_concurrency = current_concurrency
                logger.info(f"New best: {best_concurrency} conn, {best_throughput:.1f} Mbps")
            
            # Check for plateau
            plateau_reached, reason = self.plateau_checker.is_plateau_reached()
            if plateau_reached:
                logger.info(f"Plateau detected: {reason}")
                break
            
            # Increase concurrency for next step
            current_concurrency += RAMP_STEP_CONCURRENCY
        
        return {
            'best_concurrency': best_concurrency,
            'best_throughput_mbps': best_throughput,
            'step_results': step_results,
            'plateau_reached': plateau_reached,
            'reason': reason
        }

    def check_capacity(self, object_key: str = None):
        """Execute the refactored capacity discovery process."""
        if object_key:
            self.object_key = object_key
        
        logger.info("Starting capacity discovery process")
        logger.info(f"Using object key: {self.object_key}")
        
        try:
            # Ensure test object exists
            self._ensure_test_object_exists()
            
            # Phase 1: Warm-up
            warm_up_results = self._run_warmup_phase()
            
            # Phase 2: Ramp-up to find optimal concurrency
            ramp_results = self._run_rampup_phase()
            
            # Get plateau summary
            plateau_summary = self.plateau_checker.get_plateau_summary()
            
            # Save results to parquet
            parquet_file = self.persistence.save_to_file("refactored_benchmark")
            
            # Report results
            logger.info("=== Capacity Discovery Results ===")
            logger.info(f"Best concurrency: {ramp_results['best_concurrency']}")
            logger.info(f"Best throughput: {ramp_results['best_throughput_mbps']:.1f} Mbps")
            logger.info(f"Steps completed: {len(ramp_results['step_results'])}")
            logger.info(f"Plateau detected: {ramp_results['plateau_reached']}")
            logger.info(f"Plateau reason: {ramp_results['reason']}")
            
            # Show step-by-step results
            for i, step in enumerate(ramp_results['step_results']):
                logger.info(f"Step {i+1}: {step['concurrency']} conn -> {step['throughput_mbps']:.1f} Mbps")
            
            if parquet_file:
                logger.info(f"Detailed results saved to: {parquet_file}")
            
            return {
                'warm_up': warm_up_results,
                'ramp_up': {
                    'best_concurrency': ramp_results['best_concurrency'],
                    'best_throughput_mbps': ramp_results['best_throughput_mbps'],
                    'step_results': ramp_results['step_results'],
                    'plateau_detected': ramp_results['plateau_reached'],
                    'plateau_reason': ramp_results['reason'],
                    'plateau_summary': plateau_summary,
                    'parquet_file': parquet_file
                },
                'optimal_concurrency': ramp_results['best_concurrency'],
                'max_throughput_mbps': ramp_results['best_throughput_mbps'],
                'plateau_detected': ramp_results['plateau_reached'],
                'plateau_reason': ramp_results['reason']
            }
            
        except KeyboardInterrupt:
            logger.info("Benchmark interrupted by user (Ctrl+C)")
            return {
                'warm_up': {'error': 'Interrupted by user'},
                'ramp_up': {'error': 'Interrupted by user'},
                'optimal_concurrency': 0,
                'max_throughput_mbps': 0,
                'plateau_detected': False,
                'plateau_reason': 'Interrupted by user'
            }
        except Exception as e:
            logger.error(f"Error during benchmark: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            raise
        finally:
            # Always stop workers
            self._stop_workers()


def main():
    """Main entry point for the refactored capacity checker."""
    parser = argparse.ArgumentParser(description='Refactored R2 capacity checker')
    parser.add_argument('--storage', choices=['r2', 's3'], default='r2', help='Storage type')
    parser.add_argument('--object-key', help='Object key to test')
    parser.add_argument('--worker-bandwidth', type=float, help='Worker bandwidth limit in Mbps')
    
    args = parser.parse_args()
    
    checker = CapacityChecker(
        storage_type=args.storage,
        object_key=args.object_key,
        worker_bandwidth_mbps=args.worker_bandwidth
    )
    
    try:
        results = checker.check_capacity()
        print("\n=== Final Results ===")
        print(f"Optimal concurrency: {results['optimal_concurrency']}")
        print(f"Max throughput: {results['max_throughput_mbps']:.1f} Mbps")
        print(f"Plateau detected: {results['plateau_detected']}")
        print(f"Plateau reason: {results['plateau_reason']}")
    except KeyboardInterrupt:
        logger.info("Benchmark interrupted by user")
    except Exception as e:
        logger.error(f"Benchmark failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
