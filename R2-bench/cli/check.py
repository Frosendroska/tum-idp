"""
Refactored Phase 1: Capacity discovery and plateau detection with precise concurrency control.
"""

import asyncio
import os
import sys
import logging
import argparse
import time
from typing import Dict, Any

# Disable boto3 verbose logging via environment variable BEFORE any boto3 imports
os.environ['BOTO_DISABLE_COMMONNAME'] = '1'
os.environ['AWS_LOG_LEVEL'] = 'ERROR'

# Required: Use uvloop for better performance
import uvloop
asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())

# Ensure project root is in path (for running as script)
# When run as module (python -m cli.check), this is not needed
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from configuration import (
    WARM_UP_MINUTES,
    INITIAL_CONCURRENCY,
    RAMP_STEP_MINUTES,
    RAMP_STEP_CONCURRENCY,
    SECONDS_PER_MINUTE,
    PLATEAU_THRESHOLD,
)
from common.storage_factory import create_storage_system
from common.instance_detector import InstanceDetector
from persistence.parquet import ParquetPersistence
from algorithms.plateau_check import PlateauCheck
from algorithms.warm_up import WarmUp
from algorithms.ramp import Ramp
from common.process_pool import ProcessPool

# Set up logging (only if not already configured)
if not logging.root.handlers:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
    )

# Suppress verbose library loggers to reduce log duplication
logging.getLogger('botocore').setLevel(logging.CRITICAL)
logging.getLogger('botocore.credentials').setLevel(logging.CRITICAL)
logging.getLogger('boto3').setLevel(logging.CRITICAL)
logging.getLogger('aioboto3').setLevel(logging.CRITICAL)
logging.getLogger('urllib3').setLevel(logging.CRITICAL)
logging.getLogger('s3transfer').setLevel(logging.CRITICAL)

logger = logging.getLogger(__name__)


