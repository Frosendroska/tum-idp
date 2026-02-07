"""
Process pool that spawns one process per CPU core.

Architecture:
- Spawns one OS process per CPU core for maximum parallelism
- Each process runs its own async WorkerPool with configurable workers
- Shared state for dynamic ramping: workers_per_core can be adjusted without restarting
- Periodic disk flushing to prevent memory issues with long-running benchmarks
"""

import asyncio
import multiprocessing as mp
import logging
import time
import os
import pandas as pd
from typing import Dict, Any, List, Optional

# Set up uvloop for performance
import uvloop
asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())

logger = logging.getLogger(__name__)


def _run_worker_process(
    process_id: int,
    storage_type: str,
    object_key: str,
    workers_per_core: int,
    phase_id: str,
    duration_seconds: float,
    instance_config: Dict[str, Any],
    result_queue: mp.Queue,
    stop_event: mp.Event,
    shared_phase_id,
    shared_object_key,
    shared_workers_per_core,
    shared_total_workers,
    shared_total_http_requests,
):
    """Worker process function. Runs in separate process (one per core).

    Args:
        process_id: Core ID (0 to cores-1)
        storage_type: 'r2' or 's3'
        object_key: Object key to download
        workers_per_core: Initial number of async workers for this core
        phase_id: Phase identifier
        duration_seconds: How long to run (or inf for continuous)
        instance_config: Instance configuration dict
        result_queue: Queue for sending records to main process
        stop_event: Event for coordinated shutdown
        shared_phase_id: Shared value for phase transitions
        shared_object_key: Shared value for object key
        shared_workers_per_core: Shared value for workers per core (updated during ramp)
        shared_total_workers: Shared value for total workers across all cores
        shared_total_http_requests: Shared value for total HTTP requests (workers × cores × pipeline)
    """
    # Suppress verbose logging in child processes
    logging.root.setLevel(logging.WARNING)
    for handler in logging.root.handlers:
        handler.setLevel(logging.WARNING)

    logging.getLogger('botocore').setLevel(logging.CRITICAL)
    logging.getLogger('boto3').setLevel(logging.CRITICAL)
    logging.getLogger('aioboto3').setLevel(logging.CRITICAL)
    logging.getLogger('urllib3').setLevel(logging.CRITICAL)

    # Process-specific logger
    process_logger = logging.getLogger(f"process_{process_id}")
    process_logger.setLevel(logging.INFO)

    # Initialize uvloop for this process
    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())

    # Run async worker
    return asyncio.run(_async_worker_process(
        process_id, storage_type, object_key, workers_per_core,
        phase_id, duration_seconds, instance_config, result_queue, stop_event,
        shared_phase_id, shared_object_key, shared_workers_per_core,
        shared_total_workers, shared_total_http_requests
    ))


