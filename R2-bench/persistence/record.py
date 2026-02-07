"""
Data structures for the R2 benchmark.
"""

import time
from dataclasses import dataclass, field


@dataclass
class BenchmarkRecord:
    """Immutable data structure for benchmark records.

    Attributes:
        thread_id: ID of the worker thread
        conn_id: ID of the connection
        object_key: S3/R2 object key being accessed
        range_start: Start byte position of the range request
        range_len: Length of the range request in bytes
        bytes: Number of bytes successfully downloaded
        latency_ms: Total latency from request start to completion (ms)
        rtt_ms: Round-trip time to first byte (ms)
        http_status: HTTP status code of the response
        concurrency: Total concurrent HTTP requests in flight (= total_workers × pipeline_depth)
        phase_id: Identifier for the benchmark phase
        start_ts: Request start timestamp (Unix epoch)
        end_ts: Request end timestamp (Unix epoch)
    """

    thread_id: int
    conn_id: int
    object_key: str
    range_start: int
    range_len: int
    bytes: int  # bytes_downloaded renamed to bytes for consistency
    latency_ms: float
    rtt_ms: float
    http_status: int
    concurrency: int  # Total concurrent HTTP requests (workers × cores × pipeline_depth)
    phase_id: str = ""
    start_ts: float = field(default_factory=time.time)
    end_ts: float = field(default_factory=time.time)
