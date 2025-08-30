"""
Simple ramp-up algorithm for finding optimal concurrency.
"""

import time
import logging
import threading
from persistence.base import BenchmarkRecord

logger = logging.getLogger(__name__)


class SimpleRamp:
    """Simple algorithm to find optimal concurrency."""
    
    def __init__(self, storage_system, initial_concurrency: int = 8, 
                 ramp_step: int = 8, step_duration_minutes: int = 5):
        self.storage_system = storage_system
        self.initial_concurrency = initial_concurrency
        self.ramp_step = ramp_step
        self.step_duration_minutes = step_duration_minutes
        self.object_key = "test-object-1gb"
        self.range_size_mb = 100
        
        logger.info(f"Initialized ramp: {initial_concurrency} -> ?, step {ramp_step}")
    
    def execute_step(self, concurrency: int):
        """Execute one ramp step at the given concurrency level."""
        step_duration = self.step_duration_minutes * 60
        step_start = time.time()
        
        logger.info(f"Starting ramp step: {concurrency} connections for {self.step_duration_minutes} minutes")
        
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
                args=(i, results, step_start, step_duration)
            )
            thread.start()
            threads.append(thread)
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # Calculate throughput
        step_duration_actual = time.time() - step_start
        if results['successful'] > 0:
            throughput_mbps = (results['bytes'] * 8) / (step_duration_actual * 1_000_000)
        else:
            throughput_mbps = 0
        
        results['throughput_mbps'] = throughput_mbps
        results['duration'] = step_duration_actual
        
        logger.info(f"Ramp step completed: {concurrency} conn, {throughput_mbps:.1f} Mbps")
        return results
    
    def _worker_function(self, worker_id, results, step_start, step_duration):
        """Worker thread function."""
        while time.time() - step_start < step_duration:
            try:
                # Calculate range for this worker
                range_start = (worker_id * self.range_size_mb * 1024 * 1024) % (1024 * 1024 * 1024)
                range_length = self.range_size_mb * 1024 * 1024
                
                # Download range
                data, latency_ms = self.storage_system.download_range(
                    self.object_key, range_start, range_length
                )
                
                # Update results (thread-safe)
                with threading.Lock():
                    results['requests'] += 1
                    if data and len(data) > 0:
                        results['successful'] += 1
                        results['bytes'] += len(data)
                        results['latency'] += latency_ms
                    else:
                        results['errors'] += 1
                
                time.sleep(0.1)  # Small delay
                
            except Exception as e:
                logger.warning(f"Worker {worker_id} error: {e}")
                with threading.Lock():
                    results['errors'] += 1
                time.sleep(1)
    
    def find_optimal_concurrency(self, max_concurrency: int = 100):
        """Find optimal concurrency by ramping up."""
        current_concurrency = self.initial_concurrency
        best_throughput = 0
        best_concurrency = current_concurrency
        step_results = []
        
        while current_concurrency <= max_concurrency:
            # Execute step
            step_result = self.execute_step(current_concurrency)
            step_results.append(step_result)
            
            throughput = step_result['throughput_mbps']
            
            # Check if we found better throughput
            if throughput > best_throughput:
                best_throughput = throughput
                best_concurrency = current_concurrency
                logger.info(f"New best: {best_concurrency} conn, {best_throughput:.1f} Mbps")
            
            # Check if throughput is declining
            if len(step_results) > 1:
                prev_throughput = step_results[-2]['throughput_mbps']
                if throughput < prev_throughput * 0.9:  # 10% decline
                    logger.info(f"Throughput declining, stopping at {current_concurrency}")
                    break
            
            # Increase concurrency
            current_concurrency += self.ramp_step
            time.sleep(5)  # Small delay between steps
        
        return {
            'best_concurrency': best_concurrency,
            'best_throughput_mbps': best_throughput,
            'step_results': step_results
        }