class CapacityChecker:
    """Refactored capacity checker with precise concurrency control and immediate phase switching."""

    def __init__(
        self,
        storage_type: str,
        object_key: str,
    ):
        self.storage_type = storage_type.lower()
        self.object_key = object_key

        # Detect instance and load configuration
        self.instance_detector = InstanceDetector()
        self.instance_config = self.instance_detector.get_config()
        self.system_bandwidth_gbps = self.instance_config.get('bandwidth_gbps', 10)

        # Initialize components
        self.persistence = ParquetPersistence()

        # Shared process pool for reuse across phases (multiprocessing for full CPU utilization)
        self.process_pool = None

        logger.info(f"Initialized capacity checker for {storage_type.upper()}")
        logger.info(f"System bandwidth limit: {self.system_bandwidth_gbps} Gbps")


    async def check_capacity(self, object_key: str = None):
        """Execute the refactored capacity discovery process."""
        if object_key:
            self.object_key = object_key

        logger.info("Starting capacity discovery process")
        logger.info(f"Using object key: {self.object_key}")

        # Print instance configuration
        self.instance_detector.print_configuration()

        try:
            # Initialize process pool (multiprocessing for full CPU utilization)
            self.process_pool = ProcessPool(
                self.storage_type,
                self.persistence,
                instance_config=self.instance_config
            )

            # Use instance-specific concurrency for RAMP, but start warm-up conservatively
            # Warm-up should be gentle to avoid memory spike
            warmup_concurrency = INITIAL_CONCURRENCY

            # Start ramp at a low value to properly discover optimal concurrency
            initial_ramp_concurrency = warmup_concurrency

            # Use total_workers as max_concurrency (full system capacity)
            # This is num_processes × workers_per_process × pipeline_depth
            max_concurrency = self.instance_config.get('total_workers', 180)

            # Phase 1: Warm-up (start conservatively)
            logger.info("=== Phase 1: Concurrent Warm-up ===")
            logger.info(f"Warm-up will use {warmup_concurrency} workers (conservative start)")

            warm_up = WarmUp(
                worker_pool=self.process_pool,
                warm_up_minutes=WARM_UP_MINUTES,
                concurrency=warmup_concurrency,  # Conservative start
                object_key=self.object_key,
                system_bandwidth_gbps=self.system_bandwidth_gbps,
            )

            warm_up_results = await warm_up.execute()

            logger.info(
                f"Warm-up completed: {warm_up_results['throughput_gbps']:.2f} Gbps"
            )

            # Phase 2: Ramp-up
            logger.info("=== Phase 2: Ramp-up ===")
            ramp_step = self.instance_config.get('ramp_step_size', RAMP_STEP_CONCURRENCY)
            ramp_interval = self.instance_config.get('ramp_step_interval', RAMP_STEP_MINUTES * SECONDS_PER_MINUTE)

            logger.info(
                f"Starting ramp: {initial_ramp_concurrency} -> {max_concurrency}, step {ramp_step} every {ramp_interval}s"
            )

            ramp = Ramp(
                worker_pool=self.process_pool,
                initial_concurrency=initial_ramp_concurrency,  # Start ramp from configured initial
                ramp_step=ramp_step,
                step_duration_seconds=ramp_interval,
                object_key=self.object_key,
                plateau_threshold=PLATEAU_THRESHOLD,
                system_bandwidth_gbps=self.system_bandwidth_gbps,
            )

            ramp_results = await ramp.find_optimal_concurrency(
                max_concurrency=max_concurrency
            )

            # Report results
            logger.info("=== Capacity Discovery Results ===")
            logger.info(f"Best concurrency: {ramp_results['best_concurrency']}")
            logger.info(
                f"Best throughput: {ramp_results['best_throughput_gbps']:.2f} Gbps"
            )
            logger.info(f"Steps completed: {len(ramp_results['step_results'])}")
            logger.info(f"Plateau detected: {ramp_results['plateau_detected']}")
            logger.info(f"Plateau reason: {ramp_results['plateau_reason']}")

            # Show step-by-step results
            for i, step in enumerate(ramp_results["step_results"]):
                logger.info(
                    f"Step {i+1}: {step['concurrency']} conn -> {step['throughput_gbps']:.2f} Gbps"
                )

            # Save all collected benchmark data to Parquet
            logger.info(f"\n=== Saving Benchmark Data ===")
            total_records = len(self.persistence.records)
            logger.info(f"Total records collected: {total_records}")

            if total_records > 0:
                parquet_file = self.persistence.save_to_file(
                    filename_prefix=f"capacity_check_{self.storage_type}"
                )
                if parquet_file:
                    logger.info(f"✓ Benchmark data saved to: {parquet_file}")
                else:
                    logger.warning("✗ Failed to save benchmark data")
            else:
                logger.warning("✗ No records to save")

            # Print error summary from storage system metrics
            logger.info(f"\n=== Connection Health Summary ===")
            # Note: In multiprocess mode, each process has its own storage system
            # so these metrics are per-process. For aggregate view, check Parquet file.
            logger.info(f"Check logs above for:")
            logger.info(f"  - [#X] Incomplete payload warnings (connection drops)")
            logger.info(f"  - [TIMEOUT #X] Request timeouts")
            logger.info(f"  - [THROTTLE #X] R2 throttling errors (HTTP 429/503)")
            logger.info(f"If you see many errors, reduce concurrency in instance_profiles.yaml")

            return {
                "warm_up": warm_up_results,
                "ramp_up": ramp_results,
                "optimal_concurrency": ramp_results["best_concurrency"],
                "max_throughput_gbps": ramp_results["best_throughput_gbps"],
                "plateau_detected": ramp_results["plateau_detected"],
                "plateau_reason": ramp_results["plateau_reason"],
                "total_records": total_records,
                "parquet_file": parquet_file if total_records > 0 else None,
            }

        except KeyboardInterrupt:
            logger.info("Benchmark interrupted by user (Ctrl+C)")
            return {
                "warm_up": {"error": "Interrupted by user"},
                "ramp_up": {"error": "Interrupted by user"},
                "optimal_concurrency": 0,
                "max_throughput_gbps": 0,
                "plateau_detected": False,
                "plateau_reason": "Interrupted by user",
            }
        except Exception as e:
            logger.error(f"Error during benchmark: {e}")
            import traceback

            logger.error(f"Traceback: {traceback.format_exc()}")
            raise
        finally:
            # Cleanup process pool
            if self.process_pool:
                await self.process_pool.cleanup()


async def main_async():
    """Main async entry point for the refactored capacity checker."""
    parser = argparse.ArgumentParser(description="Refactored R2 capacity checker")
    parser.add_argument(
        "--storage", choices=["r2", "s3"], default="r2", help="Storage type"
    )
    parser.add_argument("--object-key", help="Object key to test")

    args = parser.parse_args()

    checker = CapacityChecker(
        storage_type=args.storage,
        object_key=args.object_key,
    )

    try:
        results = await checker.check_capacity()
        print("\n=== Final Results ===")
        print(f"Optimal concurrency: {results['optimal_concurrency']}")
        print(f"Max throughput: {results['max_throughput_gbps']:.2f} Gbps")
        print(f"Plateau detected: {results['plateau_detected']}")
        print(f"Plateau reason: {results['plateau_reason']}")
    except KeyboardInterrupt:
        logger.info("Benchmark interrupted by user")
    except Exception as e:
        logger.error(f"Benchmark failed: {e}")
        sys.exit(1)


def main():
    """Main entry point for the refactored capacity checker."""
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
