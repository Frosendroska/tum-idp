"""
Steady state algorithm for hybrid multiprocessing + async architecture.
"""

import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)


class SteadyState:
    """Steady state performance measurement across all processes."""

    def __init__(
        self,
        process_pool,
        duration_hours: int,
        workers_per_core: int,
        object_key: str,
        system_bandwidth_gbps: float
    ):
        self.process_pool = process_pool
        self.duration_hours = duration_hours
        self.workers_per_core = workers_per_core
        self.object_key = object_key
        self.system_bandwidth_gbps = system_bandwidth_gbps

    async def execute(self) -> Dict[str, Any]:
        """Execute steady state phase."""
        duration_seconds = self.duration_hours * 3600
        phase_id = "steady_state"

        logger.info(f"Starting steady state: {self.workers_per_core} workers/core for {duration_seconds}s")

        # Execute phase across all processes
        stats = await self.process_pool.execute_phase(
            workers_per_core=self.workers_per_core,
            phase_id=phase_id,
            duration_seconds=duration_seconds
        )

        logger.info(
            f"Steady state complete: {stats['throughput_gbps']:.2f} Gbps, "
            f"{stats['successful_requests']}/{stats['total_requests']} requests"
        )

        return stats
