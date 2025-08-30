"""
Simple warm-up algorithm for the R2 benchmark.
"""

import time
import logging
from ..persistence.base import BenchmarkRecord

logger = logging.getLogger(__name__)


class SimpleWarmUp:
    """Simple warm-up to stabilize connections."""
    
    def __init__(self, storage_system, warm_up_minutes: int = 5):
        self.storage_system = storage_system
        self.warm_up_minutes = warm_up_minutes
        self.object_key = "test-object-1gb"
        self.range_size_mb = 100
        
        logger.info(f"Initialized warm-up: {warm_up_minutes} minutes")
    
    def execute(self):
        """Execute the warm-up phase."""
        logger.info("Starting warm-up phase...")
        
        start_time = time.time()
        warm_up_seconds = self.warm_up_minutes * 60
        
        # Initialize metrics
        total_requests = 0
        successful_requests = 0
        total_bytes = 0
        total_latency = 0
        
        # Simple warm-up loop
        while time.time() - start_time < warm_up_seconds:
            try:
                # Make a few requests to warm up connections
                for i in range(5):
                    range_start = (i * self.range_size_mb * 1024 * 1024) % (1024 * 1024 * 1024)
                    range_length = self.range_size_mb * 1024 * 1024
                    
                    data, latency_ms = self.storage_system.download_range(
                        self.object_key, range_start, range_length
                    )
                    
                    total_requests += 1
                    if data and len(data) > 0:
                        successful_requests += 1
                        total_bytes += len(data)
                        total_latency += latency_ms
                
                time.sleep(1)
                
            except Exception as e:
                logger.error(f"Error during warm-up: {e}")
                time.sleep(5)
        
        # Calculate results
        warm_up_duration = time.time() - start_time
        avg_latency = total_latency / successful_requests if successful_requests > 0 else 0
        success_rate = successful_requests / total_requests if total_requests > 0 else 0
        
        results = {
            'warm_up_duration_minutes': warm_up_duration / 60,
            'total_requests': total_requests,
            'successful_requests': successful_requests,
            'success_rate': success_rate,
            'total_bytes_downloaded': total_bytes,
            'avg_latency_ms': avg_latency
        }
        
        logger.info(f"Warm-up completed: {total_requests} requests, {success_rate:.2%} success rate")
        return results
