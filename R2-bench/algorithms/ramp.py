"""
Ramp-up algorithm for finding optimal concurrency with hybrid multiprocessing + async.
"""

import time
import logging
from typing import Dict, Any

from configuration import MAX_ERROR_RATE, MIN_REQUESTS_FOR_ERROR_CHECK
from algorithms.plateau_check import PlateauCheck

logger = logging.getLogger(__name__)


class Ramp:
    """Ramp-up algorithm to find optimal workers per core."""

    def __init__(
        self,
        process_pool,
        initial_workers_per_core: int,
        ramp_step_workers_per_core: int,
        step_duration_seconds: int,
        object_key: str,
        plateau_threshold: float,
        system_bandwidth_gbps: float,
    ):
        self.process_pool = process_pool
        self.initial_workers_per_core = initial_workers_per_core
        self.ramp_step_workers_per_core = ramp_step_workers_per_core
        self.step_duration_seconds = step_duration_seconds
        self.object_key = object_key
        self.system_bandwidth_gbps = system_bandwidth_gbps

        # Plateau detection
        self.plateau_checker = PlateauCheck(
            threshold=plateau_threshold,
            system_bandwidth_gbps=system_bandwidth_gbps,
        )

    async def execute_step(self, workers_per_core: int, step_id: str) -> Dict[str, Any]:
        """Execute one ramp step at given workers per core."""
        logger.info(f"Starting ramp step: {workers_per_core} workers/core for {self.step_duration_seconds}s")

        # Execute phase across all processes
        stats = await self.process_pool.execute_phase(
            workers_per_core=workers_per_core,
            phase_id=step_id,
            duration_seconds=self.step_duration_seconds
        )

        logger.info(
            f"Step completed: {stats['throughput_gbps']:.2f} Gbps, "
            f"{stats['successful_requests']}/{stats['total_requests']} requests"
        )

        return stats

    async def find_optimal_concurrency(self, max_workers_per_core: int):
        """Find optimal workers per core by ramping until plateau."""
        current_workers_per_core = self.initial_workers_per_core
        best_throughput = 0
        best_workers_per_core = current_workers_per_core
        step_results = []
        step_count = 0

        # Initialize plateau tracking variables (prevents NameError in exception handling)
        plateau_reached = False
        reason = "Max workers per core reached"

        logger.info(f"Starting ramp: {current_workers_per_core} -> {max_workers_per_core} workers/core")

        try:
            while current_workers_per_core <= max_workers_per_core:
                step_count += 1
                phase_id = f"ramp_{step_count}"

                logger.info(f"Executing ramp step {step_count} at {current_workers_per_core} workers/core")

                # Execute step
                step_result = await self.execute_step(current_workers_per_core, phase_id)
                # Add workers_per_core to result for reporting
                step_result['workers_per_core'] = current_workers_per_core
                step_results.append(step_result)

                # Check error rate
                total_requests = step_result["total_requests"]
                error_rate = step_result["error_rate"]

                logger.info(
                    f"Step {step_count}: {step_result['throughput_gbps']:.2f} Gbps, "
                    f"{total_requests} requests, error rate: {error_rate:.1%}"
                )

                # Stop on high error rate
                if (
                    total_requests >= MIN_REQUESTS_FOR_ERROR_CHECK
                    and error_rate > MAX_ERROR_RATE
                ):
                    logger.warning(f"High error rate detected: {error_rate:.1%}, stopping ramp")
                    break

                # Add measurement to plateau checker
                self.plateau_checker.add_measurement(
                    current_workers_per_core,
                    step_result["throughput_gbps"],
                    step_result["duration_seconds"],
                )

                # Update best
                if step_result["throughput_gbps"] > best_throughput:
                    best_throughput = step_result["throughput_gbps"]
                    best_workers_per_core = current_workers_per_core
                    logger.info(f"✓ New best: {best_workers_per_core} workers/core → {best_throughput:.2f} Gbps")

                # Check plateau
                plateau_reached, reason = self.plateau_checker.is_plateau_reached()

                if plateau_reached:
                    logger.info("=" * 70)
                    logger.info("🛑 PLATEAU DETECTED - STOPPING RAMP")
                    logger.info(f"   Reason: {reason}")
                    logger.info(f"   Final workers/core: {current_workers_per_core}")
                    logger.info(f"   Final throughput: {step_result['throughput_gbps']:.2f} Gbps")
                    logger.info(f"   Best: {best_throughput:.2f} Gbps at {best_workers_per_core} workers/core")
                    logger.info("=" * 70)
                    break
                else:
                    logger.info(f"   Plateau check: {reason}")

                # Increase workers per core
                current_workers_per_core += self.ramp_step_workers_per_core

            # Get plateau summary
            plateau_summary = self.plateau_checker.get_plateau_summary()

            return {
                "best_workers_per_core": best_workers_per_core,
                "best_throughput_gbps": best_throughput,
                "step_results": step_results,
                "plateau_detected": plateau_reached,
                "plateau_reason": reason,
                "plateau_summary": plateau_summary,
            }

        except Exception as e:
            logger.error(f"Error during ramp optimization: {e}", exc_info=True)
            raise