async def _async_worker_process(
    process_id: int,
    storage_type: str,
    object_key: str,
    workers_per_core: int,
    phase_id: str,
    duration_seconds: float,
    instance_config: Dict[str, Any],
    result_queue: mp.Queue,
    stop_event: mp.Event,
    shared_phase_id,
    shared_object_key,
    shared_workers_per_core,
    shared_total_workers,
    shared_total_http_requests,
):
    """Async worker process task."""
    from common.storage_factory import create_storage_system
    from common.worker_pool import WorkerPool
    from persistence.parquet import ParquetPersistence

    process_logger = logging.getLogger(f"process_{process_id}")

    try:
        # Initialize storage and worker pool
        # Pass workers_per_core for accurate connection pool sizing
        storage_system = create_storage_system(storage_type, verbose_init=False, workers_per_core=workers_per_core)
        persistence = ParquetPersistence()

        cores = instance_config.get('vcpus', 1)
        pipeline_depth = instance_config.get('pipeline_depth', 3)

        process_logger.info(f"Process {process_id}: Initializing with {workers_per_core} workers/core")

        worker_pool = WorkerPool(
            storage_system,
            process_id=process_id,
            pipeline_depth=pipeline_depth,
            shared_total_http_requests=shared_total_http_requests,
        )

        # Start storage and workers
        async with storage_system:
            await worker_pool.start_workers(workers_per_core, object_key, phase_id)

            start_time = time.time()
            last_check_time = start_time
            last_flush_time = start_time
            current_workers_per_core = workers_per_core

            flush_interval = instance_config.get('persistence_flush_interval_seconds', 60.0)

            while True:
                # Check stop event or timeout
                if stop_event.is_set() or (time.time() - start_time) >= duration_seconds:
                    break

                current_time = time.time()

                # Check for phase transitions every 2 seconds
                if (current_time - last_check_time) >= 2.0:
                    new_workers_per_core = shared_workers_per_core.value
                    new_phase = shared_phase_id.value
                    new_object_key = shared_object_key.value

                    # Detect phase change (including flush signals)
                    if new_phase != phase_id:
                        process_logger.info(
                            f"Process {process_id}: Phase transition detected: "
                            f"{phase_id} → {new_phase}"
                        )

                        # Force flush if this is a flush signal (ends with _flush)
                        if new_phase.endswith("_flush"):
                            actual_phase = new_phase.replace("_flush", "")
                            process_logger.info(f"Process {process_id}: Flush signal received for phase {actual_phase}")

                            records = worker_pool.get_records()
                            if len(records) > 0:
                                # CRITICAL: Use phase_id from worker_pool to match records
                                current_phase_for_records = worker_pool.current_phase_id or actual_phase

                                filename = f"benchmark_process{process_id}_phase_{current_phase_for_records}_{int(current_time)}"
                                filepath = persistence.save_records_to_parquet(records, filename)
                                if filepath:
                                    result_queue.put({
                                        "type": "parquet_file",
                                        "process_id": process_id,
                                        "filepath": filepath,
                                        "record_count": len(records),
                                        "phase_id": current_phase_for_records  # Tag with ACTUAL phase in records
                                    })
                                    worker_pool.clear_records()
                                    last_flush_time = current_time
                                    process_logger.info(f"Process {process_id}: Flushed {len(records)} records for phase {current_phase_for_records}")

                        # Update phase (don't update if it's just a flush signal)
                        if not new_phase.endswith("_flush"):
                            phase_id = new_phase
                            # CRITICAL: Update worker pool phase_id immediately
                            # This ensures workers use the new phase_id for all records
                            worker_pool.current_phase_id = phase_id
                            process_logger.warning(f"Process {process_id}: Phase updated to '{phase_id}'")

                    # Detect worker count change
                    if new_workers_per_core != current_workers_per_core:
                        process_logger.warning(
                            f"Process {process_id}: Ramp detected - "
                            f"workers_per_core {current_workers_per_core} → {new_workers_per_core}, "
                            f"phase_id={phase_id}"
                        )
                        # Adjust worker pool (this also updates phase_id, but we already did above)
                        await worker_pool.start_workers(new_workers_per_core, new_object_key, phase_id)
                        current_workers_per_core = new_workers_per_core

                    last_check_time = current_time

                # Periodic flush to disk to free memory
                if (current_time - last_flush_time) >= flush_interval:
                    records = worker_pool.get_records()
                    if len(records) > 0:
                        # CRITICAL: Use worker_pool.current_phase_id, NOT local phase_id variable
                        # This ensures file tagging matches the actual records inside
                        current_phase_for_records = worker_pool.current_phase_id or phase_id

                        # Use WARNING level so it shows in main log
                        process_logger.warning(f"Process {process_id}: Periodic flush of {len(records)} records (phase={current_phase_for_records})")

                        # Save to process-specific parquet file (tagged with phase FROM RECORDS)
                        filename = f"benchmark_process{process_id}_phase_{current_phase_for_records}_{int(current_time)}"
                        filepath = persistence.save_records_to_parquet(records, filename)

                        if filepath:
                            # Send filepath to main process with phase tag FROM RECORDS
                            result_queue.put({
                                "type": "parquet_file",
                                "process_id": process_id,
                                "filepath": filepath,
                                "record_count": len(records),
                                "phase_id": current_phase_for_records  # Tag with ACTUAL phase in records
                            })

                            # Clear from memory
                            worker_pool.clear_records()

                        last_flush_time = current_time

                await asyncio.sleep(0.5)

            # Final flush
            process_logger.info(f"Process {process_id}: Final flush")
            await worker_pool.stop_workers()

            records = worker_pool.get_records()
            if len(records) > 0:
                # CRITICAL: Use phase_id from worker_pool to match records
                current_phase_for_records = worker_pool.current_phase_id or phase_id

                filename = f"benchmark_process{process_id}_phase_{current_phase_for_records}_final"
                filepath = persistence.save_records_to_parquet(records, filename)
                if filepath:
                    result_queue.put({
                        "type": "parquet_file",
                        "process_id": process_id,
                        "filepath": filepath,
                        "record_count": len(records),
                        "phase_id": current_phase_for_records  # Tag with ACTUAL phase in records
                    })

            await worker_pool.cleanup()
            process_logger.info(f"Process {process_id}: Cleanup complete")

    except Exception as e:
        process_logger.error(f"Process {process_id}: Error: {e}", exc_info=True)
        raise


