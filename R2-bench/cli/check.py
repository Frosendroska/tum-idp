"""
Capacity discovery with hybrid multiprocessing + async architecture.
"""

import os
import sys
import logging
import argparse

# Disable boto3 verbose logging
os.environ['BOTO_DISABLE_COMMONNAME'] = '1'
os.environ['AWS_LOG_LEVEL'] = 'ERROR'

# Ensure project root is in path
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from configuration import (
    WARM_UP_MINUTES,
    RAMP_STEP_MINUTES,
    RAMP_STEP_WORKERS_PER_CORE,
    SECONDS_PER_MINUTE,
    PLATEAU_THRESHOLD,
    PIPELINE_DEPTH,
    INITIAL_WORKERS_PER_CORE,
    MAX_WORKERS_PER_CORE,
    CONNECTION_POOL_SAFETY_FACTOR,
    PERSISTENCE_FLUSH_INTERVAL_SECONDS,
    CONSOLIDATION_BATCH_SIZE,
)
from persistence.parquet import ParquetPersistence
from algorithms.warm_up import WarmUp
from algorithms.ramp import Ramp
from common.process_pool import ProcessPool

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

# Suppress verbose library loggers
logging.getLogger('botocore').setLevel(logging.CRITICAL)
logging.getLogger('boto3').setLevel(logging.CRITICAL)
logging.getLogger('aioboto3').setLevel(logging.CRITICAL)
logging.getLogger('urllib3').setLevel(logging.CRITICAL)

logger = logging.getLogger(__name__)


