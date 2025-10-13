"""
Simple plateau check algorithm for the R2 benchmark.
"""

import logging
from configuration import PLATEAU_THRESHOLD

logger = logging.getLogger(__name__)


class PlateauCheck:
    """Algorithm to check if throughput has plateaued or system bandwidth limit is reached."""
    
    def __init__(self, threshold: float = None, system_bandwidth_mbps: float = 0):
        self.threshold = threshold or PLATEAU_THRESHOLD
        self.system_bandwidth_mbps = system_bandwidth_mbps
        self.measurements = []
        logger.info(f"Initialized plateau checker with {self.threshold*100}% threshold, system bandwidth limit: {system_bandwidth_mbps} Mbps")
    
    def add_measurement(self, concurrency: int, throughput_mbps: float, duration_seconds: float):
        """Add a measurement."""
        self.measurements.append({
            'concurrency': concurrency,
            'throughput_mbps': throughput_mbps,
            'duration_seconds': duration_seconds
        })
        logger.debug(f"Added measurement: {concurrency} conn -> {throughput_mbps:.1f} Mbps")
    
    def is_plateau_reached(self) -> tuple:
        """Check if plateau is reached or system bandwidth limit is hit."""
        if len(self.measurements) < 1:
            return False, "Not enough measurements"
        
        # Check system bandwidth limit first
        if self.system_bandwidth_mbps > 0:
            latest_measurement = self.measurements[-1]
            total_throughput = latest_measurement['throughput_mbps']
            
            if total_throughput >= self.system_bandwidth_mbps:
                return True, f"System bandwidth limit reached: {total_throughput:.1f} Mbps >= {self.system_bandwidth_mbps} Mbps limit"
        
        # Check for plateau (need at least 5 measurements)
        if len(self.measurements) < 5:
            return False, "Not enough measurements for plateau detection"
        
        # Get last 5 measurements
        recent = self.measurements[-5:]
        
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
