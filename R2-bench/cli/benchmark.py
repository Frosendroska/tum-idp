"""
Phase 2: Long-term performance benchmark with precise concurrency control.
"""

import asyncio
import os
import sys
import logging
import argparse
import time
from typing import Dict, Any

# Required: Use uvloop for better performance
import uvloop
asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())

# Ensure project root is in path (for running as script)
# When run as module (python -m cli.benchmark), this is not needed
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from configuration import (
    WARM_UP_MINUTES,
    STEADY_STATE_HOURS,
    AWS_ACCESS_KEY_ID,
    AWS_SECRET_ACCESS_KEY,
    AWS_REGION,
    R2_ACCESS_KEY_ID,
    R2_SECRET_ACCESS_KEY,
    MAX_CONCURRENCY,
)
from systems.r2 import R2System
from systems.aws import AWSSystem
from algorithms.warm_up import WarmUp
from algorithms.ramp import Ramp
from algorithms.steady_state import SteadyState
from persistence.parquet import ParquetPersistence
from common.worker_pool import WorkerPool

# Set up logging (only if not already configured)
if not logging.root.handlers:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
    )
logger = logging.getLogger(__name__)


class BenchmarkRunner:
    """Benchmark runner for long-term performance measurement with precise concurrency control."""

    def __init__(
        self,
        storage_type: str = "r2",
        object_key: str = None,
        concurrency: int = None,
        system_bandwidth_gbps: float = None,
    ):
        self.storage_type = storage_type.lower()
        self.concurrency = concurrency
        self.object_key = object_key
        self.system_bandwidth_gbps = system_bandwidth_gbps
        self.storage_system = None
        self.persistence = None
        self.worker_pool = None

        # Initialize components
        self._initialize_components()

        logger.info(
            f"Initialized benchmark runner: {storage_type.upper()} with {self.concurrency} connections"
        )
        logger.info(f"Worker bandwidth limit: {self.system_bandwidth_gbps} Gbps")

    def _initialize_components(self):
        """Initialize required components."""
        try:
            # Initialize storage system
            if self.storage_type == "r2":
                credentials = {
                    "access_key_id": R2_ACCESS_KEY_ID,
                    "secret_access_key": R2_SECRET_ACCESS_KEY,
                    "region_name": "auto",
                }
                self.storage_system = R2System(credentials)

            elif self.storage_type == "s3":
                credentials = {
                    "access_key_id": AWS_ACCESS_KEY_ID,
                    "secret_access_key": AWS_SECRET_ACCESS_KEY,
                    "region_name": AWS_REGION,
                }
                self.storage_system = AWSSystem(credentials)

            else:
                raise ValueError(f"Unsupported storage type: {self.storage_type}")

            # Initialize persistence
            self.persistence = ParquetPersistence()

            # Initialize shared worker pool
            self.worker_pool = WorkerPool(self.storage_system, self.persistence, MAX_CONCURRENCY)

        except Exception as e:
            logger.error(f"Failed to initialize components: {e}")
            raise

    async def run_benchmark(self) -> Dict[str, Any]:
        """Execute the complete benchmark."""
        logger.info("Starting benchmark")
        logger.info(f"Using object key: {self.object_key}")

        # Use storage system as async context manager
        async with self.storage_system:
            try:
                # Check if object exists
                logger.info("Checking if test object exists...")
                response = await self.storage_system.client.head_object(
                    Bucket=self.storage_system.bucket_name, Key=self.object_key
                )
                logger.info(f"Test object found: {response['ContentLength']} bytes")
            except Exception as e:
                logger.warning(f"Test object not found or error accessing it: {e}")
                return

            try:
                # Phase 1: Warm-up using WarmUp class with shared worker pool
                logger.info("=== Phase 1: Concurrent Warm-up ===")

                warm_up = WarmUp(
                    worker_pool=self.worker_pool,
                    warm_up_minutes=WARM_UP_MINUTES,
                    concurrency=self.concurrency,
                    object_key=self.object_key,
                    system_bandwidth_gbps=self.system_bandwidth_gbps,
                )

                warm_up_results = await warm_up.execute()

                logger.info(
                    f"Warm-up completed: {warm_up_results['throughput_gbps']:.2f} Gbps"
                )

                # Phase 2: Ramp-up to find optimal concurrency using Ramp class with shared worker pool
                logger.info("=== Phase 2: Ramp-up ===")
                logger.info(
                    f"Starting ramp: {self.concurrency} -> {MAX_CONCURRENCY}, step 8 every 2m"
                )

                ramp = Ramp(
                    worker_pool=self.worker_pool,
                    initial_concurrency=self.concurrency,
                    ramp_step=8,
                    step_duration_seconds=120,  # 2 minutes
                    object_key=self.object_key,
                    plateau_threshold=0.2,
                    system_bandwidth_gbps=self.system_bandwidth_gbps,
                )

                ramp_results = await ramp.find_optimal_concurrency(
                    max_concurrency=MAX_CONCURRENCY
                )

                # Phase 3: Steady state benchmark using sophisticated SteadyState class
                logger.info("=== Phase 3: Steady State Benchmark ===")
                logger.info(
                    f"Running steady state for {STEADY_STATE_HOURS} hours with {ramp_results['best_concurrency']} connections"
                )

                steady_state = SteadyState(
                    worker_pool=self.worker_pool,
                    duration_hours=STEADY_STATE_HOURS,
                    concurrency=ramp_results["best_concurrency"],
                    object_key=self.object_key,
                    system_bandwidth_gbps=self.system_bandwidth_gbps,
                )

                steady_results = await steady_state.execute()

                # Save results to parquet
                parquet_file = self.persistence.save_to_file("benchmark")

                # Report results
                logger.info("=== Benchmark Results ===")
                logger.info(f"Total requests: {steady_results.get('total_requests', 0)}")
                logger.info(
                    f"Successful requests: {steady_results.get('successful_requests', 0)}"
                )
                logger.info(f"Throughput: {steady_results.get('throughput_gbps', 0):.2f} Gbps")
                logger.info(
                    f"Average latency: {steady_results.get('avg_latency_ms', 0):.1f} ms"
                )
                logger.info(
                    f"P95 latency: {steady_results.get('p95_latency_ms', 0):.1f} ms"
                )
                logger.info(
                    f"P99 latency: {steady_results.get('p99_latency_ms', 0):.1f} ms"
                )

                if parquet_file:
                    logger.info(f"Detailed results saved to: {parquet_file}")

                return {
                    "warm_up": warm_up_results,
                    "ramp_up": ramp_results,
                    "steady_state": steady_results,
                    "storage_type": self.storage_type,
                    "concurrency": self.concurrency,
                    "optimal_concurrency": ramp_results["best_concurrency"],
                }
            finally:
                # Cleanup shared worker pool
                if self.worker_pool:
                    await self.worker_pool.cleanup()


