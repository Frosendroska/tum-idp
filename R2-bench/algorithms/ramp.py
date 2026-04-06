"""
Ramp-up algorithm for finding optimal concurrency with hybrid multiprocessing + async.
"""

import logging
from typing import Any, Dict

from configuration import MAX_ERROR_RATE, MIN_REQUESTS_FOR_ERROR_CHECK
from algorithms.plateau_check import PlateauCheck, PLATEAU_STOP_DEGRADATION

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

        self.plateau_checker = PlateauCheck(
            threshold=plateau_threshold,
            system_bandwidth_gbps=system_bandwidth_gbps,
        )

    async def execute_step(self, workers_per_core: int, step_id: str) -> Dict[str, Any]:
        """Execute one ramp step at given workers per core."""
        stats = await self.process_pool.execute_phase(
            workers_per_core=workers_per_core,
            phase_id=step_id,
            duration_seconds=self.step_duration_seconds,
        )
        return stats

    async def find_optimal_concurrency(self, max_workers_per_core: int):
        """Find optimal workers per core by ramping until plateau."""
        current_workers_per_core = self.initial_workers_per_core
        best_throughput = 0.0
        best_workers_per_core = current_workers_per_core
        step_results = []
        step_count = 0

        plateau_reached = False
        reason = "Max workers per core reached"
        plateau_stop_kind = None
        reverted_to_peak_workers = False

        logger.info(
            f"Starting ramp: {current_workers_per_core} -> {max_workers_per_core} workers/core "
            f"({self.step_duration_seconds}s per step)"
        )

        try:
            while current_workers_per_core <= max_workers_per_core:
                step_count += 1
                phase_id = f"ramp_{step_count}"

                step_result = await self.execute_step(current_workers_per_core, phase_id)
                step_result["workers_per_core"] = current_workers_per_core
                step_results.append(step_result)

                total_requests = step_result["total_requests"]
                error_rate = step_result["error_rate"]

                logger.info(
                    f"Ramp step {step_count} ({phase_id}): {current_workers_per_core} workers/core → "
                    f"{step_result['throughput_gbps']:.2f} Gbps, "
                    f"{step_result['successful_requests']}/{total_requests} ok, "
                    f"errors {error_rate:.1%}"
                )

                if (
                    total_requests >= MIN_REQUESTS_FOR_ERROR_CHECK
                    and error_rate > MAX_ERROR_RATE
                ):
                    logger.warning(f"High error rate detected: {error_rate:.1%}, stopping ramp")
                    break

                self.plateau_checker.add_measurement(
                    current_workers_per_core,
                    step_result["throughput_gbps"],
                    step_result["duration_seconds"],
                )

                if step_result["throughput_gbps"] > best_throughput:
                    best_throughput = step_result["throughput_gbps"]
                    best_workers_per_core = current_workers_per_core
                    logger.info(
                        f"✓ New best throughput: {best_throughput:.2f} Gbps at "
                        f"{best_workers_per_core} workers/core"
                    )

                plateau_reached, reason, plateau_stop_kind = self.plateau_checker.is_plateau_reached()

                if plateau_reached:
                    logger.info("=" * 70)
                    logger.info("PLATEAU DETECTED — stopping ramp")
                    logger.info(f"   Reason: {reason}")
                    logger.info(f"   Last ramp workers/core: {current_workers_per_core}")
                    logger.info(f"   Last step throughput: {step_result['throughput_gbps']:.2f} Gbps")
                    logger.info(
                        f"   Best throughput: {best_throughput:.2f} Gbps at "
                        f"{best_workers_per_core} workers/core"
                    )

                    if plateau_stop_kind == PLATEAU_STOP_DEGRADATION:
                        if best_workers_per_core != current_workers_per_core:
                            logger.info(
                                f"   Reverting load to peak-throughput level: "
                                f"{best_workers_per_core} workers/core (phase revert_to_peak)"
                            )
                            await self.process_pool.start_workers(
                                best_workers_per_core,
                                self.object_key,
                                "revert_to_peak",
                            )
                            reverted_to_peak_workers = True
                        else:
                            logger.info(
                                "   Already at best workers/core; no revert needed."
                            )

                    logger.info("=" * 70)
                    break

                logger.info(f"   Plateau check: {reason}")

                current_workers_per_core += self.ramp_step_workers_per_core

            plateau_summary = self.plateau_checker.get_plateau_summary()

            return {
                "best_workers_per_core": best_workers_per_core,
                "best_throughput_gbps": best_throughput,
                "step_results": step_results,
                "plateau_detected": plateau_reached,
                "plateau_reason": reason,
                "plateau_stop_kind": plateau_stop_kind,
                "plateau_summary": plateau_summary,
                "reverted_to_peak_workers": reverted_to_peak_workers,
            }

        except Exception as e:
            logger.error(f"Error during ramp optimization: {e}", exc_info=True)
            raise
