"""
Simple Grafana setup for the R2 benchmark.
"""

import logging

logger = logging.getLogger(__name__)


class SimpleGrafanaSetup:
    """Simple Grafana setup for monitoring R2 benchmark."""
    
    def __init__(self, prometheus_url: str = "http://localhost:9100"):
        self.prometheus_url = prometheus_url
        
        logger.info(f"Initialized Grafana setup for Prometheus at {prometheus_url}")
    
    def get_dashboard_config(self):
        """Get basic dashboard configuration."""
        return {
            'title': 'R2 Benchmark Dashboard',
            'panels': [
                {
                    'title': 'Throughput',
                    'type': 'graph',
                    'targets': [
                        {
                            'expr': 'r2_benchmark_throughput_mbps',
                            'legendFormat': 'Throughput (Mbps)'
                        }
                    ]
                },
                {
                    'title': 'Requests',
                    'type': 'graph',
                    'targets': [
                        {
                            'expr': 'r2_benchmark_requests_total',
                            'legendFormat': 'Total Requests'
                        }
                    ]
                },
                {
                    'title': 'Concurrency',
                    'type': 'graph',
                    'targets': [
                        {
                            'expr': 'r2_benchmark_concurrency',
                            'legendFormat': 'Current Concurrency'
                        }
                    ]
                }
            ]
        }
    
    def get_setup_instructions(self):
        """Get setup instructions for Grafana."""
        return f"""
Grafana Setup Instructions for R2 Benchmark
==========================================

1. Install Grafana (if not already installed)
2. Add Prometheus as a data source:
   - URL: {self.prometheus_url}
   - Access: Server (default)

3. Import the dashboard configuration:
   - Use the configuration from get_dashboard_config()

4. The dashboard will show:
   - Real-time throughput
   - Request counts
   - Current concurrency levels

5. Metrics are available at: {self.prometheus_url}/metrics
        """
