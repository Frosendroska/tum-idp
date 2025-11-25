"""
Concurrent warm-up algorithm for the R2 benchmark with sophisticated architecture.
"""

import asyncio
import time
import logging
from typing import Dict, Any
from configuration import (
    DEFAULT_OBJECT_KEY,
    INITIAL_CONCURRENCY,
    SECONDS_PER_MINUTE,
    PROGRESS_INTERVAL,
)

logger = logging.getLogger(__name__)


class WarmUp:
    """Concurrent warm-up to stabilize connections using shared worker pool."""

    def __init__(
        self,
        worker_pool,
        warm_up_minutes,
        concurrency: int = None,
        object_key: str = None,
        system_bandwidth_mbps: float = None,
    ):
        self.worker_pool = worker_pool
        self.warm_up_minutes = warm_up_minutes
        self.concurrency = concurrency or INITIAL_CONCURRENCY
        self.object_key = object_key or DEFAULT_OBJECT_KEY
        self.system_bandwidth_mbps = system_bandwidth_mbps

        logger.info(
            f"Initialized warm-up: {warm_up_minutes} minutes, {self.concurrency} connections"
        )

    async def execute(self) -> Dict[str, Any]:
        """Execute the warm-up phase using shared worker pool."""
        logger.info(f"Starting warm-up phase with {self.concurrency} connections...")

        # Start workers for warm-up and begin phase
        await self.worker_pool.start_workers(self.concurrency, self.object_key, "warmup")

        # Wait for warm-up duration
        warm_up_duration = self.warm_up_minutes * SECONDS_PER_MINUTE
        start_time = time.time()
        end_time = start_time + warm_up_duration

        # Wait for the warm-up duration
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
