"""
Concurrent warm-up algorithm for the R2 benchmark.
"""

import time
import logging
import threading
from persistence.base import BenchmarkRecord
from configuration import RANGE_SIZE_MB, DEFAULT_OBJECT_KEY, INITIAL_CONCURRENCY, ERROR_RETRY_DELAY, BYTES_PER_MB, BYTES_PER_GB, MAX_ERROR_RATE, MAX_CONSECUTIVE_ERRORS, LOG_REQUESTS_INTERVAL


logger = logging.getLogger(__name__)


class WarmUp:
    """Concurrent warm-up to stabilize connections."""
    
    def __init__(self, storage_system, warm_up_minutes: int = 5, concurrency: int = None, object_key: str = None):
        self.storage_system = storage_system
        self.warm_up_minutes = warm_up_minutes
        self.concurrency = concurrency or INITIAL_CONCURRENCY
        self.object_key = object_key or DEFAULT_OBJECT_KEY
        self.range_size_mb = RANGE_SIZE_MB
        self.lock = threading.Lock()  # Create shared lock for thread safety
        
        logger.info(f"Initialized concurrent warm-up: {warm_up_minutes} minutes, {self.concurrency} connections")
    
    def execute(self):
        """Execute the concurrent warm-up phase."""
        logger.info(f"Starting concurrent warm-up phase with {self.concurrency} connections...")
        
        start_time = time.time()
        warm_up_seconds = self.warm_up_minutes * 60
        
        # Initialize shared metrics
        results = {
            'requests': 0,
            'successful': 0,
            'bytes': 0,
            'latency': 0,
            'errors': 0
        }
        
        # Create worker threads
        threads = []
        for i in range(self.concurrency):
            thread = threading.Thread(
                target=self._worker_function,
                args=(i, results, start_time, warm_up_seconds)
            )
            thread.start()
            threads.append(thread)
        
        # Wait for all threads to complete with progress reporting
        logger.info(f"Warm-up running for {self.warm_up_minutes} minutes...")
        for thread in threads:
            thread.join()
        
        # Calculate results
        warm_up_duration = time.time() - start_time
        avg_latency = results['latency'] / results['successful'] if results['successful'] > 0 else 0
        success_rate = results['successful'] / results['requests'] if results['requests'] > 0 else 0
        error_rate = results['errors'] / results['requests'] if results['requests'] > 0 else 0
        
        # Check for high error rate
        if error_rate > MAX_ERROR_RATE:
            logger.warning(f"High error rate during warm-up: {error_rate:.1%} ({results['errors']}/{results['requests']} errors)")
        
        final_results = {
            'warm_up_duration_minutes': warm_up_duration / 60,
            'concurrency': self.concurrency,
            'total_requests': results['requests'],
            'successful_requests': results['successful'],
            'success_rate': success_rate,
            'total_bytes_downloaded': results['bytes'],
            'avg_latency_ms': avg_latency,
            'errors': results['errors']
        }
        
        logger.info(f"Concurrent warm-up completed: {results['requests']} requests, {success_rate:.2%} success rate")
        return final_results
    
    def _worker_function(self, worker_id, results, start_time, duration_seconds):
        """Worker thread function for concurrent warm-up."""
        request_count = 0
        consecutive_errors = 0
        
        while time.time() - start_time < duration_seconds:
            try:
                # Calculate range for this worker
                range_start = (worker_id * self.range_size_mb * BYTES_PER_MB) % BYTES_PER_GB
                range_length = self.range_size_mb * BYTES_PER_MB
                
                # Download range
                data, latency_ms = self.storage_system.download_range(
                    self.object_key, range_start, range_length
                )
                
                request_count += 1
                
                # Update results (thread-safe)
                with self.lock:
                    results['requests'] += 1
                    if data and len(data) > 0:
                        results['successful'] += 1
                        results['bytes'] += len(data)
                        results['latency'] += latency_ms
                        consecutive_errors = 0  # Reset error counter on success
                    else:
                        results['errors'] += 1
                        consecutive_errors += 1
                    
                    # Log progress every LOG_REQUESTS_INTERVAL requests
                    if results['requests'] % LOG_REQUESTS_INTERVAL == 0:
                        elapsed = time.time() - start_time
                        success_rate = results['successful'] / results['requests'] if results['requests'] > 0 else 0
                        logger.info(f"Warm-up progress: {results['requests']} requests completed in {elapsed:.1f}s (success rate: {success_rate:.2%})")
                
                # Check for too many consecutive errors
                if consecutive_errors >= MAX_CONSECUTIVE_ERRORS:
                    logger.error(f"Worker {worker_id} stopping due to {consecutive_errors} consecutive errors")
                    break
                
            except Exception as e:
                logger.warning(f"Worker {worker_id} error during warm-up: {e}")
                consecutive_errors += 1
                with self.lock:
                    results['errors'] += 1
                
                # Check for too many consecutive errors
                if consecutive_errors >= MAX_CONSECUTIVE_ERRORS:
                    logger.error(f"Worker {worker_id} stopping due to {consecutive_errors} consecutive errors")
                    break
                    
                time.sleep(ERROR_RETRY_DELAY)
