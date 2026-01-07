"""
Sophisticated ramp-up algorithm for finding optimal concurrency with advanced architecture.
"""

import asyncio
import time
import logging
from typing import Dict, Any
from configuration import (
    MAX_ERROR_RATE,
    MIN_REQUESTS_FOR_ERROR_CHECK,
    PROGRESS_INTERVAL,
)
from algorithms.plateau_check import PlateauCheck
from common.worker_pool import WorkerPool

logger = logging.getLogger(__name__)


class Ramp:
    """Sophisticated algorithm to find optimal concurrency using shared worker pool."""

    def __init__(
        self,
        worker_pool: WorkerPool,
        initial_concurrency: int,
        ramp_step: int,
        step_duration_seconds: int,
        object_key: str,
        plateau_threshold: float,
        system_bandwidth_gbps: float,
    ):
        self.worker_pool = worker_pool
        self.initial_concurrency = initial_concurrency
        self.ramp_step = ramp_step
        self.step_duration_seconds = step_duration_seconds
        self.object_key = object_key
        self.system_bandwidth_gbps = system_bandwidth_gbps

        # Initialize plateau checker
        self.plateau_checker = PlateauCheck(
            threshold=plateau_threshold,
            system_bandwidth_gbps=system_bandwidth_gbps,
        )

        logger.info(
            f"Initialized ramp with plateau detection: {initial_concurrency} -> ?, step {self.ramp_step} every {self.step_duration_seconds}s, system limit: {self.system_bandwidth_gbps} Gbps"
        )

    async def execute_step(self, concurrency: int, step_id: str) -> Dict[str, Any]:
        """Execute one ramp step at the given concurrency level."""
        logger.info(
            f"Starting ramp step: {concurrency} connections for {self.step_duration_seconds} seconds"
        )

        # Adjust worker pool to target concurrency and begin ramp step
        await self.worker_pool.start_workers(concurrency, self.object_key, step_id)

        start_time = time.time()
        end_time = start_time + self.step_duration_seconds

        # Wait for the step duration with progress logging and diagnostics
        last_log_time = start_time
        while time.time() < end_time:
            current_time = time.time()
            elapsed = current_time - start_time
            remaining = end_time - current_time

            # Log progress every 30 seconds with diagnostics
            if (current_time - last_log_time) >= 30:
                # Get current record count from persistence
                if hasattr(self.worker_pool, 'persistence'):
                    current_records = len(self.worker_pool.persistence.records)

                    # Check if processes are alive (for ProcessPool)
                    if hasattr(self.worker_pool, 'processes'):
                        alive_processes = sum(1 for p in self.worker_pool.processes if p.is_alive())
                        logger.info(
                            f"Step progress: {elapsed:.0f}s elapsed, {remaining:.0f}s remaining "
                            f"({current_records} records, {alive_processes}/{len(self.worker_pool.processes)} processes alive)"
                        )
                    else:
                        logger.info(
                            f"Step progress: {elapsed:.0f}s elapsed, {remaining:.0f}s remaining "
                            f"({current_records} records collected so far)"
                        )
                else:
                    logger.info(
                        f"Step progress: {elapsed:.0f}s elapsed, {remaining:.0f}s remaining"
                    )
                last_log_time = current_time

            await asyncio.sleep(1)

        # Get step statistics
        step_stats = self.worker_pool.get_step_stats(step_id)

        if step_stats:
            logger.info(
                f"Ramp step completed: {step_stats['throughput_gbps']:.2f} Gbps, "
                f"{step_stats['successful_requests']}/{step_stats['total_requests']} requests"
            )
        else:
            logger.warning(f"No step statistics available for ramp step {step_id}")
            step_stats = {
                "phase_id": step_id,
                "concurrency": concurrency,
                "throughput_gbps": 0.0,
                "total_requests": 0,
                "successful_requests": 0,
                "error_requests": 0,
                "error_rate": 1.0,
                "duration_seconds": self.step_duration_seconds,
                "avg_latency_ms": 0.0,
                "p50_latency_ms": 0.0,
                "p95_latency_ms": 0.0,
                "p99_latency_ms": 0.0,
                "total_bytes": 0,
            }

        return step_stats

    async def find_optimal_concurrency(self, max_concurrency: int):
        """Find optimal concurrency by ramping up until plateau is reached."""
        current_concurrency = self.initial_concurrency
        best_throughput = 0
        best_concurrency = current_concurrency
        step_results = []
        step_count = 0

        logger.info(
            f"Starting sophisticated concurrency optimization: {current_concurrency} -> {max_concurrency}"
        )

        try:
            while current_concurrency <= max_concurrency:
                step_count += 1
                phase_id = f"ramp_{step_count}"

                logger.info(
                    f"Executing ramp step {step_count} at {current_concurrency} connections..."
                )

                # Execute step using sophisticated architecture
                step_result = await self.execute_step(current_concurrency, phase_id)
                step_results.append(step_result)

                # Check error rate
                total_requests = step_result["total_requests"]
                error_rate = step_result["error_rate"]

                logger.info(
                    f"Step completed: {step_result['throughput_gbps']:.2f} Gbps, "
                    f"{total_requests} requests, error rate: {error_rate:.1%}"
                )

                # Check for high error rate
                if (
                    total_requests >= MIN_REQUESTS_FOR_ERROR_CHECK
                    and error_rate > MAX_ERROR_RATE
                ):
                    logger.warning(f"High error rate detected: {error_rate:.1%}")
                    break

                # Add measurement to plateau checker
                self.plateau_checker.add_measurement(
                    current_concurrency,
                    step_result["throughput_gbps"],
                    step_result["duration_seconds"],
                )

                # Check if we found better throughput
                if step_result["throughput_gbps"] > best_throughput:
                    best_throughput = step_result["throughput_gbps"]
                    best_concurrency = current_concurrency
                    logger.info(
                        f"✓ New best: {best_concurrency} workers → {best_throughput:.2f} Gbps"
                    )

                # Check for plateau using plateau detection algorithm
                plateau_reached, reason = self.plateau_checker.is_plateau_reached()

                # Log plateau check result
                if plateau_reached:
                    logger.info("=" * 70)
                    logger.info("🛑 PLATEAU DETECTED - STOPPING RAMP")
                    logger.info(f"   Reason: {reason}")
                    logger.info(f"   Final concurrency: {current_concurrency} workers")
                    logger.info(f"   Final throughput: {step_result['throughput_gbps']:.2f} Gbps")
                    logger.info(f"   Best achieved: {best_throughput:.2f} Gbps at {best_concurrency} workers")
                    logger.info("=" * 70)
                    break
                else:
                    logger.info(f"   Plateau check: {reason}")
                    logger.debug(
                        f"   Continuing ramp: next step will test {current_concurrency + self.ramp_step} workers"
                    )

                # Increase concurrency
                current_concurrency += self.ramp_step

            # Get plateau summary
            plateau_summary = self.plateau_checker.get_plateau_summary()

            return {
                "best_concurrency": best_concurrency,
                "best_throughput_gbps": best_throughput,
                "step_results": step_results,
                "plateau_detected": (
                    plateau_reached if "plateau_reached" in locals() else False
                ),
                "plateau_reason": (
                    reason if "reason" in locals() else "Max concurrency reached"
                ),
                "plateau_summary": plateau_summary,
            }

        except Exception as e:
            logger.error(f"Error during ramp optimization: {e}")
            raise
