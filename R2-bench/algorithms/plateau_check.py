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
        """Check if plateau is reached, degradation detected, or system bandwidth limit is hit."""
        if len(self.measurements) < 1:
            return False, "Not enough measurements"
        
        # Check system bandwidth limit first
        if self.system_bandwidth_mbps > 0:
            latest_measurement = self.measurements[-1]
            total_throughput = latest_measurement['throughput_mbps']
            
            if total_throughput >= self.system_bandwidth_mbps:
                return True, f"System bandwidth limit reached: {total_throughput:.1f} Mbps >= {self.system_bandwidth_mbps} Mbps limit"
        
        # Find peak throughput so far
        peak_throughput = max(m['throughput_mbps'] for m in self.measurements)
        latest_throughput = self.measurements[-1]['throughput_mbps']
        
        # Check for significant degradation from peak (more robust than consecutive comparison)
        if peak_throughput > 0:
            degradation_from_peak = (peak_throughput - latest_throughput) / peak_throughput
            if degradation_from_peak > 0.2:
                return True, f"Significant degradation from peak: {degradation_from_peak:.1%} drop (peak: {peak_throughput:.1f} -> current: {latest_throughput:.1f} Mbps)"
        
        # Check for plateau (need at least 3 measurements)
        if len(self.measurements) < 3:
            return False, "Not enough measurements for plateau detection"
        
        # Get last 3 measurements
        recent = self.measurements[-3:]
        
        # Calculate improvement/degradation between consecutive measurements
        changes = []
        for i in range(1, len(recent)):
            prev_throughput = recent[i-1]['throughput_mbps']
            curr_throughput = recent[i]['throughput_mbps']
            
            if prev_throughput > 0:
                change = (curr_throughput - prev_throughput) / prev_throughput
                changes.append(change)
        
        # Check if all improvements are below threshold
        if changes and all(abs(change) < self.threshold for change in changes):
            return True, f"Throughput improvement below {self.threshold*100}% threshold"
        
        # Check for consecutive degradation (after improvements check)
        # If all recent steps show degradation > 10%, stop
        if changes and all(change < -0.1 for change in changes):
            avg_degradation = sum(abs(change) for change in changes) / len(changes)
            return True, f"Consistent degradation detected: {avg_degradation:.1%} average drop over last {len(changes)} steps"
        
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
