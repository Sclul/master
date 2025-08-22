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
        self._reset_timer = None  # Track the reset timer
    
    def reset(self):
        """Reset progress state."""
        with getattr(self, '_lock', threading.Lock()):
            self.active = False
            self.value = 0
            self.message = ""
            self.has_error = False
            self.start_time = None
            self.total_items = None  # New: total items to process
            self.processed_items = 0  # New: items processed so far
    
    def start(self, message: str = "Processing...", total_items: int = None):
        """Start tracking progress."""
        with self._lock:
            # Cancel any pending reset timer
            if self._reset_timer and self._reset_timer.is_alive():
                self._reset_timer.cancel()
                self._reset_timer = None
                
            self.active = True
            self.value = 0
            self.message = message
            self.has_error = False
            self.start_time = time.time()
            self.total_items = total_items
            self.processed_items = 0
            logger.info(f"Progress started: {message}" + (f" (total items: {total_items})" if total_items else ""))
    
    def update(self, value: int, message: str = None, processed_items: int = None):
        """Update progress value (0-100) and optional message."""
        with self._lock:
            self.value = max(0, min(100, value))
            if message:
                self.message = message
            if processed_items is not None:
                self.processed_items = processed_items
            logger.debug(f"Progress updated: {self.value}% - {self.message}")
    
    def update_items_processed(self, processed_items: int, message: str = None):
        """Update based on items processed (auto-calculate percentage)."""
        with self._lock:
            self.processed_items = processed_items
            if self.total_items and self.total_items > 0:
                self.value = int((processed_items / self.total_items) * 100)
            if message:
                self.message = message
            logger.debug(f"Items progress: {processed_items}/{self.total_items} ({self.value}%)")
    
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
            self.has_error = True
            self.message = f"Error: {message}"
            logger.error(f"Progress error: {message}")
    
    def get_state(self):
        """Get current progress state."""
        with self._lock:
            elapsed = time.time() - self.start_time if self.start_time else 0
            
            # Calculate estimated time remaining
            eta = None
            if self.active and self.value > 0 and elapsed > 0:
                estimated_total_time = (elapsed / self.value) * 100
                eta = estimated_total_time - elapsed
                
            return {
                "active": self.active,
                "value": self.value,
                "message": self.message,
                "error": self.has_error,
                "elapsed": elapsed,
                "total_items": self.total_items,
                "processed_items": self.processed_items,
                "eta": eta
            }


# Global progress tracker instance
progress_tracker = ProgressTracker()
