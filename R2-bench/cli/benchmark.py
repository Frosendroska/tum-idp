"""
Phase 2: Long-term performance benchmark.
"""

import os
import sys
import logging
import argparse
import time
from configuration import DEFAULT_OUTPUT_DIR

# Add the current directory to Python path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from configuration import (
    WARM_UP_MINUTES,
    STEADY_STATE_HOURS,
    AWS_ACCESS_KEY_ID,
    AWS_SECRET_ACCESS_KEY,
    AWS_REGION,
    R2_ACCESS_KEY_ID,
    R2_SECRET_ACCESS_KEY,
    INITIAL_CONCURRENCY,
    DEFAULT_OBJECT_KEY,
)
from systems.r2 import R2System
from systems.aws import AWSSystem
from algorithms.warm_up import WarmUp
from algorithms.steady import SimpleSteadyState
from persistence.parquet import ParquetPersistence

# Set up logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class SimpleBenchmarkRunner:
    """Simple benchmark runner for long-term performance measurement."""

    def __init__(self, storage_type: str = "r2", object_key: str = None):
        self.storage_type = storage_type.lower()
        self.concurrency = INITIAL_CONCURRENCY
        self.object_key = object_key or DEFAULT_OBJECT_KEY
        self.storage_system = None
        self.persistence = None

        # Initialize components
        self._initialize_components()

        logger.info(
            f"Initialized benchmark runner: {storage_type.upper()} with {concurrency} connections"
        )

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
            self.persistence = ParquetPersistence(output_dir=DEFAULT_OUTPUT_DIR)

        except Exception as e:
            logger.error(f"Failed to initialize components: {e}")
            raise

    def run_benchmark(self):
        """Execute the complete benchmark."""
        logger.info("Starting R2 benchmark")

        # Phase 1: Warm-up
        logger.info("=== Phase 1: Warm-up ===")
        warm_up = WarmUp(self.storage_system, WARM_UP_MINUTES, self.object_key)
        warm_up_results = warm_up.execute()

        logger.info(
            f"Warm-up completed: {warm_up_results['successful_requests']} successful requests"
        )

        # Phase 2: Steady state benchmark
        logger.info("=== Phase 2: Steady State Benchmark ===")
        steady_state = SteadyState(
            self.storage_system,
            duration_hours=STEADY_STATE_HOURS,
            object_key=self.object_key,
        )

        steady_results = steady_state.execute()

        # Save results to Parquet
        if self.persistence:
            # Create benchmark records from steady state results
            # This is a simplified approach - in a real implementation you'd collect records during execution
            logger.info("Saving benchmark results to Parquet file")

            # For now, just save a summary
            # In a real implementation, you'd collect BenchmarkRecord objects during execution
            logger.info("Benchmark results summary:")
            logger.info(f"  Total requests: {steady_results.get('total_requests', 0)}")
            logger.info(
                f"  Successful requests: {steady_results.get('successful_requests', 0)}"
            )
            logger.info(f"  Success rate: {steady_results.get('success_rate', 0):.2%}")
            logger.info(
                f"  Total bytes: {steady_results.get('total_bytes_downloaded', 0) / (1024**3):.2f} GB"
            )
            logger.info(
                f"  Average throughput: {steady_results.get('avg_throughput_mbps', 0):.1f} Mbps"
            )
            logger.info(
                f"  Average latency: {steady_results.get('avg_latency_ms', 0):.1f} ms"
            )

        return {
            "warm_up": warm_up_results,
            "steady_state": steady_results,
            "storage_type": self.storage_type,
            "concurrency": self.concurrency,
        }
