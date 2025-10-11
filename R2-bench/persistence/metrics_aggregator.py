"""
Metrics aggregator for phase-based step statistics.
"""

import time
import threading
import logging
from typing import List, Dict, Any, Optional
from collections import defaultdict
from persistence.base import BenchmarkRecord

logger = logging.getLogger(__name__)


class MetricsAggregator:
    """Aggregates metrics by phase and computes step statistics."""
    
    def __init__(self):
        """Initialize the metrics aggregator."""
        self.records: List[BenchmarkRecord] = []
        self.phase_step_times: Dict[str, float] = {}  # phase_id -> step_start_ts
        self.lock = threading.Lock()
        
        logger.info("Initialized MetricsAggregator")
    
    def record_request(self, record: BenchmarkRecord) -> None:
        """Record a request with phase attribution.
        
        Args:
            record: Benchmark record with phase information
        """
        with self.lock:
            self.records.append(record)
    
    def set_phase_step_time(self, phase_id: str, step_start_ts: float) -> None:
        """Set the step start time for a phase.
        
        Args:
            phase_id: Phase identifier
            step_start_ts: When the step started measuring
        """
        with self.lock:
            self.phase_step_times[phase_id] = step_start_ts
            logger.debug(f"Set step start time for {phase_id}: {step_start_ts:.3f}")
    
    def get_step_stats(self, phase_id: str) -> Optional[Dict[str, Any]]:
        """Get statistics for a specific phase step.
        
        Args:
            phase_id: Phase identifier
            
        Returns:
            Dictionary with step statistics or None if no data
        """
        with self.lock:
            if phase_id not in self.phase_step_times:
                logger.warning(f"No step start time recorded for phase {phase_id}")
                return None
            
            step_start_ts = self.phase_step_times[phase_id]
            
            # Filter records that started at or after the step start time
            step_records = [
                r for r in self.records 
                if r.phase_id == phase_id and r.start_ts >= step_start_ts
            ]
            
            if not step_records:
                logger.warning(f"No records found for phase {phase_id} after step start time")
                return None
            
            return self._compute_step_statistics(phase_id, step_records, step_start_ts)
    
    def _compute_step_statistics(self, phase_id: str, records: List[BenchmarkRecord], 
                                step_start_ts: float) -> Dict[str, Any]:
        """Compute statistics for a step.
        
        Args:
            phase_id: Phase identifier
            records: Records for this step
            step_start_ts: When the step started
            
        Returns:
            Dictionary with step statistics
        """
        if not records:
            return {}
        
        # Basic counts
        total_requests = len(records)
        successful_requests = sum(1 for r in records if r.http_status == 200)
        error_requests = total_requests - successful_requests
        
        # Throughput calculation
        if successful_requests > 0:
            total_bytes = sum(r.bytes for r in records if r.http_status == 200)
            step_duration = time.time() - step_start_ts
            throughput_mbps = (total_bytes * 8) / (step_duration * 1_000_000) if step_duration > 0 else 0
        else:
            throughput_mbps = 0
        
        # Latency statistics
        successful_latencies = [r.latency_ms for r in records if r.http_status == 200]
        if successful_latencies:
            successful_latencies.sort()
            p50_latency = successful_latencies[len(successful_latencies) // 2]
            p95_latency = successful_latencies[int(len(successful_latencies) * 0.95)]
            p99_latency = successful_latencies[int(len(successful_latencies) * 0.99)]
            avg_latency = sum(successful_latencies) / len(successful_latencies)
        else:
            p50_latency = p95_latency = p99_latency = avg_latency = 0
        
        # Error rate
        error_rate = error_requests / total_requests if total_requests > 0 else 0
        
        # Concurrency (should be consistent within a step)
        concurrency = records[0].concurrency if records else 0
        
        stats = {
            'phase_id': phase_id,
            'concurrency': concurrency,
            'step_start_ts': step_start_ts,
            'duration_seconds': time.time() - step_start_ts,
            'total_requests': total_requests,
            'successful_requests': successful_requests,
            'error_requests': error_requests,
            'error_rate': error_rate,
            'throughput_mbps': throughput_mbps,
            'avg_latency_ms': avg_latency,
            'p50_latency_ms': p50_latency,
            'p95_latency_ms': p95_latency,
            'p99_latency_ms': p99_latency,
            'total_bytes': sum(r.bytes for r in records if r.http_status == 200)
        }
        
        logger.debug(f"Computed step stats for {phase_id}: {throughput_mbps:.1f} Mbps, "
                    f"{successful_requests}/{total_requests} requests, {error_rate:.1%} error rate")
        
        return stats
    
    def get_all_phase_stats(self) -> Dict[str, Dict[str, Any]]:
        """Get statistics for all phases.
        
        Returns:
            Dictionary mapping phase_id to step statistics
        """
        with self.lock:
            all_stats = {}
            for phase_id in self.phase_step_times:
                stats = self.get_step_stats(phase_id)
                if stats:
                    all_stats[phase_id] = stats
            return all_stats
    
    def clear_phase_data(self, phase_id: str) -> None:
        """Clear data for a specific phase.
        
        Args:
            phase_id: Phase identifier to clear
        """
        with self.lock:
            if phase_id in self.phase_step_times:
                del self.phase_step_times[phase_id]
            
            # Remove records for this phase
            self.records = [r for r in self.records if r.phase_id != phase_id]
            
            logger.debug(f"Cleared data for phase {phase_id}")
    
    def get_total_records(self) -> int:
        """Get total number of records.
        
        Returns:
            Total number of records
        """
        with self.lock:
            return len(self.records)
