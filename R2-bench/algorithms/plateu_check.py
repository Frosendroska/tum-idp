"""
Simple plateau check algorithm for the R2 benchmark.
"""

import logging
from configuration import PLATEAU_THRESHOLD

logger = logging.getLogger(__name__)


class PlateauCheck:
    """Algorithm to check if throughput has plateaued or worker bandwidth is reached."""
    
    def __init__(self, threshold: float = None, worker_bandwidth_mbps: float = 0):
        self.threshold = threshold or PLATEAU_THRESHOLD
        self.worker_bandwidth_mbps = worker_bandwidth_mbps
        self.measurements = []
        logger.info(f"Initialized plateau checker with {self.threshold*100}% threshold, worker bandwidth limit: {worker_bandwidth_mbps} Mbps")
    
    def add_measurement(self, concurrency: int, throughput_mbps: float, duration_seconds: float):
        """Add a measurement."""
        self.measurements.append({
            'concurrency': concurrency,
            'throughput_mbps': throughput_mbps,
            'duration_seconds': duration_seconds
        })
        logger.debug(f"Added measurement: {concurrency} conn -> {throughput_mbps:.1f} Mbps")
    
    def is_plateau_reached(self) -> tuple:
        """Check if plateau is reached or worker bandwidth limit is hit."""
        if len(self.measurements) < 1:
            return False, "Not enough measurements"
        
        # Check worker bandwidth limit first
        if self.worker_bandwidth_mbps > 0:
            latest_measurement = self.measurements[-1]
            concurrency = latest_measurement['concurrency']
            total_throughput = latest_measurement['throughput_mbps']
            
            # Calculate per-worker throughput
            per_worker_throughput = total_throughput / concurrency if concurrency > 0 else 0
            
            if per_worker_throughput >= self.worker_bandwidth_mbps:
                return True, f"Worker bandwidth limit reached: {per_worker_throughput:.1f} Mbps per worker >= {self.worker_bandwidth_mbps} Mbps limit"
        
        # Check for plateau (need at least 3 measurements)
        if len(self.measurements) < 3:
            return False, "Not enough measurements for plateau detection"
        
        # Get last 3 measurements
        recent = self.measurements[-3:]
        
        # Calculate improvement between consecutive measurements
        improvements = []
        for i in range(1, len(recent)):
            prev_throughput = recent[i-1]['throughput_mbps']
            curr_throughput = recent[i]['throughput_mbps']
            
            if prev_throughput > 0:
                improvement = (curr_throughput - prev_throughput) / prev_throughput
                improvements.append(improvement)
        
        # Check if all improvements are below threshold
        if improvements and all(abs(imp) < self.threshold for imp in improvements):
            return True, f"Throughput improvement below {self.threshold*100}% threshold"
        
        return False, "Throughput still improving"
    
    def get_plateau_summary(self):
        """Get summary of plateau detection."""
        if not self.measurements:
            return {'status': 'no_measurements'}
        
        plateau_reached, reason = self.is_plateau_reached()
        
        return {
            'measurements_count': len(self.measurements),
            'plateau_reached': plateau_reached,
            'reason': reason,
            'last_measurement': self.measurements[-1] if self.measurements else None
        }
