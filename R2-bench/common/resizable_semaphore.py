"""
Resizable semaphore for precise concurrency control.
"""

import threading
import time
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class ResizableSemaphore:
    """A semaphore that can be resized at runtime with precise in-flight tracking."""
    
    def __init__(self, initial_permits: int):
        """Initialize the semaphore with the given number of permits.
        
        Args:
            initial_permits: Initial number of permits available
        """
        self._permits = initial_permits
        self._max_permits = initial_permits
        self._in_flight = 0
        self._lock = threading.RLock()
        self._condition = threading.Condition(self._lock)
        
        logger.info(f"Initialized ResizableSemaphore with {initial_permits} permits")
    
    def acquire(self, blocking: bool = True, timeout: Optional[float] = None) -> bool:
        """Acquire a permit from the semaphore.
        
        Args:
            blocking: If True, block until a permit is available
            timeout: Maximum time to wait for a permit (None = wait forever)
            
        Returns:
            True if permit was acquired, False if timeout or non-blocking
        """
        with self._condition:
            if not blocking:
                if self._permits > 0:
                    self._permits -= 1
                    self._in_flight += 1
                    return True
                return False
            
            # Blocking acquire with timeout
            if timeout is None:
                while self._permits <= 0:
                    self._condition.wait()
            else:
                end_time = time.time() + timeout
                while self._permits <= 0:
                    remaining = end_time - time.time()
                    if remaining <= 0:
                        return False
                    self._condition.wait(remaining)
            
            self._permits -= 1
            self._in_flight += 1
            return True
    
    def release(self) -> None:
        """Release a permit back to the semaphore."""
        with self._condition:
            if self._in_flight > 0:
                self._in_flight -= 1
                # Only add back to permits if we're not over the current max
                if self._permits < self._max_permits:
                    self._permits += 1
                self._condition.notify()
            else:
                logger.warning("Attempted to release semaphore when in_flight is 0")
    
    def resize(self, new_permits: int) -> None:
        """Resize the semaphore to a new number of permits.
        
        Args:
            new_permits: New maximum number of permits
        """
        with self._condition:
            old_permits = self._max_permits
            self._max_permits = new_permits
            
            if new_permits > old_permits:
                # Increasing permits - add the difference
                self._permits += (new_permits - old_permits)
                self._condition.notify_all()
                logger.info(f"Resized semaphore: {old_permits} -> {new_permits} permits (+{new_permits - old_permits})")
            elif new_permits < old_permits:
                # Decreasing permits - adjust available permits
                excess_permits = old_permits - new_permits
                self._permits = max(0, self._permits - excess_permits)
                
                # Note: We don't wait for in-flight requests to complete here
                # as this could cause deadlocks. The semaphore will naturally
                # limit new acquires to the new maximum.
                
                logger.info(f"Resized semaphore: {old_permits} -> {new_permits} permits (-{excess_permits})")
            else:
                logger.debug(f"Semaphore already at {new_permits} permits")
    
    def in_flight(self) -> int:
        """Get the current number of in-flight requests.
        
        Returns:
            Number of currently in-flight requests
        """
        with self._lock:
            return self._in_flight
    
    def available_permits(self) -> int:
        """Get the number of available permits.
        
        Returns:
            Number of permits currently available
        """
        with self._lock:
            return self._permits
    
    def max_permits(self) -> int:
        """Get the maximum number of permits.
        
        Returns:
            Maximum number of permits
        """
        with self._lock:
            return self._max_permits
    
    def __repr__(self) -> str:
        """String representation of the semaphore."""
        return f"ResizableSemaphore(permits={self._permits}/{self._max_permits}, in_flight={self._in_flight})"
