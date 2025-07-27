"""Simple progress tracker for long-running operations."""
import time
import threading
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class ProgressTracker:
    """Simple progress tracker for long-running operations."""
    
    def __init__(self):
        self.reset()
        self._lock = threading.Lock()
    
    def reset(self):
        """Reset progress state."""
        with getattr(self, '_lock', threading.Lock()):
            self.active = False
            self.value = 0
            self.message = ""
            self.error = False
            self.start_time = None
    
    def start(self, message: str = "Processing..."):
        """Start tracking progress."""
        with self._lock:
            self.active = True
            self.value = 0
            self.message = message
            self.error = False
            self.start_time = time.time()
            logger.info(f"Progress started: {message}")
    
    def update(self, value: int, message: str = None):
        """Update progress value (0-100) and optional message."""
        with self._lock:
            self.value = max(0, min(100, value))
            if message:
                self.message = message
            logger.debug(f"Progress updated: {self.value}% - {self.message}")
    
    def complete(self, message: str = "Completed successfully"):
        """Mark progress as complete."""
        with self._lock:
            self.value = 100
            self.message = message
            logger.info(f"Progress completed: {message}")
            # Will be reset after a short delay by the callback
    
    def error(self, message: str):
        """Mark progress as failed."""
        with self._lock:
            self.error = True
            self.message = f"Error: {message}"
            logger.error(f"Progress error: {message}")
    
    def get_state(self):
        """Get current progress state."""
        with self._lock:
            elapsed = time.time() - self.start_time if self.start_time else 0
            return {
                "active": self.active,
                "value": self.value,
                "message": self.message,
                "error": self.error,
                "elapsed": elapsed
            }


# Global progress tracker instance
progress_tracker = ProgressTracker()
