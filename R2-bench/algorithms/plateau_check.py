"""
Plateau detection algorithm for R2 benchmark capacity discovery.

Detects three types of ceilings:
1. System bandwidth limit (instance NIC capacity)
2. Performance degradation (R2 throttling or overload)
3. Throughput plateau (marginal improvement despite increased concurrency)
"""

import logging
from typing import Tuple
from configuration import PLATEAU_THRESHOLD, PEAK_DEGRADATION_THRESHOLD

logger = logging.getLogger(__name__)


class PlateauCheck:
    """Algorithm to detect throughput ceiling via three mechanisms:

    1. Hard limit: System bandwidth ceiling (e.g., 100 Gbps instance)
    2. Degradation: Throughput drops from peak (R2 throttling/overload)
    3. Plateau: Marginal improvements (diminishing returns)
    """

    def __init__(self, threshold: float = None, system_bandwidth_gbps: float = 0):
        """Initialize plateau detector.

        Args:
            threshold: Minimum relative improvement to continue ramping (default: 5%)
            system_bandwidth_gbps: Instance bandwidth limit in Gbps (0 = no limit)
        """
        self.threshold = threshold or PLATEAU_THRESHOLD
        self.system_bandwidth_gbps = system_bandwidth_gbps
        self.measurements = []

        # How close to system limit before we consider it "reached" (95% of limit)
        self.system_limit_margin = 0.95

        logger.info(
            f"Initialized plateau checker: "
            f"improvement_threshold={self.threshold*100:.1f}%, "
            f"degradation_threshold={PEAK_DEGRADATION_THRESHOLD*100:.0f}%, "
            f"system_limit={system_bandwidth_gbps} Gbps"
        )
    
    def add_measurement(self, concurrency: int, throughput_gbps: float, duration_seconds: float):
        """Add a measurement."""
        self.measurements.append({
            'concurrency': concurrency,
            'throughput_gbps': throughput_gbps,
            'duration_seconds': duration_seconds
        })
        logger.debug(f"Added measurement: {concurrency} conn -> {throughput_gbps:.2f} Gbps")
    
    def is_plateau_reached(self) -> Tuple[bool, str]:
        """Determine if throughput has reached its ceiling.

        Returns:
            Tuple of (plateau_reached: bool, reason: str)
        """
        if len(self.measurements) < 1:
            return False, "Not enough measurements"

        latest_measurement = self.measurements[-1]
        latest_throughput = latest_measurement['throughput_gbps']

        # === CHECK 1: System Bandwidth Limit (Instance Ceiling) ===
        if self.system_bandwidth_gbps > 0:
            # Consider "reached" if within 95% of limit (to account for overhead)
            effective_limit = self.system_bandwidth_gbps * self.system_limit_margin
            utilization = (latest_throughput / self.system_bandwidth_gbps) * 100

            if latest_throughput >= effective_limit:
                return True, (
                    f"System bandwidth ceiling reached: {latest_throughput:.2f} Gbps "
                    f"({utilization:.1f}% of {self.system_bandwidth_gbps} Gbps limit)"
                )

        # === CHECK 2: Performance Degradation (R2 Throttling or Overload) ===
        # Find peak throughput across all measurements
        peak_throughput = max(m['throughput_gbps'] for m in self.measurements)

        if peak_throughput > 0 and latest_throughput < peak_throughput:
            degradation = (peak_throughput - latest_throughput) / peak_throughput

            # Stop if throughput degraded by more than threshold
            if degradation > PEAK_DEGRADATION_THRESHOLD:
                return True, (
                    f"Performance degradation detected: {degradation:.1%} drop from peak "
                    f"(peak: {peak_throughput:.2f} Gbps → current: {latest_throughput:.2f} Gbps). "
                    f"Likely R2 throttling or system overload."
                )

        # === CHECK 3: Throughput Plateau (Diminishing Returns) ===
        # Need at least 2 measurements to calculate improvement
        if len(self.measurements) < 2:
            return False, "Insufficient measurements for plateau detection (need ≥2)"

        # Look at last 2 measurements to check recent improvement
        prev_measurement = self.measurements[-2]
        prev_throughput = prev_measurement['throughput_gbps']

        if prev_throughput > 0:
            improvement = (latest_throughput - prev_throughput) / prev_throughput

            # For more confidence, also check if we've had multiple low-improvement steps
            if len(self.measurements) >= 3:
                # Check last 2 consecutive improvements
                third_last = self.measurements[-3]
                third_throughput = third_last['throughput_gbps']

                if third_throughput > 0:
                    prev_improvement = (prev_throughput - third_throughput) / third_throughput

                    # Both recent steps show minimal improvement
                    if abs(improvement) < self.threshold and abs(prev_improvement) < self.threshold:
                        return True, (
                            f"Throughput plateau detected: last 2 steps improved by "
                            f"{improvement:.1%} and {prev_improvement:.1%} "
                            f"(both below {self.threshold*100:.0f}% threshold). "
                            f"Current: {latest_throughput:.2f} Gbps"
                        )

        # Still improving significantly
        if len(self.measurements) >= 2:
            improvement = ((latest_throughput - prev_throughput) / prev_throughput) if prev_throughput > 0 else 0
            return False, f"Throughput still improving: +{improvement:.1%} in last step"

        return False, "Throughput still improving"
    
    def get_plateau_summary(self) -> dict:
        """Get comprehensive summary of plateau detection results.

        Returns:
            Dictionary with detection statistics and final state
        """
        if not self.measurements:
            return {
                'status': 'no_measurements',
                'measurements_count': 0,
                'plateau_reached': False,
                'reason': 'No measurements recorded'
            }

        plateau_reached, reason = self.is_plateau_reached()

        # Calculate peak and final throughput
        peak_throughput = max(m['throughput_gbps'] for m in self.measurements)
        final_throughput = self.measurements[-1]['throughput_gbps']

        # Calculate peak utilization if system limit known
        peak_utilization_pct = None
        if self.system_bandwidth_gbps > 0:
            peak_utilization_pct = (peak_throughput / self.system_bandwidth_gbps) * 100

        return {
            'status': 'complete',
            'measurements_count': len(self.measurements),
            'plateau_reached': plateau_reached,
            'reason': reason,
            'peak_throughput_gbps': peak_throughput,
            'final_throughput_gbps': final_throughput,
            'peak_utilization_pct': peak_utilization_pct,
            'system_limit_gbps': self.system_bandwidth_gbps,
            'last_measurement': self.measurements[-1]
        }
