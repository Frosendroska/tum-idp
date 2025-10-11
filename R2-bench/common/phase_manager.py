"""
Phase manager for tracking benchmark phases and step timing.
"""

import time
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


class PhaseManager:
    """Manages benchmark phases and tracks when steps begin measurement."""
    
    def __init__(self):
        """Initialize the phase manager."""
        self.phase_id: str = ""
        self.target_concurrency: int = 0
        self.step_started: bool = False
        self.step_start_ts: Optional[float] = None
        self.phase_start_ts: Optional[float] = None
        
        logger.info("Initialized PhaseManager")
    
    def begin_phase(self, phase_id: str, target_concurrency: int) -> None:
        """Begin a new phase.
        
        Args:
            phase_id: Unique identifier for the phase (e.g., "warmup", "ramp_1")
            target_concurrency: Target concurrency for this phase
        """
        self.phase_id = phase_id
        self.target_concurrency = target_concurrency
        self.step_started = False
        self.step_start_ts = None
        self.phase_start_ts = time.time()
        
        logger.info(f"Began phase: {phase_id} with target concurrency: {target_concurrency}")
    
    def mark_started(self, timestamp: Optional[float] = None) -> None:
        """Mark that the step has started measurement.
        
        This should be called when in_flight first equals target_concurrency.
        
        Args:
            timestamp: When the step started (defaults to current time)
        """
        if self.step_started:
            logger.warning(f"Phase {self.phase_id} already marked as started")
            return
        
        self.step_started = True
        self.step_start_ts = timestamp or time.time()
        
        logger.info(f"Phase {self.phase_id} started measurement at {self.step_start_ts:.3f}")
    
    def should_start_measuring(self, current_in_flight: int) -> bool:
        """Check if we should start measuring based on current in-flight count.
        
        Args:
            current_in_flight: Current number of in-flight requests
            
        Returns:
            True if we should start measuring and haven't already
        """
        if self.step_started:
            return False
        
        if current_in_flight >= self.target_concurrency:
            self.mark_started()
            return True
        
        return False
    
    def get_phase_info(self) -> Dict[str, Any]:
        """Get current phase information.
        
        Returns:
            Dictionary with current phase information
        """
        return {
            'phase_id': self.phase_id,
            'target_concurrency': self.target_concurrency,
            'step_started': self.step_started,
            'step_start_ts': self.step_start_ts,
            'phase_start_ts': self.phase_start_ts,
            'phase_duration': time.time() - self.phase_start_ts if self.phase_start_ts else None
        }
    
    def is_phase_active(self) -> bool:
        """Check if a phase is currently active.
        
        Returns:
            True if a phase is active
        """
        return bool(self.phase_id)
    
    def reset(self) -> None:
        """Reset the phase manager to initial state."""
        self.phase_id = ""
        self.target_concurrency = 0
        self.step_started = False
        self.step_start_ts = None
        self.phase_start_ts = None
        
        logger.debug("PhaseManager reset")
    
    def __repr__(self) -> str:
        """String representation of the phase manager."""
        return f"PhaseManager(phase_id='{self.phase_id}', target={self.target_concurrency}, started={self.step_started})"