async def main_async():
    """Main async entry point for the benchmark runner."""
    parser = argparse.ArgumentParser(description="R2 benchmark runner")
    parser.add_argument(
        "--storage", choices=["r2", "s3"], default="r2", help="Storage type"
    )
    parser.add_argument("--object-key", help="Object key to test")
    parser.add_argument(
        "--concurrency", type=int, help="Number of concurrent connections"
    )
    parser.add_argument(
        "--worker-bandwidth", type=float, help="Worker bandwidth limit in Gbps"
    )

    args = parser.parse_args()

    runner = BenchmarkRunner(
        storage_type=args.storage,
        object_key=args.object_key,
        concurrency=args.concurrency,
        system_bandwidth_gbps=args.worker_bandwidth,
    )

    try:
        results = await runner.run_benchmark()
        print("\n=== Final Results ===")
        print(f"Storage type: {results['storage_type']}")
        print(f"Concurrency: {results['concurrency']}")
        if "steady_state" in results:
            steady = results["steady_state"]
            print(f"Total requests: {steady.get('total_requests', 0)}")
            print(f"Throughput: {steady.get('throughput_gbps', 0):.2f} Gbps")
            print(f"Average latency: {steady.get('avg_latency_ms', 0):.1f} ms")
    except KeyboardInterrupt:
        logger.info("Benchmark interrupted by user")
    except Exception as e:
        logger.error(f"Benchmark failed: {e}")
        sys.exit(1)


def main():
    """Main entry point for the benchmark runner."""
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
