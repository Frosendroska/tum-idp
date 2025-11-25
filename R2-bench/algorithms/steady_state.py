"""
Steady state algorithm for long-term benchmarking with worker pool and phase manager.
"""

import asyncio
import time
import logging
from typing import Dict, Any, Optional
from configuration import (
    DEFAULT_OBJECT_KEY, 
    SECONDS_PER_HOUR,
    PROGRESS_INTERVAL,
)

logger = logging.getLogger(__name__)


class SteadyState:
    """Steady state performance measurement using shared worker pool."""
    
    def __init__(
        self, 
        worker_pool,
        duration_hours, 
        concurrency: int = 10,
        object_key: str = None,
        system_bandwidth_mbps: float = None
    ):
        self.worker_pool = worker_pool
        self.duration_hours = duration_hours
        self.concurrency = concurrency
        self.object_key = object_key or DEFAULT_OBJECT_KEY
        self.system_bandwidth_mbps = system_bandwidth_mbps
        
        logger.info(f"Initialized steady state: {concurrency} conn for {duration_hours}h")
    
    async def execute(self) -> Dict[str, Any]:
        """Execute the steady state phase using shared worker pool."""
        logger.info(f"Starting steady state: {self.concurrency} connections for {self.duration_hours} hours")
        
        # Start workers for steady state and begin phase
        await self.worker_pool.start_workers(self.concurrency, self.object_key, "steady_state")
        
        # Wait for steady state duration with periodic logging
        steady_duration = self.duration_hours * SECONDS_PER_HOUR
        start_time = time.time()
        end_time = start_time + steady_duration

        # Wait for the steady state duration
        while time.time() < end_time:
            current_time = time.time()
            elapsed = current_time - start_time
            remaining = end_time - current_time

            if int(elapsed) % PROGRESS_INTERVAL == 0 and int(elapsed) > 0:
                logger.info(
                    f"Step progress: {elapsed:.0f}s elapsed, {remaining:.0f}s remaining"
                )

            await asyncio.sleep(1)
        
        # Get step statistics
        step_stats = self.worker_pool.get_step_stats("steady_state")
        
        if step_stats:
            logger.info(
                f"Steady state completed: {step_stats['throughput_mbps']:.1f} Mbps, "
                f"{step_stats['successful_requests']}/{step_stats['total_requests']} requests"
            )
        else:
            logger.warning("No step statistics available for steady state phase")
            step_stats = {
                "phase_id": "steady_state",
                "concurrency": self.concurrency,
                "throughput_mbps": 0.0,
                "total_requests": 0,
                "successful_requests": 0,
                "error_requests": 0,
                "error_rate": 1.0,
                "duration_seconds": steady_duration,
                "avg_latency_ms": 0.0,
                "p50_latency_ms": 0.0,
                "p95_latency_ms": 0.0,
                "p99_latency_ms": 0.0,
                "total_bytes": 0,
            }
        
        return step_stats
