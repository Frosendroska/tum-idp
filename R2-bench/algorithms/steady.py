"""
Simple steady-state algorithm for long-term benchmarking.
"""

import time
import logging
import threading
from persistence.base import BenchmarkRecord
from configuration import (
    RANGE_SIZE_MB, DEFAULT_OBJECT_KEY, ERROR_RETRY_DELAY,
    PROGRESS_REPORT_INTERVAL, PROGRESS_MONITOR_INTERVAL,
    MEGABITS_PER_MB, BYTES_PER_MB, BYTES_PER_GB, SECONDS_PER_HOUR, default=INITIAL_CONCURRENCY
)

logger = logging.getLogger(__name__)


class SteadyState:
    """Steady state performance measurement."""
    
    def __init__(self, storage_system, duration_hours: int = 3, object_key: str = None):
        self.storage_system = storage_system
        self.concurrency = INITIAL_CONCURRENCY
        self.duration_hours = duration_hours
        self.object_key = object_key or DEFAULT_OBJECT_KEY
        self.range_size_mb = RANGE_SIZE_MB
        
        # Execution state
        self.is_running = False
        self.start_time = None
        self.end_time = None
        self.stop_event = threading.Event()
        self.worker_threads = []
        self.lock = threading.Lock()  # Create shared lock for thread safety
        
        # Metrics
        self.total_requests = 0
        self.successful_requests = 0
        self.total_bytes = 0
        self.total_latency = 0
        self.errors = 0
        
        logger.info(f"Initialized steady state: {concurrency} conn for {duration_hours}h")
    
    def execute(self):
        """Execute the steady state phase."""
        if self.is_running:
            logger.warning("Steady state already running")
            return {}
        
        logger.info(f"Starting steady state: {self.concurrency} connections for {self.duration_hours} hours")
        
        self.is_running = True
        self.start_time = time.time()
        self.end_time = self.start_time + (self.duration_hours * SECONDS_PER_HOUR)
        self.stop_event.clear()
        
        try:
            # Start worker threads
            self._start_workers()
            
            # Monitor progress
            self._monitor_progress()
            
            # Wait for completion or stop
            while time.time() < self.end_time and not self.stop_event.is_set():
                time.sleep(1)
            
            # Stop workers
            self._stop_workers()
            
            # Calculate results
            results = self._calculate_results()
            
            logger.info("Steady state completed")
            return results
            
        except Exception as e:
            logger.error(f"Error during steady state: {e}")
            self._stop_workers()
            return {'error': str(e)}
        finally:
            self.is_running = False
    
    def _start_workers(self):
        """Start worker threads."""
        for i in range(self.concurrency):
            worker = threading.Thread(target=self._worker_function, args=(i,))
            worker.daemon = True
            worker.start()
            self.worker_threads.append(worker)
    
    def _worker_function(self, worker_id):
        """Worker thread function for executing requests."""
        logger.debug(f"Worker {worker_id} started")
        
        while not self.stop_event.is_set() and time.time() < self.end_time:
            try:
                # Calculate range for this request
                range_start = (worker_id * self.range_size_mb * BYTES_PER_MB) % BYTES_PER_GB
                range_length = self.range_size_mb * BYTES_PER_MB
                
                # Download range
                data, latency_ms = self.storage_system.download_range(
                    self.object_key, range_start, range_length
                )
                
                # Record metrics
                with self.lock:
                    self.total_requests += 1
                    if data and len(data) > 0:
                        self.successful_requests += 1
                        self.total_bytes += len(data)
                        self.total_latency += latency_ms
                    else:
                        self.errors += 1
                                
            except Exception as e:
                logger.warning(f"Worker {worker_id} error: {e}")
                with self.lock:
                    self.errors += 1
                time.sleep(ERROR_RETRY_DELAY)
        
        logger.debug(f"Worker {worker_id} finished")
    
    def _monitor_progress(self):
        """Monitor progress during execution."""
        logger.info("Starting progress monitoring")
        
        last_report_time = time.time()
        
        while time.time() < self.end_time and not self.stop_event.is_set():
            current_time = time.time()
            
            # Report progress every minute
            if current_time - last_report_time >= PROGRESS_REPORT_INTERVAL:
                self._report_progress()
                last_report_time = current_time
            
            # Sleep for a short interval
            time.sleep(PROGRESS_MONITOR_INTERVAL)
    
    def _report_progress(self):
        """Report current progress."""
        if not self.start_time:
            return
        
        elapsed = time.time() - self.start_time
        remaining = self.end_time - time.time()
        
        success_rate = self.successful_requests / self.total_requests if self.total_requests > 0 else 0
        avg_latency = self.total_latency / self.successful_requests if self.successful_requests > 0 else 0
        
        if elapsed > 0:
            throughput_mbps = (self.total_bytes * 8) / (elapsed * MEGABITS_PER_MB)
        else:
            throughput_mbps = 0
        
        logger.info(f"Progress: {elapsed/SECONDS_PER_HOUR:.1f}h elapsed, {remaining/SECONDS_PER_HOUR:.1f}h remaining")
        logger.info(f"Requests: {self.total_requests} total, {self.successful_requests} successful ({success_rate:.2%})")
        logger.info(f"Throughput: {throughput_mbps:.1f} Mbps, Avg Latency: {avg_latency:.1f} ms")
    
    def _stop_workers(self):
        """Stop all worker threads."""
        self.stop_event.set()
        
        for worker in self.worker_threads:
            worker.join()
        
        self.worker_threads.clear()
        self.is_running = False
    
    def _calculate_results(self):
        """Calculate final results from the steady state run."""
        if not self.start_time:
            return {}
        
        duration = time.time() - self.start_time
        success_rate = self.successful_requests / self.total_requests if self.total_requests > 0 else 0
        avg_latency = self.total_latency / self.successful_requests if self.successful_requests > 0 else 0
        
        if duration > 0:
            throughput_mbps = (self.total_bytes * 8) / (duration * MEGABITS_PER_MB)
            qps = self.total_requests / duration
        else:
            throughput_mbps = 0
            qps = 0
        
        results = {
            'status': 'completed',
            'duration_hours': duration / SECONDS_PER_HOUR,
            'total_requests': self.total_requests,
            'successful_requests': self.successful_requests,
            'success_rate': success_rate,
            'total_bytes_downloaded': self.total_bytes,
            'avg_throughput_mbps': throughput_mbps,
            'avg_latency_ms': avg_latency,
            'requests_per_second': qps,
            'errors': self.errors
        }
        
        return results
    
    def stop(self):
        """Stop the steady state execution."""
        if self.is_running:
            logger.info("Stopping steady state execution")
            self.stop_event.set()
            self.end_time = time.time()  # Force immediate stop
