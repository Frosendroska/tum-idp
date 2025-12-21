"""
Parquet persistence for benchmark results.
"""

import os
import logging
from typing import List, Optional
from datetime import datetime

import pandas as pd

from persistence.record import BenchmarkRecord

logger = logging.getLogger(__name__)


class ParquetPersistence:
    """Thread-safe Parquet file persistence for benchmark records.

    This class stores benchmark records in memory and provides functionality
    to save them to Parquet files for later analysis.

    Attributes:
        output_dir: Directory where Parquet files will be saved
        records: List of benchmark records accumulated during the benchmark
    """

    def __init__(self, output_dir: str = "results"):
        """Initialize Parquet persistence.

        Args:
            output_dir: Directory for saving Parquet files (default: 'results')
        """
        self.output_dir: str = output_dir
        self.records: List[BenchmarkRecord] = []

        # Ensure output directory exists
        os.makedirs(output_dir, exist_ok=True)

    def store_record(self, record: BenchmarkRecord) -> None:
        """Store a benchmark record in memory.

        Args:
            record: Benchmark record to store
        """
        self.records.append(record)

    def save_to_file(self, filename_prefix: str = "benchmark") -> Optional[str]:
        """Save all records to a Parquet file.

        Args:
            filename_prefix: Prefix for the generated filename (default: 'benchmark')

        Returns:
            Path to the saved file, or None if no records to save
        """
        if not self.records:
            return None

        logger.info(f"Saving {len(self.records)} records to file")
        # Convert records to DataFrame
        data = []
        for record in self.records:
            data.append({
                'thread_id': record.thread_id,
                'conn_id': record.conn_id,
                'object_key': record.object_key,
                'range_start': record.range_start,
                'range_len': record.range_len,
                'bytes': record.bytes,
                'latency_ms': record.latency_ms,
                'rtt_ms': record.rtt_ms,
                'http_status': record.http_status,
                'concurrency': record.concurrency,
                'phase_id': record.phase_id,
                'start_ts': record.start_ts,
                'end_ts': record.end_ts
            })
        
        df = pd.DataFrame(data)
        
        # Generate filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{filename_prefix}_{timestamp}.parquet"
        filepath = os.path.join(self.output_dir, filename)
        
        # Save to Parquet
        df.to_parquet(filepath, index=False)
        
        return filepath