class ProcessPool:
    """Process pool that spawns one process per CPU core."""

    def __init__(
        self,
        storage_type: str,
        persistence,
        instance_config: Dict[str, Any],
    ):
        """Initialize process pool.

        Args:
            storage_type: 'r2' or 's3'
            persistence: Main process persistence (for aggregated results)
            instance_config: Instance configuration from InstanceDetector
        """
        self.storage_type = storage_type
        self.persistence = persistence
        self.instance_config = instance_config
        self.cores = instance_config.get('vcpus', 1)

        # Multiprocessing
        mp_ctx = mp.get_context('spawn')
        # Increase queue size - with 36 processes flushing every 15s over many phases,
        # we can accumulate many messages. Make it unlimited to prevent blocking.
        self.result_queue: mp.Queue = mp_ctx.Queue(maxsize=0)  # 0 = unlimited
        self.stop_event: mp.Event = mp_ctx.Event()

        # Shared state for phase transitions (allows dynamic ramping)
        self.manager = mp.Manager()
        self.shared_phase_id = self.manager.Value('s', '')
        self.shared_object_key = self.manager.Value('s', '')
        self.shared_workers_per_core = self.manager.Value('i', 0)
        self.shared_total_workers = self.manager.Value('i', 0)
        self.shared_total_http_requests = self.manager.Value('i', 0)  # Total HTTP requests for metrics

        # State
        self.current_phase_id: Optional[str] = None
        self.current_object_key: Optional[str] = None
        self.current_workers_per_core: int = 0
        self.processes: List[mp.Process] = []

        # Collected parquet files
        self.parquet_files: List[str] = []

        logger.info(
            f"ProcessPool: Configured for {self.cores} cores"
        )

    async def execute_phase(
        self,
        workers_per_core: int,
        phase_id: str,
        duration_seconds: float
    ) -> Dict[str, Any]:
        """Execute a phase with given workers per core for specified duration.

        Args:
            workers_per_core: Number of async workers per core (not total)
            phase_id: Phase identifier
            duration_seconds: How long to run this phase

        Returns:
            Statistics for this phase
        """
        # Validation
        if workers_per_core <= 0:
            raise ValueError(f"workers_per_core must be positive, got {workers_per_core}")
        if duration_seconds <= 0:
            raise ValueError(f"duration_seconds must be positive, got {duration_seconds}")
        if not phase_id:
            raise ValueError("phase_id cannot be empty")

        total_workers = workers_per_core * self.cores
        pipeline_depth = self.instance_config.get('pipeline_depth', 3)
        total_http_requests = total_workers * pipeline_depth

        logger.info(
            f"Executing phase '{phase_id}': "
            f"{workers_per_core} workers/core × {self.cores} cores = "
            f"{total_workers} total workers, "
            f"{total_http_requests} concurrent HTTP requests ({pipeline_depth}× pipeline), "
            f"duration={duration_seconds}s"
        )

        try:
            # Start workers (or adjust if already running)
            await self.start_workers(workers_per_core, self.current_object_key or "", phase_id)

            # Wait for phase duration with progress logging
            start_time = time.time()
            check_interval = 5.0  # Check every 5s

            while (time.time() - start_time) < duration_seconds:
                remaining = duration_seconds - (time.time() - start_time)
                await asyncio.sleep(min(check_interval, remaining))

                # Log progress every 30s
                elapsed = time.time() - start_time
                if int(elapsed) % 30 == 0 and elapsed > 0:
                    logger.info(f"Phase '{phase_id}': {elapsed:.0f}s / {duration_seconds:.0f}s elapsed")

            # Phase complete - force flush from all processes
            logger.info(f"Phase '{phase_id}' duration complete, forcing flush...")

            # Signal flush by updating phase ID with _flush suffix
            flush_phase = f"{phase_id}_flush"
            self.shared_phase_id.value = flush_phase

            # Wait for processes to detect flush signal and flush
            # Increased from 3s to 10s to handle memory pressure and 36 processes
            logger.info(f"Waiting 10 seconds for {self.cores} processes to flush...")
            await asyncio.sleep(10.0)

            # Restore actual phase ID
            self.shared_phase_id.value = phase_id

            # Collect stats for this phase (with retry logic)
            stats = self.get_step_stats(phase_id)

            if stats:
                logger.info(
                    f"Phase '{phase_id}' complete: "
                    f"{stats['throughput_gbps']:.2f} Gbps, "
                    f"{stats['successful_requests']}/{stats['total_requests']} requests, "
                    f"error_rate={stats['error_rate']:.1%}"
                )
            else:
                logger.warning(f"No stats available for phase '{phase_id}'")
                stats = {
                    "phase_id": phase_id,
                    "throughput_gbps": 0.0,
                    "total_requests": 0,
                    "successful_requests": 0,
                    "error_rate": 1.0,
                    "duration_seconds": duration_seconds,
                }

            return stats

        except Exception as e:
            logger.error(f"Phase '{phase_id}' failed: {e}", exc_info=True)

            # Try to collect partial stats
            try:
                stats = self.get_step_stats(phase_id)
                if stats:
                    stats['error'] = str(e)
                    stats['partial'] = True
                    return stats
            except:
                pass

            # Return error stats
            return {
                "phase_id": phase_id,
                "error": str(e),
                "throughput_gbps": 0.0,
                "total_requests": 0,
                "successful_requests": 0,
                "error_rate": 1.0,
                "duration_seconds": duration_seconds,
            }

    async def start_workers(
        self,
        workers_per_core: int,
        object_key: str,
        phase_id: str
    ) -> None:
        """Start workers across all cores.

        Args:
            workers_per_core: Number of async workers per core
            object_key: Object key to download
            phase_id: Phase identifier
        """
        self.current_workers_per_core = workers_per_core
        self.current_object_key = object_key
        self.current_phase_id = phase_id

        total_workers = self.cores * workers_per_core
        pipeline_depth = self.instance_config.get('pipeline_depth', 3)
        total_http_requests = total_workers * pipeline_depth

        # Check if processes are already running (ramp-up)
        if self.processes:
            alive_count = sum(1 for p in self.processes if p.is_alive())
            logger.info(f"Process check: {alive_count}/{len(self.processes)} processes alive")

            if not all(p.is_alive() for p in self.processes):
                logger.error(
                    f"⚠️ PROCESS FAILURE: Only {alive_count}/{len(self.processes)} processes alive! "
                    f"Cannot safely ramp. Stopping benchmark."
                )
                raise RuntimeError(f"Process failure detected: {alive_count}/{len(self.processes)} alive")

            logger.info(
                f"Ramp: Adjusting all {self.cores} cores to {workers_per_core} workers/core "
                f"(total_workers={total_workers}, total_http_requests={total_http_requests})"
            )

            # Update shared state - all processes will pick up new values
            self.shared_phase_id.value = phase_id
            self.shared_object_key.value = object_key
            self.shared_workers_per_core.value = workers_per_core
            self.shared_total_workers.value = total_workers
            self.shared_total_http_requests.value = total_http_requests

            # Wait a moment for all processes to pick up the phase change
            # This prevents records from old phase ending up in new phase files
            logger.info(f"Waiting 3 seconds for phase_id='{phase_id}' to propagate to all processes...")
            await asyncio.sleep(3.0)

            logger.info(f"Ramp complete: all cores now have {workers_per_core} workers/core with phase='{phase_id}'")
            return

        # First time: spawn all processes (one per core)
        logger.info(
            f"Starting {self.cores} cores with {workers_per_core} workers/core "
            f"(total_workers={total_workers}, total_http_requests={total_http_requests})"
        )

        # Initialize shared state
        self.shared_phase_id.value = phase_id
        self.shared_object_key.value = object_key
        self.shared_workers_per_core.value = workers_per_core
        self.shared_total_workers.value = total_workers
        self.shared_total_http_requests.value = total_http_requests

        # Clear stop event
        self.stop_event.clear()

        # Spawn processes (one per core)
        self.processes = []
        for i in range(self.cores):
            process = mp.Process(
                target=_run_worker_process,
                args=(
                    i,
                    self.storage_type,
                    object_key,
                    workers_per_core,
                    phase_id,
                    float('inf'),  # Run until stopped
                    self.instance_config,
                    self.result_queue,
                    self.stop_event,
                    self.shared_phase_id,
                    self.shared_object_key,
                    self.shared_workers_per_core,
                    self.shared_total_workers,
                    self.shared_total_http_requests
                )
            )
            process.start()
            self.processes.append(process)

        logger.info(f"All {self.cores} cores started with {workers_per_core} workers/core")

    def get_step_stats(self, phase_id: str) -> Optional[Dict[str, Any]]:
        """Get statistics for a phase.

        This is called after a phase completes to get aggregated stats.
        Since records are on disk, this loads and analyzes parquet files.
        """
        # Collect any pending parquet files from queue (with retry)
        import queue
        import time as time_module

        # Retry collection for up to 5 seconds (handles delayed queue messages)
        retry_deadline = time_module.time() + 5.0
        files_before = len(self.parquet_files)

        while time_module.time() < retry_deadline:
            collected_this_round = 0
            while not self.result_queue.empty():
                try:
                    msg = self.result_queue.get_nowait()
                    if msg.get("type") == "parquet_file":
                        filepath = msg.get("filepath")
                        msg_phase = msg.get("phase_id", "unknown")

                        if filepath and os.path.exists(filepath):
                            # Store as dict with phase tag
                            file_info = {
                                'path': filepath,
                                'phase_id': msg_phase,
                                'record_count': msg.get("record_count", 0)
                            }
                            # Check if not already added
                            if not any(f['path'] == filepath for f in self.parquet_files):
                                self.parquet_files.append(file_info)
                                collected_this_round += 1
                except queue.Empty:
                    break

            # If we collected files this round, keep trying
            if collected_this_round > 0:
                logger.debug(f"Collected {collected_this_round} more files, checking for more...")
                time_module.sleep(0.5)
            else:
                # No new files, exit early
                break

        files_collected = len(self.parquet_files) - files_before
        logger.info(f"Collected {files_collected} parquet files for phase '{phase_id}' (total accumulated: {len(self.parquet_files)})")

        if not self.parquet_files:
            logger.warning(f"No parquet files collected for phase {phase_id}")
            return None

        # Load and analyze parquet files (only for this phase)
        from common.metrics_utils import calculate_phase_throughput_with_prorating, calculate_latency_stats

        # Debug: show phase distribution
        phase_counts = {}
        for f in self.parquet_files:
            fp = f.get('phase_id', 'unknown')
            phase_counts[fp] = phase_counts.get(fp, 0) + 1
        logger.info(f"File phase distribution: {phase_counts}")

        dfs = []
        files_loaded = 0
        files_checked = 0
        files_skipped = 0
        for file_info in self.parquet_files:
            file_phase = file_info.get('phase_id', '')
            filepath = file_info.get('path', '')

            # Match by phase_id tag or filename contains phase_id
            if not (file_phase == phase_id or f"_phase_{phase_id}" in filepath or f"_phase_{phase_id}_" in filepath):
                files_skipped += 1
                continue

            # File matches - try to load it
            files_checked += 1

            try:
                df = pd.read_parquet(filepath)
                # Check what phase_ids are actually in the file
                unique_phases = df['phase_id'].unique() if 'phase_id' in df.columns else []

                # Log first 3 files to see what's inside
                if files_checked <= 3:
                    logger.warning(f"File {os.path.basename(filepath)}: contains phases {list(unique_phases)}, looking for '{phase_id}', records={len(df)}")

                # Additional filter by phase_id column
                phase_df = df[df['phase_id'] == phase_id]
                if len(phase_df) > 0:
                    dfs.append(phase_df)
                    files_loaded += 1
                    if files_checked <= 3:
                        logger.warning(f"  ✓ Loaded {len(phase_df)} records from this file")
                else:
                    # Log ALL mismatches (this is the bug we're hunting)
                    if files_checked <= 10:  # Log first 10 mismatches
                        logger.warning(f"  ✗ File tagged as '{file_phase}' contains phases {list(unique_phases)}, NOT '{phase_id}'")

            except Exception as e:
                logger.error(f"Error loading {filepath}: {e}")

        logger.info(f"Phase '{phase_id}': Checked {files_checked} files, skipped {files_skipped}, loaded {files_loaded} with matching data")

        if not dfs:
            logger.warning(f"No data found for phase {phase_id}")
            return None

        # Concatenate all data
        records_df = pd.concat(dfs, ignore_index=True)

        # Calculate stats
        successful_df = records_df[records_df['http_status'] == 200]
        total_requests = len(records_df)
        successful_requests = len(successful_df)
        error_rate = 1.0 - (successful_requests / total_requests) if total_requests > 0 else 1.0

        if len(successful_df) == 0:
            return {
                "phase_id": phase_id,
                "total_http_requests": 0,
                "total_requests": total_requests,
                "successful_requests": 0,
                "error_requests": total_requests,
                "error_rate": 1.0,
                "throughput_gbps": 0.0,
                "duration_seconds": 0.0,
                "avg_latency_ms": 0.0,
                "p50_latency_ms": 0.0,
                "p95_latency_ms": 0.0,
                "p99_latency_ms": 0.0,
                "total_bytes": 0,
            }

        # Calculate throughput and latency
        throughput_result = calculate_phase_throughput_with_prorating(successful_df, phase_id)
        latency_stats = calculate_latency_stats(successful_df)

        return {
            "phase_id": phase_id,
            "total_http_requests": successful_df['concurrency'].iloc[0] if len(successful_df) > 0 else 0,
            "total_requests": total_requests,
            "successful_requests": successful_requests,
            "error_requests": total_requests - successful_requests,
            "error_rate": error_rate,
            "throughput_gbps": throughput_result['throughput_gbps'],
            "duration_seconds": throughput_result['duration_seconds'],
            "avg_latency_ms": latency_stats["avg"],
            "p50_latency_ms": latency_stats["p50"],
            "p95_latency_ms": latency_stats["p95"],
            "p99_latency_ms": latency_stats["p99"],
            "total_bytes": int(successful_df['bytes'].sum()),
        }

    async def cleanup(self):
        """Stop all processes and cleanup."""
        logger.info("Stopping all processes...")

        # Signal stop
        self.stop_event.set()

        # Wait for processes
        for i, process in enumerate(self.processes):
            process.join(timeout=30)
            if process.is_alive():
                logger.warning(f"Process {i} did not stop gracefully, terminating")
                process.terminate()
                process.join()
            logger.info(f"Process {i} stopped")

        # Collect any remaining parquet files
        import queue
        while not self.result_queue.empty():
            try:
                msg = self.result_queue.get_nowait()
                if msg.get("type") == "parquet_file":
                    filepath = msg.get("filepath")
                    msg_phase = msg.get("phase_id", "unknown")

                    if filepath and os.path.exists(filepath):
                        file_info = {
                            'path': filepath,
                            'phase_id': msg_phase,
                            'record_count': msg.get("record_count", 0)
                        }
                        # Check if not already added
                        if not any(f['path'] == filepath for f in self.parquet_files):
                            self.parquet_files.append(file_info)
            except queue.Empty:
                break

        logger.info(f"Collected {len(self.parquet_files)} parquet files from all cores")
        logger.info("ProcessPool cleanup complete")
