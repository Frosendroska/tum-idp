"""
Simple Prometheus metrics exporter for the R2 benchmark.
"""

import logging
from prometheus_client import start_http_server, Counter, Histogram, Gauge

logger = logging.getLogger(__name__)


class SimplePrometheusExporter:
    """Simple Prometheus metrics exporter."""
    
    def __init__(self, port: int = 9100):
        self.port = port
        self.server_started = False
        
        # Define metrics
        self.requests_total = Counter('r2_benchmark_requests_total', 'Total requests', ['status'])
        self.request_duration = Histogram('r2_benchmark_request_duration_seconds', 'Request duration')
        self.bytes_downloaded = Counter('r2_benchmark_bytes_downloaded_total', 'Total bytes downloaded')
        self.throughput = Gauge('r2_benchmark_throughput_mbps', 'Current throughput in Mbps')
        self.concurrency = Gauge('r2_benchmark_concurrency', 'Current concurrency level')
    
    def start_server(self):
        """Start the Prometheus HTTP server."""
        if not self.server_started:
            try:
                start_http_server(self.port)
                self.server_started = True
                logger.info(f"Prometheus server started on port {self.port}")
            except Exception as e:
                logger.error(f"Failed to start Prometheus server: {e}")
    
    def record_request(self, status: int, duration_seconds: float, bytes_downloaded: int):
        """Record a request metric."""
        try:
            self.requests_total.labels(status=str(status)).inc()
            self.request_duration.observe(duration_seconds)
            self.bytes_downloaded.inc(bytes_downloaded)
        except Exception as e:
            logger.error(f"Failed to record request metric: {e}")
    
    def update_throughput(self, throughput_mbps: float):
        """Update throughput metric."""
        try:
            self.throughput.set(throughput_mbps)
        except Exception as e:
            logger.error(f"Failed to update throughput metric: {e}")
    
    def update_concurrency(self, concurrency: int):
        """Update concurrency metric."""
        try:
            self.concurrency.set(concurrency)
        except Exception as e:
            logger.error(f"Failed to update concurrency metric: {e}")