class CapacityChecker:
    """Hybrid multiprocessing + async capacity checker."""

    def __init__(
        self,
        storage_type: str,
        object_key: str,
        system_bandwidth_gbps: float = 50.0,
        num_processes: int = None,
        workers_per_process: int = None,
        ramp_step_workers: int = None,
        ramp_step_minutes: int = None,
        pipeline_depth: int = None,
        max_workers_per_core: int = None,
    ):
        import multiprocessing

        self.storage_type = storage_type.lower()
        self.object_key = object_key
        self.system_bandwidth_gbps = system_bandwidth_gbps

        # Auto-detect number of cores if not specified
        self.num_processes = num_processes or multiprocessing.cpu_count()

        # Use config values if not specified via CLI
        self.initial_workers_per_core = workers_per_process or INITIAL_WORKERS_PER_CORE
        self.ramp_step_workers_per_core = ramp_step_workers or RAMP_STEP_WORKERS_PER_CORE
        self.ramp_step_minutes = ramp_step_minutes or RAMP_STEP_MINUTES
        self.pipeline_depth = pipeline_depth or PIPELINE_DEPTH
        self.max_workers_per_core = max_workers_per_core or MAX_WORKERS_PER_CORE

        # Process pool manager
        self.process_pool = None

        # Persistence
        self.persistence = ParquetPersistence()

        total_workers = self.num_processes * self.initial_workers_per_core
        total_http_requests = total_workers * self.pipeline_depth
        logger.info(f"Initialized hybrid capacity checker for {storage_type.upper()}")
        logger.info(f"Detected/configured: {self.num_processes} cores")
        logger.info(f"Starting configuration: {self.initial_workers_per_core} workers/core × {self.pipeline_depth} pipeline depth")
        logger.info(f"Initial total workers: {total_workers}")
        logger.info(f"Initial concurrent HTTP requests: {total_http_requests}")
        logger.info(f"System bandwidth limit: {self.system_bandwidth_gbps} Gbps")
        logger.info(f"Ramp configuration: +{self.ramp_step_workers_per_core} workers/core every {self.ramp_step_minutes} minutes")

    async def check_capacity(self):
        """Execute capacity discovery."""
        logger.info("Starting capacity discovery")
        logger.info(f"Object key: {self.object_key}")

        try:
            # Initialize process pool
            # Create complete instance config with all required fields
            instance_config = {
                'vcpus': self.num_processes,
                'bandwidth_gbps': self.system_bandwidth_gbps,
                'pipeline_depth': self.pipeline_depth,
                'persistence_flush_interval_seconds': PERSISTENCE_FLUSH_INTERVAL_SECONDS,
                'connection_pool_size': int(self.max_workers_per_core * CONNECTION_POOL_SAFETY_FACTOR),
                'executor_threads_per_process': 2,  # Minimal threads for disk writes
            }

            self.process_pool = ProcessPool(
                storage_type=self.storage_type,
                persistence=self.persistence,
                instance_config=instance_config,
            )

            # Store object key for ProcessPool
            self.process_pool.current_object_key = self.object_key

            # Use instance variables for configuration (can be overridden via CLI)
            initial_workers_per_core = self.initial_workers_per_core
            ramp_step_workers_per_core = self.ramp_step_workers_per_core
            warm_up_minutes = WARM_UP_MINUTES  # Keep from config for now
            ramp_step_duration_seconds = self.ramp_step_minutes * SECONDS_PER_MINUTE
            max_workers_per_core = self.max_workers_per_core

            # Phase 1: Warm-up
            logger.info("=== Phase 1: Warm-up ===")
            logger.info(f"Warm-up: {initial_workers_per_core} workers/core for {warm_up_minutes} minutes")

            warm_up = WarmUp(
                process_pool=self.process_pool,
                warm_up_minutes=warm_up_minutes,
                workers_per_core=initial_workers_per_core,
                object_key=self.object_key,
                system_bandwidth_gbps=self.system_bandwidth_gbps,
            )

            warm_up_results = await warm_up.execute()
            logger.info(f"Warm-up completed: {warm_up_results['throughput_gbps']:.2f} Gbps")

            # Phase 2: Ramp-up
            logger.info("=== Phase 2: Ramp-up ===")

            # Calculate system-wide totals for logging
            total_workers_initial = initial_workers_per_core * self.num_processes
            total_workers_max = max_workers_per_core * self.num_processes
            total_http_requests_initial = total_workers_initial * self.pipeline_depth
            total_http_requests_max = total_workers_max * self.pipeline_depth

            logger.info(
                f"Ramp: {initial_workers_per_core} -> {max_workers_per_core} workers/core, "
                f"step +{ramp_step_workers_per_core} every {ramp_step_duration_seconds}s"
            )
            logger.info(
                f"System-wide totals: "
                f"{total_workers_initial} -> {total_workers_max} total workers, "
                f"{total_http_requests_initial} -> {total_http_requests_max} concurrent HTTP requests "
                f"({self.num_processes} cores × workers/core × {self.pipeline_depth} pipeline)"
            )

            ramp = Ramp(
                process_pool=self.process_pool,
                initial_workers_per_core=initial_workers_per_core,
                ramp_step_workers_per_core=ramp_step_workers_per_core,
                step_duration_seconds=ramp_step_duration_seconds,
                object_key=self.object_key,
                plateau_threshold=PLATEAU_THRESHOLD,
                system_bandwidth_gbps=self.system_bandwidth_gbps,
            )

            ramp_results = await ramp.find_optimal_concurrency(max_workers_per_core=max_workers_per_core)

            # Report results
            logger.info("=== Capacity Discovery Results ===")
            logger.info(f"Best workers per core: {ramp_results['best_workers_per_core']}")
            logger.info(f"Best throughput: {ramp_results['best_throughput_gbps']:.2f} Gbps")
            logger.info(f"Steps completed: {len(ramp_results['step_results'])}")
            logger.info(f"Plateau detected: {ramp_results['plateau_detected']}")
            logger.info(f"Plateau reason: {ramp_results['plateau_reason']}")

            # Log step results
            for i, step in enumerate(ramp_results['step_results'], 1):
                workers_per_core = step.get('workers_per_core', 0)
                total_http_requests = step.get('total_http_requests', 0)
                throughput = step.get('throughput_gbps', 0)
                avg_latency = step.get('avg_latency_ms', 0)
                total_requests = step.get('total_requests', 0)
                duration = step.get('duration_seconds', 0)
                rps = total_requests / duration if duration > 0 else 0
                logger.info(
                    f"Step {i}: {workers_per_core} workers/core ({total_http_requests} HTTP requests) -> {throughput:.2f} Gbps "
                    f"({total_requests} requests, {rps:.1f} req/s, {avg_latency:.0f}ms avg latency)"
                )

        except Exception as e:
            logger.error(f"Error during capacity check: {e}", exc_info=True)
            raise
        finally:
            # CRITICAL: Cleanup processes FIRST to capture final flush files
            if self.process_pool:
                await self.process_pool.cleanup()

            # THEN consolidate ALL files (including final flush files from cleanup)
            logger.info("\n=== Saving Benchmark Data ===")

            # Collect parquet files from all processes (now includes final flush files)
            parquet_files = []
            for file_info in self.process_pool.parquet_files:
                # Extract file path from dict or use directly if it's a string
                if isinstance(file_info, dict):
                    parquet_files.append(file_info['path'])
                else:
                    parquet_files.append(file_info)

            logger.info(f"Parquet files from processes: {len(parquet_files)}")

            if parquet_files:
                logger.info(f"Consolidating {len(parquet_files)} parquet files into single output file...")
                # Generate output filename
                from datetime import datetime
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                output_dir = self.persistence.output_dir
                output_file = os.path.join(output_dir, f"capacity_check_{self.storage_type}_{timestamp}.parquet")

                # Streaming consolidation to minimize memory usage
                try:
                    import pandas as pd
                    import shutil

                    # Use streaming consolidation if we have many files
                    batch_size = CONSOLIDATION_BATCH_SIZE

                    if len(parquet_files) <= batch_size:
                        # Small number of files - use simple approach
                        logger.info(f"Using direct consolidation (files <= {batch_size})")
                        dfs = []
                        files_read = []

                        for filepath in parquet_files:
                            if os.path.exists(filepath):
                                df = pd.read_parquet(filepath)
                                dfs.append(df)
                                files_read.append(filepath)
                            else:
                                logger.warning(f"File not found: {filepath}")

                        if dfs:
                            merged_df = pd.concat(dfs, ignore_index=True)
                        else:
                            logger.error("No data frames to merge")
                            merged_df = None
                    else:
                        # Large number of files - use streaming consolidation
                        logger.info(f"Using streaming consolidation (batch size: {batch_size} files)")

                        # Create temporary directory for intermediate batch files
                        temp_dir = os.path.join(output_dir, f"temp_consolidation_{timestamp}")
                        os.makedirs(temp_dir, exist_ok=True)

                        try:
                            temp_batch_files = []
                            files_read = []
                            total_batches = (len(parquet_files) + batch_size - 1) // batch_size

                            # Process files in batches
                            for batch_idx in range(0, len(parquet_files), batch_size):
                                batch = parquet_files[batch_idx:batch_idx + batch_size]
                                batch_dfs = []

                                for filepath in batch:
                                    if os.path.exists(filepath):
                                        df = pd.read_parquet(filepath)
                                        batch_dfs.append(df)
                                        files_read.append(filepath)
                                    else:
                                        logger.warning(f"File not found: {filepath}")

                                if batch_dfs:
                                    # Concatenate this batch
                                    batch_merged = pd.concat(batch_dfs, ignore_index=True)

                                    # Write intermediate batch file
                                    batch_file = os.path.join(temp_dir, f"batch_{batch_idx // batch_size:04d}.parquet")
                                    batch_merged.to_parquet(batch_file, index=False)
                                    temp_batch_files.append(batch_file)

                                    current_batch = (batch_idx // batch_size) + 1
                                    logger.info(
                                        f"Processed batch {current_batch}/{total_batches} "
                                        f"({len(batch_dfs)} files, {len(batch_merged):,} records)"
                                    )

                                    # Free memory
                                    del batch_dfs, batch_merged

                            # Final merge of batch files (much fewer files)
                            if temp_batch_files:
                                logger.info(f"Final merge of {len(temp_batch_files)} batch files...")
                                final_dfs = [pd.read_parquet(f) for f in temp_batch_files]
                                merged_df = pd.concat(final_dfs, ignore_index=True)
                                del final_dfs
                            else:
                                logger.error("No batch files created")
                                merged_df = None

                        finally:
                            # Clean up temporary directory
                            if os.path.exists(temp_dir):
                                try:
                                    shutil.rmtree(temp_dir)
                                    logger.info(f"Cleaned up temporary directory: {temp_dir}")
                                except Exception as e:
                                    logger.warning(f"Failed to remove temp directory {temp_dir}: {e}")

                    # Sort and save final consolidated file
                    if merged_df is not None:
                        # Sort by timestamp for chronological order
                        if 'start_ts' in merged_df.columns:
                            logger.info("Sorting records by start_ts...")
                            merged_df = merged_df.sort_values('start_ts')

                        # Save consolidated file
                        logger.info(f"Writing consolidated file: {output_file}")
                        merged_df.to_parquet(output_file, index=False, compression='snappy')
                        self.persistence.output_file = output_file

                        logger.info(f"✓ Consolidated benchmark data saved to: {output_file}")
                        logger.info(f"✓ Total records: {len(merged_df):,}")
                        logger.info(f"✓ Phases: {sorted(merged_df['phase_id'].unique())}")

                        # Delete individual parquet files to save space and reduce clutter
                        logger.info(f"Cleaning up {len(files_read)} individual parquet files...")
                        deleted_count = 0
                        for filepath in files_read:
                            try:
                                os.remove(filepath)
                                deleted_count += 1
                            except Exception as e:
                                logger.warning(f"Failed to delete {filepath}: {e}")

                        logger.info(f"✓ Deleted {deleted_count} temporary parquet files")
                    else:
                        logger.error("No data to save")

                except Exception as e:
                    logger.error(f"Failed to merge parquet files: {e}", exc_info=True)
            else:
                logger.warning("No parquet files to merge")


def main():
    """Entry point."""
    import asyncio

    parser = argparse.ArgumentParser(description="R2 capacity checker (hybrid multiprocessing + async)")
    parser.add_argument(
        "--storage", choices=["r2", "s3"], default="r2", help="Storage type"
    )
    parser.add_argument("--object-key", help="Object key to test")
    parser.add_argument(
        "--bandwidth",
        type=float,
        default=50.0,
        help="System bandwidth limit in Gbps (default: 50.0)",
    )
    parser.add_argument(
        "--processes",
        type=int,
        help="Number of worker processes (default: auto-detect CPU count)",
    )
    parser.add_argument(
        "--workers",
        type=int,
        help=f"Initial workers per core (default: {INITIAL_WORKERS_PER_CORE})",
    )

    args = parser.parse_args()

    checker = CapacityChecker(
        storage_type=args.storage,
        object_key=args.object_key or "test-object-9gb",
        system_bandwidth_gbps=args.bandwidth,
        num_processes=args.processes,
        workers_per_process=args.workers,  # Parameter name kept for backward compatibility
    )

    asyncio.run(checker.check_capacity())


if __name__ == "__main__":
    main()
