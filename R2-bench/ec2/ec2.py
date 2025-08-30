"""
EC2 instance monitoring functionality.
"""

import psutil
import logging

logger = logging.getLogger(__name__)


class EC2Monitor:
    """Monitor EC2 instance performance metrics."""
    
    def __init__(self):
        self.instance_type = self._detect_instance_type()
        logger.info(f"Initialized EC2 monitor for {self.instance_type}")
    
    def _detect_instance_type(self):
        """Detect EC2 instance type."""
        try:
            # Try to get from metadata service
            import requests
            response = requests.get('http://169.254.169.254/latest/meta-data/instance-type', timeout=1)
            return response.text
        except:
            return "unknown"
    
    def get_current_metrics(self):
        """Get current system metrics."""
        try:
            # CPU and memory
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            
            # Network stats
            net_io = psutil.net_io_counters()
            bytes_sent = net_io.bytes_sent
            bytes_recv = net_io.bytes_recv
            
            return {
                'instance_type': self.instance_type,
                'cpu_percent': cpu_percent,
                'memory_percent': memory.percent,
                'bytes_sent': bytes_sent,
                'bytes_recv': bytes_recv
            }
        except Exception as e:
            logger.error(f"Failed to get metrics: {e}")
            return {}
    
    def get_health_summary(self):
        """Get system health summary."""
        metrics = self.get_current_metrics()
        
        if not metrics:
            return {'status': 'unknown'}
        
        # Simple health check
        if metrics.get('cpu_percent', 0) > 90 or metrics.get('memory_percent', 0) > 90:
            status = 'degraded'
        else:
            status = 'healthy'
        
        return {
            'status': status,
            'instance_type': metrics.get('instance_type', 'unknown'),
            'cpu_usage': f"{metrics.get('cpu_percent', 0):.1f}%",
            'memory_usage': f"{metrics.get('memory_percent', 0):.1f}%"
        }
