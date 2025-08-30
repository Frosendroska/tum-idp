"""
Simple Parquet file persistence for the R2 benchmark.
"""

import pandas as pd
import os
import logging
from datetime import datetime
from .base import BenchmarkRecord

logger = logging.getLogger(__name__)


class SimpleParquetPersistence:
    """Simple Parquet file persistence."""
    
    def __init__(self, output_dir: str = "results"):
        self.output_dir = output_dir
        self.records = []
        
        # Ensure output directory exists
        os.makedirs(output_dir, exist_ok=True)
    
    def store_record(self, record: BenchmarkRecord):
        """Store a benchmark record."""
        self.records.append(record)
    
    def save_to_file(self, filename_prefix: str = "benchmark"):
        """Save records to Parquet file."""
        if not self.records:
            return None
        
        # Convert records to DataFrame
        data = []
        for record in self.records:
            data.append({
                'ts': record.ts,
                'thread_id': record.thread_id,
                'conn_id': record.conn_id,
                'object_key': record.object_key,
                'range_start': record.range_start,
                'range_len': record.range_len,
                'bytes': record.bytes,
                'latency_ms': record.latency_ms,
                'http_status': record.http_status,
                'concurrency': record.concurrency
            })
        
        df = pd.DataFrame(data)
        
        # Generate filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{filename_prefix}_{timestamp}.parquet"
        filepath = os.path.join(self.output_dir, filename)
        
        # Save to Parquet
        df.to_parquet(filepath, index=False)
        
        return filepath
