"""
Refactored Phase 1: Capacity discovery and plateau detection with precise concurrency control.
"""

import os
import sys
import logging
import argparse
import time
from typing import Dict, Any

# Add the current directory to Python path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from configuration import (
    WARM_UP_MINUTES,
    INITIAL_CONCURRENCY,
    RAMP_STEP_MINUTES,
    RAMP_STEP_CONCURRENCY,
    AWS_ACCESS_KEY_ID,
    AWS_SECRET_ACCESS_KEY,
    AWS_REGION,
    R2_ACCESS_KEY_ID,
    R2_SECRET_ACCESS_KEY,
    MAX_CONCURRENCY,
    SECONDS_PER_MINUTE,
    PLATEAU_THRESHOLD,
)
from systems.r2 import R2System
from systems.aws import AWSSystem
from persistence.parquet import ParquetPersistence
from algorithms.plateau_check import PlateauCheck
from algorithms.warm_up import WarmUp
from algorithms.ramp import Ramp
from common.worker_pool import WorkerPool

# Set up logging
logging.basicConfig(
    level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class CapacityChecker:
    """Refactored capacity checker with precise concurrency control and immediate phase switching."""

    def __init__(
        self,
        storage_type: str,
        object_key: str,
        system_bandwidth_mbps: float,
    ):
        self.storage_type = storage_type.lower()
        self.object_key = object_key
        self.system_bandwidth_mbps = system_bandwidth_mbps
        self.storage_system = None

        # Initialize components
        self.persistence = ParquetPersistence()

        # Shared worker pool for reuse across phases
        self.worker_pool = None

        # Initialize storage system
        self._initialize_storage()

        logger.info(f"Initialized capacity checker for {storage_type.upper()}")
        logger.info(f"System bandwidth limit: {self.system_bandwidth_mbps} Mbps")

    def _initialize_storage(self):
        """Initialize the appropriate storage system."""
        try:
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

        except Exception as e:
            logger.error(
                f"Failed to initialize {self.storage_type.upper()} storage: {e}"
            )
            raise

    def check_capacity(self, object_key: str = None):
        """Execute the refactored capacity discovery process."""
        if object_key:
            self.object_key = object_key

        logger.info("Starting capacity discovery process")
        logger.info(f"Using object key: {self.object_key}")

        try:
            # Check if object exists
            logger.info("Checking if test object exists...")
            response = self.storage_system.client.head_object(
                Bucket=self.storage_system.bucket_name, Key=self.object_key
            )
            logger.info(f"Test object found: {response['ContentLength']} bytes")
        except Exception as e:
            logger.warning(f"Test object not found or error accessing it: {e}")
            logger.info(
                "Attempting to create a smaller test object for more reliable testing..."
            )
            return

        try:
            # Initialize shared worker pool
            self.worker_pool = WorkerPool(self.storage_system, MAX_CONCURRENCY)

            # Phase 1: Warm-up using WarmUp class with shared worker pool
            logger.info("=== Phase 1: Concurrent Warm-up ===")

            warm_up = WarmUp(
                worker_pool=self.worker_pool,
                warm_up_minutes=WARM_UP_MINUTES,
                concurrency=INITIAL_CONCURRENCY,
                object_key=self.object_key,
                system_bandwidth_mbps=self.system_bandwidth_mbps,
            )

            warm_up_results = warm_up.execute()

            logger.info(
                f"Warm-up completed: {warm_up_results['throughput_mbps']:.1f} Mbps"
            )

            # Phase 2: Ramp-up to find optimal concurrency using Ramp class with shared worker pool
            logger.info("=== Phase 2: Ramp-up ===")
            logger.info(
                f"Starting ramp: {INITIAL_CONCURRENCY} -> {MAX_CONCURRENCY}, step {RAMP_STEP_CONCURRENCY} every {RAMP_STEP_MINUTES}m"
            )

            ramp = Ramp(
                worker_pool=self.worker_pool,
                initial_concurrency=INITIAL_CONCURRENCY,
                ramp_step=RAMP_STEP_CONCURRENCY,
                step_duration_seconds=RAMP_STEP_MINUTES * SECONDS_PER_MINUTE,
                object_key=self.object_key,
                plateau_threshold=PLATEAU_THRESHOLD,
                system_bandwidth_mbps=self.system_bandwidth_mbps,
            )

            ramp_results = ramp.find_optimal_concurrency(
                max_concurrency=MAX_CONCURRENCY
            )

            # Save results to parquet
            parquet_file = self.persistence.save_to_file("benchmark")

            # Report results
            logger.info("=== Capacity Discovery Results ===")
            logger.info(f"Best concurrency: {ramp_results['best_concurrency']}")
            logger.info(
                f"Best throughput: {ramp_results['best_throughput_mbps']:.1f} Mbps"
            )
            logger.info(f"Steps completed: {len(ramp_results['step_results'])}")
            logger.info(f"Plateau detected: {ramp_results['plateau_detected']}")
            logger.info(f"Plateau reason: {ramp_results['plateau_reason']}")

            # Show step-by-step results
            for i, step in enumerate(ramp_results["step_results"]):
                logger.info(
                    f"Step {i+1}: {step['concurrency']} conn -> {step['throughput_mbps']:.1f} Mbps"
                )

            if parquet_file:
                logger.info(f"Detailed results saved to: {parquet_file}")

            return {
                "warm_up": warm_up_results,
                "ramp_up": ramp_results,
                "optimal_concurrency": ramp_results["best_concurrency"],
                "max_throughput_mbps": ramp_results["best_throughput_mbps"],
                "plateau_detected": ramp_results["plateau_detected"],
                "plateau_reason": ramp_results["plateau_reason"],
            }

        except KeyboardInterrupt:
            logger.info("Benchmark interrupted by user (Ctrl+C)")
            return {
                "warm_up": {"error": "Interrupted by user"},
                "ramp_up": {"error": "Interrupted by user"},
                "optimal_concurrency": 0,
                "max_throughput_mbps": 0,
                "plateau_detected": False,
                "plateau_reason": "Interrupted by user",
            }
        except Exception as e:
            logger.error(f"Error during benchmark: {e}")
            import traceback

            logger.error(f"Traceback: {traceback.format_exc()}")
            raise
        finally:
            # Cleanup shared worker pool
            if self.worker_pool:
                self.worker_pool.cleanup()


def main():
    """Main entry point for the refactored capacity checker."""
    parser = argparse.ArgumentParser(description="Refactored R2 capacity checker")
    parser.add_argument(
        "--storage", choices=["r2", "s3"], default="r2", help="Storage type"
    )
    parser.add_argument("--object-key", help="Object key to test")
    parser.add_argument(
        "--worker-bandwidth", type=float, help="Worker bandwidth limit in Mbps"
    )

    args = parser.parse_args()

    checker = CapacityChecker(
        storage_type=args.storage,
        object_key=args.object_key,
        system_bandwidth_mbps=args.system_bandwidth_mbps,
    )

    try:
        results = checker.check_capacity()
        print("\n=== Final Results ===")
        print(f"Optimal concurrency: {results['optimal_concurrency']}")
        print(f"Max throughput: {results['max_throughput_mbps']:.1f} Mbps")
        print(f"Plateau detected: {results['plateau_detected']}")
        print(f"Plateau reason: {results['plateau_reason']}")
    except KeyboardInterrupt:
        logger.info("Benchmark interrupted by user")
    except Exception as e:
        logger.error(f"Benchmark failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
