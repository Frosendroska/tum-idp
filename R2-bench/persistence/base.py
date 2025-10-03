"""
Basic data structures for the R2 benchmark.
"""

import time


class BenchmarkRecord:
    """Data structure for benchmark records."""
    
    def __init__(self, thread_id, conn_id, object_key, range_start, range_len, 
                 bytes_downloaded, latency_ms, http_status, concurrency, 
                 phase_id: str = "", start_ts: float = None, end_ts: float = None):
        self.ts = time.time()  # Record creation timestamp
        self.thread_id = thread_id
        self.conn_id = conn_id
        self.object_key = object_key
        self.range_start = range_start
        self.range_len = range_len
        self.bytes = bytes_downloaded
        self.latency_ms = latency_ms
        self.http_status = http_status
        self.concurrency = concurrency
        self.phase_id = phase_id
        self.start_ts = start_ts or time.time()
        self.end_ts = end_ts or time.time()


class SimpleMetricsCollector:
    """Simple metrics collection."""
    
    def __init__(self):
        self.records = []
    
    def add_record(self, record):
        """Add a benchmark record."""
        self.records.append(record)
    
    def get_summary(self):
        """Get basic summary statistics."""
        if not self.records:
            return {}
        
        total_requests = len(self.records)
        successful_requests = sum(1 for r in self.records if r.http_status == 200)
        total_bytes = sum(r.bytes for r in self.records if r.http_status == 200)
        total_latency = sum(r.latency_ms for r in self.records if r.http_status == 200)
        
        return {
            'total_requests': total_requests,
            'successful_requests': successful_requests,
            'success_rate': successful_requests / total_requests if total_requests > 0 else 0,
            'total_bytes': total_bytes,
            'avg_latency_ms': total_latency / successful_requests if successful_requests > 0 else 0
        }
