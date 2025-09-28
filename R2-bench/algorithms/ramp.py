"""
Simple ramp-up algorithm for finding optimal concurrency.
"""

import time
import logging
import threading
from persistence.base import BenchmarkRecord
from persistence.parquet import ParquetPersistence
from configuration import (
    RANGE_SIZE_MB, DEFAULT_OBJECT_KEY, RAMP_STEP_SECONDS, RAMP_STEP_CONCURRENCY, WORKER_BANDWIDTH_MBPS,
    PLATEAU_THRESHOLD, DEFAULT_OUTPUT_DIR, MEGABITS_PER_MB, BYTES_PER_MB, BYTES_PER_GB,
    MAX_ERROR_RATE, MIN_REQUESTS_FOR_ERROR_CHECK, MAX_CONSECUTIVE_ERRORS, LOG_REQUESTS_INTERVAL
)
from algorithms.plateu_check import PlateauCheck

logger = logging.getLogger(__name__)


class Ramp:
    """Algorithm to find optimal concurrency."""
    
    def __init__(self, storage_system, initial_concurrency: int = 8, 
                 ramp_step: int = None, step_duration_seconds: int = None, object_key: str = None,
                 plateau_threshold: float = None, worker_bandwidth_mbps: float = None, output_dir: str = None):
        self.storage_system = storage_system
        self.initial_concurrency = initial_concurrency
        self.ramp_step = ramp_step or RAMP_STEP_CONCURRENCY
        self.step_duration_seconds = step_duration_seconds or RAMP_STEP_SECONDS
        self.object_key = object_key or DEFAULT_OBJECT_KEY
        self.range_size_mb = RANGE_SIZE_MB
        self.worker_bandwidth_mbps = worker_bandwidth_mbps if worker_bandwidth_mbps is not None else WORKER_BANDWIDTH_MBPS
        self.plateau_checker = PlateauCheck(threshold=plateau_threshold or PLATEAU_THRESHOLD, worker_bandwidth_mbps=self.worker_bandwidth_mbps)
        self.persistence = ParquetPersistence(output_dir=output_dir or DEFAULT_OUTPUT_DIR)
        self.records_lock = threading.Lock()
        
        logger.info(f"Initialized ramp with plateau detection and worker bandwidth limit: {initial_concurrency} -> ?, step {self.ramp_step} every {self.step_duration_seconds}s, worker limit: {self.worker_bandwidth_mbps} Mbps")
    
    def execute_step(self, concurrency: int):
        """Execute one ramp step at the given concurrency level."""
        step_duration = self.step_duration_seconds
        step_start = time.time()
        
        logger.info(f"Starting ramp step: {concurrency} connections for {self.step_duration_seconds} seconds")
        
        # Simple concurrent requests
        results = {
            'concurrency': concurrency,
            'requests': 0,
            'successful': 0,
            'bytes': 0,
            'latency': 0,
            'errors': 0
        }
        
        # Create worker threads
        threads = []
        for i in range(concurrency):
            thread = threading.Thread(
                target=self._worker_function,
                args=(i, results, step_start, step_duration, concurrency)
            )
            thread.start()
            threads.append(thread)
        
        # Wait for all threads to complete
        logger.debug(f"Waiting for {len(threads)} worker threads to complete...")
        for thread in threads:
            thread.join()
        logger.debug("All worker threads completed")
        
        # Calculate throughput
        step_duration_actual = time.time() - step_start
        if results['successful'] > 0:
            throughput_mbps = (results['bytes'] * 8) / (step_duration_actual * MEGABITS_PER_MB)
        else:
            throughput_mbps = 0
        
        results['throughput_mbps'] = throughput_mbps
        results['duration'] = step_duration_actual
        
        logger.info(f"Ramp step completed: {concurrency} conn, {throughput_mbps:.1f} Mbps")
        return results
    
    def _worker_function(self, worker_id, results, step_start, step_duration, concurrency):
        """Worker thread function."""
        while time.time() - step_start < step_duration:
            try:
                # Calculate range for this worker
                range_start = (worker_id * self.range_size_mb * BYTES_PER_MB) % BYTES_PER_GB
                range_length = self.range_size_mb * BYTES_PER_MB
                
                # Download range
                data, latency_ms = self.storage_system.download_range(
                    self.object_key, range_start, range_length
                )
                
                # Determine HTTP status based on success
                http_status = 200 if data and len(data) > 0 else 500
                bytes_downloaded = len(data) if data else 0
                
                # Create benchmark record
                record = BenchmarkRecord(
                    thread_id=worker_id,
                    conn_id=worker_id,  # Using worker_id as conn_id for simplicity
                    object_key=self.object_key,
                    range_start=range_start,
                    range_len=range_length,
                    bytes_downloaded=bytes_downloaded,
                    latency_ms=latency_ms,
                    http_status=http_status,
                    concurrency=concurrency
                )
                
                # Store record
                with self.records_lock:
                    self.persistence.store_record(record)
                
                # Update results (thread-safe)
                with self.records_lock:
                    results['requests'] += 1
                    if data and len(data) > 0:
                        results['successful'] += 1
                        results['bytes'] += len(data)
                        results['latency'] += latency_ms
                    else:
                        results['errors'] += 1
                    
                    # Log progress every LOG_REQUESTS_INTERVAL requests
                    if results['requests'] % LOG_REQUESTS_INTERVAL == 0:
                        elapsed = time.time() - step_start
                        success_rate = results['successful'] / results['requests'] if results['requests'] > 0 else 0
                        logger.info(f"Ramp step progress: {results['requests']} requests completed in {elapsed:.1f}s (concurrency: {concurrency}, success rate: {success_rate:.2%})")
                
            except Exception as e:
                logger.warning(f"Worker {worker_id} error: {e}")
                
                # Create error record
                error_record = BenchmarkRecord(
                    thread_id=worker_id,
                    conn_id=worker_id,
                    object_key=self.object_key,
                    range_start=0,
                    range_len=0,
                    bytes_downloaded=0,
                    latency_ms=0,
                    http_status=500,
                    concurrency=concurrency
                )
                
                with self.records_lock:
                    self.persistence.store_record(error_record)
                    results['errors'] += 1
                    
                    # Log progress every LOG_REQUESTS_INTERVAL requests (including errors)
                    if results['requests'] % LOG_REQUESTS_INTERVAL == 0:
                        elapsed = time.time() - step_start
                        success_rate = results['successful'] / results['requests'] if results['requests'] > 0 else 0
                        logger.info(f"Ramp step progress: {results['requests']} requests completed in {elapsed:.1f}s (concurrency: {concurrency}, success rate: {success_rate:.2%})")
                
                time.sleep(1)
    
    def find_optimal_concurrency(self, max_concurrency: int = 100):
        """Find optimal concurrency by ramping up until plateau is reached."""
        current_concurrency = self.initial_concurrency
        best_throughput = 0
        best_concurrency = current_concurrency
        step_results = []
        consecutive_high_error_steps = 0
        
        logger.info(f"Starting concurrency optimization: {current_concurrency} -> {max_concurrency}")
        
        while current_concurrency <= max_concurrency:
            logger.info(f"Executing step at {current_concurrency} connections...")
            # Execute step
            step_result = self.execute_step(current_concurrency)
            step_results.append(step_result)
            
            # Check error rate
            total_requests = step_result['requests']
            total_errors = step_result['errors']
            error_rate = total_errors / total_requests if total_requests > 0 else 0
            
            logger.info(f"Step completed: {step_result['throughput_mbps']:.1f} Mbps, "
                       f"{total_requests} requests, {total_errors} errors ({error_rate:.1%} error rate)")
            
            # Check for high error rate
            if total_requests >= MIN_REQUESTS_FOR_ERROR_CHECK and error_rate > MAX_ERROR_RATE:
                consecutive_high_error_steps += 1
                logger.warning(f"High error rate detected: {error_rate:.1%} (step {consecutive_high_error_steps})")
                
                if consecutive_high_error_steps >= 2:  # Allow 2 consecutive high-error steps
                    logger.error(f"Terminating due to high error rate: {error_rate:.1%} for {consecutive_high_error_steps} consecutive steps")
                    logger.error(f"Stopping at {current_concurrency} connections due to excessive errors")
                    break
            else:
                consecutive_high_error_steps = 0  # Reset counter on successful step
            
            throughput = step_result['throughput_mbps']
            duration = step_result['duration']
            
            # Add measurement to plateau checker
            self.plateau_checker.add_measurement(current_concurrency, throughput, duration)
            
            # Check if we found better throughput
            if throughput > best_throughput:
                best_throughput = throughput
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
