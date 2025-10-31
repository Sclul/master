"""Centralized status message factory for consistent UI feedback."""
from dash import html
from typing import Optional, Union, List
from enum import Enum


class MessageSeverity(Enum):
    """Message severity levels."""
    SUCCESS = "success"
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class StatusMessageFactory:
    """Factory for creating consistent status messages across the application."""
    
    @staticmethod
    def create(
        message: Union[str, List[str]],
        severity: MessageSeverity = MessageSeverity.INFO,
        title: Optional[str] = None,
        details: Optional[Union[str, List[str]]] = None
    ) -> html.Div:
        """
        Create a standardized status message component.
        
        Args:
            message: Main message text (or list of message lines)
            severity: Message severity level
            title: Optional title/heading for the message
            details: Optional additional details (collapsed by default)
        
        Returns:
            Dash html.Div component with consistent structure
        """
        class_name = f"message message-{severity.value}"
        
        # Build message content
        content = []
        
        if title:
            content.append(html.Strong(title, style={"display": "block", "marginBottom": "0.25rem"}))
        
        # Handle single string or list of strings
        if isinstance(message, str):
            content.append(html.Span(message))
        elif isinstance(message, list):
            for msg in message:
                content.append(html.Div(msg))
        
        # Add optional details
        if details:
            detail_content = details if isinstance(details, list) else [details]
            content.append(
                html.Div([
                    html.Hr(style={"margin": "0.5rem 0", "border": "none", "borderTop": "1px solid currentColor", "opacity": "0.2"}),
                    *[html.Div(d, style={"fontSize": "0.85rem", "opacity": "0.8"}) for d in detail_content]
                ])
            )
        
        return html.Div(content, className=class_name)
    
    @staticmethod
    def success(message: Union[str, List[str]], title: Optional[str] = None, details: Optional[Union[str, List[str]]] = None) -> html.Div:
        """Create success message."""
        return StatusMessageFactory.create(message, MessageSeverity.SUCCESS, title, details)
    
    @staticmethod
    def error(message: Union[str, List[str]], title: Optional[str] = None, details: Optional[Union[str, List[str]]] = None) -> html.Div:
        """Create error message."""
        return StatusMessageFactory.create(message, MessageSeverity.ERROR, title, details)
    
    @staticmethod
    def warning(message: Union[str, List[str]], title: Optional[str] = None, details: Optional[Union[str, List[str]]] = None) -> html.Div:
        """Create warning message."""
        return StatusMessageFactory.create(message, MessageSeverity.WARNING, title, details)
    
    @staticmethod
    def info(message: Union[str, List[str]], title: Optional[str] = None, details: Optional[Union[str, List[str]]] = None) -> html.Div:
        """Create info message."""
        return StatusMessageFactory.create(message, MessageSeverity.INFO, title, details)


# Convenience instance
status_message = StatusMessageFactory()
