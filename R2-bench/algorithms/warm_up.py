"""
Warm-up phase for hybrid multiprocessing + async architecture.
"""

import time
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)


class WarmUp:
    """Warm-up phase to stabilize connections across all processes."""

    def __init__(
        self,
        process_pool,
        warm_up_minutes: int,
        workers_per_core: int,
        object_key: str,
        system_bandwidth_gbps: float,
    ):
        self.process_pool = process_pool
        self.warm_up_minutes = warm_up_minutes
        self.workers_per_core = workers_per_core
        self.object_key = object_key
        self.system_bandwidth_gbps = system_bandwidth_gbps

    async def execute(self) -> Dict[str, Any]:
        """Execute warm-up phase."""
        duration_seconds = self.warm_up_minutes * 60
        phase_id = "warmup"

        logger.info(f"Starting warm-up: {self.workers_per_core} workers/core for {duration_seconds}s")

        # Execute phase across all processes
        stats = await self.process_pool.execute_phase(
            workers_per_core=self.workers_per_core,
            phase_id=phase_id,
            duration_seconds=duration_seconds
        )

        logger.info(
            f"Warm-up complete: {stats['throughput_gbps']:.2f} Gbps, "
            f"{stats['successful_requests']}/{stats['total_requests']} requests"
        )

        return stats
