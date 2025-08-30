"""
Simple Prometheus metrics scraper for the R2 benchmark.
"""

import requests
import logging
import time

logger = logging.getLogger(__name__)


class SimplePrometheusScraper:
    """Simple Prometheus metrics scraper."""
    
    def __init__(self, endpoint: str = "http://localhost:9100"):
        self.endpoint = endpoint
        self.history = []
        self.is_running = False
        
        logger.info(f"Initialized Prometheus scraper for {endpoint}")
    
    def start_scraping(self, interval_seconds: int = 10):
        """Start scraping metrics at regular intervals."""
        if self.is_running:
            logger.warning("Scraper already running")
            return
        
        self.is_running = True
        logger.info(f"Started scraping metrics every {interval_seconds} seconds")
        
        try:
            while self.is_running:
                metrics = self.scrape_metrics()
                if metrics:
                    self.history.append({
                        'timestamp': time.time(),
                        'metrics': metrics
                    })
                
                time.sleep(interval_seconds)
        except KeyboardInterrupt:
            logger.info("Scraping stopped by user")
        except Exception as e:
            logger.error(f"Error during scraping: {e}")
        finally:
            self.is_running = False
    
    def stop_scraping(self):
        """Stop scraping metrics."""
        self.is_running = False
        logger.info("Stopped scraping metrics")
    
    def scrape_metrics(self):
        """Scrape metrics from Prometheus endpoint."""
        try:
            response = requests.get(f"{self.endpoint}/metrics", timeout=5)
            if response.status_code == 200:
                return self._parse_metrics(response.text)
            else:
                logger.warning(f"Failed to scrape metrics: {response.status_code}")
                return None
        except Exception as e:
            logger.error(f"Error scraping metrics: {e}")
            return None
    
    def _parse_metrics(self, metrics_text: str):
        """Parse Prometheus metrics text."""
        metrics = {}
        
        for line in metrics_text.split('\n'):
            if line.startswith('#') or not line.strip():
                continue
            
            try:
                # Simple parsing for basic metrics
                if 'r2_benchmark_requests_total' in line:
                    parts = line.split(' ')
                    if len(parts) >= 2:
                        metrics['requests_total'] = float(parts[-1])
                
                elif 'r2_benchmark_throughput_mbps' in line:
                    parts = line.split(' ')
                    if len(parts) >= 2:
                        metrics['throughput_mbps'] = float(parts[-1])
                
                elif 'r2_benchmark_concurrency' in line:
                    parts = line.split(' ')
                    if len(parts) >= 2:
                        metrics['concurrency'] = float(parts[-1])
                        
            except Exception as e:
                logger.debug(f"Failed to parse metric line '{line}': {e}")
        
        return metrics
    
    def get_metric_value(self, metric_name: str):
        """Get the latest value for a specific metric."""
        if not self.history:
            return None
        
        latest = self.history[-1]['metrics']
        return latest.get(metric_name)
    
    def get_metric_history(self, metric_name: str, limit: int = 100):
        """Get history of values for a specific metric."""
        history = []
        
        for entry in self.history[-limit:]:
            if metric_name in entry['metrics']:
                history.append({
                    'timestamp': entry['timestamp'],
                    'value': entry['metrics'][metric_name]
                })
        
        return history
