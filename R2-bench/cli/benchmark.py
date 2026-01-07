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
)
from common.storage_factory import create_storage_system
from common.instance_detector import InstanceDetector
from algorithms.warm_up import WarmUp
from algorithms.ramp import Ramp
from algorithms.steady_state import SteadyState
from persistence.parquet import ParquetPersistence
from common.process_pool import ProcessPool

# Set up logging (only if not already configured)
if not logging.root.handlers:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
    )

# Suppress verbose library loggers to reduce log duplication
logging.getLogger('botocore').setLevel(logging.ERROR)
logging.getLogger('botocore.credentials').setLevel(logging.ERROR)
logging.getLogger('boto3').setLevel(logging.ERROR)
logging.getLogger('aioboto3').setLevel(logging.ERROR)
logging.getLogger('urllib3').setLevel(logging.ERROR)
logging.getLogger('s3transfer').setLevel(logging.ERROR)

logger = logging.getLogger(__name__)


class BenchmarkRunner:
    """Benchmark runner for long-term performance measurement with precise concurrency control."""

    def __init__(
        self,
        storage_type: str = "r2",
        object_key: str = None,
        concurrency: int = None,
    ):
        self.storage_type = storage_type.lower()
        self.object_key = object_key
        self.persistence = None
        self.process_pool = None

        # Detect instance and load configuration
        logger.info("Detecting instance type and loading configuration...")
        self.instance_detector = InstanceDetector()
        self.instance_config = self.instance_detector.get_config()
        self.system_bandwidth_gbps = self.instance_config.get('bandwidth_gbps', 10)

        # Print detected configuration
        self.instance_detector.print_configuration()

        # Use instance-specific concurrency if not provided
        self.concurrency = concurrency or self.instance_config.get('max_concurrency')

        # Initialize components
        self._initialize_components()

        logger.info(
            f"Initialized benchmark runner: {storage_type.upper()} with {self.concurrency} connections"
        )
        logger.info(f"Worker bandwidth limit: {self.system_bandwidth_gbps} Gbps")

    def _initialize_components(self):
        """Initialize required components."""
        try:
            # Initialize persistence
            self.persistence = ParquetPersistence()

            # Initialize process pool (multiprocessing for full CPU utilization)
            self.process_pool = ProcessPool(
                self.storage_type,
                self.persistence,
                instance_config=self.instance_config
            )

        except Exception as e:
            logger.error(f"Failed to initialize components: {e}")
            raise

    async def run_benchmark(self) -> Dict[str, Any]:
        """Execute the complete benchmark."""
        logger.info("Starting benchmark")
        logger.info(f"Using object key: {self.object_key}")

        try:
            # Phase 1: Warm-up
            logger.info("=== Phase 1: Concurrent Warm-up ===")

            warm_up = WarmUp(
                worker_pool=self.process_pool,
                warm_up_minutes=WARM_UP_MINUTES,
                concurrency=self.concurrency,
                object_key=self.object_key,
                system_bandwidth_gbps=self.system_bandwidth_gbps,
            )

            warm_up_results = await warm_up.execute()

            logger.info(
                f"Warm-up completed: {warm_up_results['throughput_gbps']:.2f} Gbps"
            )

            # Phase 2: Ramp-up
            logger.info("=== Phase 2: Ramp-up ===")

            # Use instance-specific ramp configuration
            ramp_step = self.instance_config.get('ramp_step_size', 8)
            ramp_interval = self.instance_config.get('ramp_step_interval', 120)
            max_concurrency = self.instance_config.get('max_concurrency')

            logger.info(
                f"Starting ramp: {self.concurrency} -> {max_concurrency}, "
                f"step {ramp_step} every {ramp_interval}s"
            )

            ramp = Ramp(
                worker_pool=self.process_pool,
                initial_concurrency=self.concurrency,
                ramp_step=ramp_step,
                step_duration_seconds=ramp_interval,
                object_key=self.object_key,
                plateau_threshold=0.2,
                system_bandwidth_gbps=self.system_bandwidth_gbps,
            )

            ramp_results = await ramp.find_optimal_concurrency(
                max_concurrency=max_concurrency
            )

            # Phase 3: Steady state
            logger.info("=== Phase 3: Steady State Benchmark ===")
            logger.info(
                f"Running steady state for {STEADY_STATE_HOURS} hours with {ramp_results['best_concurrency']} connections"
            )

            steady_state = SteadyState(
                worker_pool=self.process_pool,
                duration_hours=STEADY_STATE_HOURS,
                concurrency=ramp_results["best_concurrency"],
                object_key=self.object_key,
                system_bandwidth_gbps=self.system_bandwidth_gbps,
            )

            steady_results = await steady_state.execute()

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

            return {
                "warm_up": warm_up_results,
                "ramp_up": ramp_results,
                "steady_state": steady_results,
                "storage_type": self.storage_type,
                "concurrency": self.concurrency,
                "optimal_concurrency": ramp_results["best_concurrency"],
            }
        finally:
            # Cleanup process pool
            if self.process_pool:
                await self.process_pool.cleanup()


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
    args = parser.parse_args()

    runner = BenchmarkRunner(
        storage_type=args.storage,
        object_key=args.object_key,
        concurrency=args.concurrency,
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
