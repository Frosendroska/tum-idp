"""
Simple plateau check algorithm for the R2 benchmark.
"""

import logging

logger = logging.getLogger(__name__)


class SimplePlateauCheck:
    """Simple algorithm to check if throughput has plateaued."""
    
    def __init__(self, threshold: float = 0.05):
        self.threshold = threshold
        self.measurements = []
        logger.info(f"Initialized plateau checker with {threshold*100}% threshold")
    
    def add_measurement(self, concurrency: int, throughput_mbps: float, duration_seconds: float):
        """Add a measurement."""
        self.measurements.append({
            'concurrency': concurrency,
            'throughput_mbps': throughput_mbps,
            'duration_seconds': duration_seconds
        })
        logger.debug(f"Added measurement: {concurrency} conn -> {throughput_mbps:.1f} Mbps")
    
    def is_plateau_reached(self) -> tuple:
        """Check if plateau is reached."""
        if len(self.measurements) < 3:
            return False, "Not enough measurements"
        
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
