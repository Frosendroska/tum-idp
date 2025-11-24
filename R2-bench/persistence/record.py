"""
Basic data structures for the R2 benchmark.
"""

import time


class BenchmarkRecord:
    """Data structure for benchmark records."""
    
    def __init__(self, thread_id, conn_id, object_key, range_start, range_len, 
                 bytes_downloaded, latency_ms, http_status, concurrency, 
                 phase_id: str = "", start_ts: float = None, end_ts: float = None):
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
