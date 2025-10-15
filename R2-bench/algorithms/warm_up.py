"""
Concurrent warm-up algorithm for the R2 benchmark with sophisticated architecture.
"""

import time
import logging
from typing import Dict, Any
from common import PhaseManager
from configuration import (
    DEFAULT_OBJECT_KEY, INITIAL_CONCURRENCY
)

logger = logging.getLogger(__name__)


class WarmUp:
    """Concurrent warm-up to stabilize connections using shared worker pool."""
    
    def __init__(self, worker_pool, warm_up_minutes: int = 5, concurrency: int = None, 
                 object_key: str = None, system_bandwidth_mbps: float = None):
        self.worker_pool = worker_pool
        self.warm_up_minutes = warm_up_minutes
        self.concurrency = concurrency or INITIAL_CONCURRENCY
        self.object_key = object_key or DEFAULT_OBJECT_KEY
        self.system_bandwidth_mbps = system_bandwidth_mbps
        
        logger.info(f"Initialized warm-up: {warm_up_minutes} minutes, {self.concurrency} connections")
    

    def execute(self):
        """Execute the warm-up phase using shared worker pool."""
        logger.info(f"Starting warm-up phase with {self.concurrency} connections...")
        
        try:
            # Start workers for warm-up using shared pool
            self.worker_pool.start_workers(self.concurrency, self.object_key)
            
            # Begin warm-up phase
            self.worker_pool.begin_phase("warmup", self.concurrency)
            
            # Give workers a moment to start making requests
            time.sleep(2)
            
            # Set step start time
            self.worker_pool.set_phase_step_time("warmup", time.time())
            
            # Wait for warm-up duration
            warm_up_duration = self.warm_up_minutes * 60
            start_time = time.time()
            end_time = start_time + warm_up_duration
            
            while time.time() < end_time:
                time.sleep(0.1)
            
            # Get step statistics
            step_stats = self.worker_pool.get_step_stats("warmup")
            
            if step_stats:
                logger.info(
                    f"Warm-up completed: {step_stats['throughput_mbps']:.1f} Mbps, "
                    f"{step_stats['successful_requests']}/{step_stats['total_requests']} requests"
                )
            else:
                logger.warning("No step statistics available for warm-up phase")
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
