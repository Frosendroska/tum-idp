"""
Concurrent warm-up algorithm for the R2 benchmark.
"""

import time
import logging
import threading
from persistence.base import BenchmarkRecord
from configuration import RANGE_SIZE_MB, DEFAULT_OBJECT_KEY, INITIAL_CONCURRENCY, ERROR_RETRY_DELAY, BYTES_PER_MB, BYTES_PER_GB, MAX_ERROR_RATE, MAX_CONSECUTIVE_ERRORS


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
        
        # Progress monitoring
        progress_thread = threading.Thread(target=self._progress_monitor, args=(results, start_time, warm_up_seconds))
        progress_thread.daemon = True
        progress_thread.start()
        
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
                if request_count % 5 == 0:  # Log every 5 requests per worker for better visibility
                    elapsed = time.time() - start_time
                    remaining = duration_seconds - elapsed
                    logger.debug(f"Worker {worker_id}: {request_count} requests in {elapsed:.1f}s (remaining: {remaining:.1f}s)")
                
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
                        logger.warning(f"Worker {worker_id}: Empty data received for request {request_count}")
                
                # Check for too many consecutive errors
                if consecutive_errors >= MAX_CONSECUTIVE_ERRORS:
                    logger.error(f"Worker {worker_id} stopping due to {consecutive_errors} consecutive errors")
                    break
                
            except Exception as e:
                logger.warning(f"Worker {worker_id} error during warm-up (request {request_count}): {e}")
                consecutive_errors += 1
                with self.lock:
                    results['errors'] += 1
                
                # Check for too many consecutive errors
                if consecutive_errors >= MAX_CONSECUTIVE_ERRORS:
                    logger.error(f"Worker {worker_id} stopping due to {consecutive_errors} consecutive errors")
                    break
                    
                # Exponential backoff for retries
                retry_delay = min(ERROR_RETRY_DELAY * (2 ** min(consecutive_errors, 5)), 30)
                logger.debug(f"Worker {worker_id}: Retrying in {retry_delay}s after error")
                time.sleep(retry_delay)
    
    def _progress_monitor(self, results, start_time, duration_seconds):
        """Monitor progress during warm-up and log status updates."""
        last_report_time = start_time
        
        while time.time() - start_time < duration_seconds:
            time.sleep(10)  # Report every 10 seconds
            current_time = time.time()
            elapsed = current_time - start_time
            remaining = duration_seconds - elapsed
            
            with self.lock:
                requests = results['requests']
                successful = results['successful']
                errors = results['errors']
                bytes_downloaded = results['bytes']
            
            if requests > 0:
                success_rate = successful / requests
                throughput_mbps = (bytes_downloaded * 8) / (elapsed * 1_000_000) if elapsed > 0 else 0
                logger.info(f"Warm-up progress: {elapsed:.1f}s elapsed, {remaining:.1f}s remaining, "
                          f"{requests} requests ({successful} successful, {errors} errors), "
                          f"{success_rate:.1%} success rate, {throughput_mbps:.1f} Mbps")
            else:
                logger.info(f"Warm-up progress: {elapsed:.1f}s elapsed, {remaining:.1f}s remaining, no requests yet")
