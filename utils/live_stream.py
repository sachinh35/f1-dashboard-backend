"""
Utility module for handling F1 SignalR live streaming.
"""
import asyncio
import json
import logging
import os
import threading
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, Callable
from signalrcore.hub_connection_builder import HubConnectionBuilder

logger = logging.getLogger(__name__)

# F1 SignalR Hub URL - WebSocket URLs must use wss:// for secure connections
F1_SIGNALR_URL = "wss://livetiming.formula1.com/signalr"
# Alternative URL that might be used:
# F1_SIGNALR_URL = "wss://api.formula1.com/v1/livetiming/signalr"

# Directory to store stream log files
STREAM_LOGS_DIR = Path("stream_logs")


class F1SignalRStreamer:
    """Handles F1 SignalR connection and data streaming."""
    
    def __init__(self, access_token: str, refresh_token: Optional[str] = None, cookies: Optional[str] = None):
        """
        Initialize the F1 SignalR streamer.
        
        Args:
            access_token: F1 TV Pro access token
            refresh_token: Optional refresh token
            cookies: Optional session cookies
        """
        self.access_token = access_token
        self.refresh_token = refresh_token
        self.cookies = cookies
        self.connection: Optional[Any] = None
        self.stream_id: str = str(int(datetime.now().timestamp()))
        self.log_file_path: Optional[Path] = None
        self.log_file_handle: Optional[Any] = None
        self.is_connected = False
        self._setup_log_directory()
        self._setup_log_file()
    
    def _setup_log_directory(self):
        """Create the stream logs directory if it doesn't exist."""
        STREAM_LOGS_DIR.mkdir(exist_ok=True)
        logger.info(f"Stream logs directory: {STREAM_LOGS_DIR.absolute()}")
    
    def _setup_log_file(self):
        """Create a unique log file for this stream session."""
        timestamp = int(datetime.now().timestamp())
        filename = f"f1_stream_{timestamp}.jsonl"
        self.log_file_path = STREAM_LOGS_DIR / filename
        self.log_file_handle = open(self.log_file_path, 'a', encoding='utf-8')
        logger.info(f"Created log file: {self.log_file_path.absolute()}")
    
    def _log_event(self, event_type: str, data: Any):
        """
        Log an event to both console and file.
        
        Args:
            event_type: Type of event (e.g., 'message', 'error', 'connection')
            data: Event data to log
        """
        timestamp = datetime.now().isoformat()
        log_entry = {
            "timestamp": timestamp,
            "stream_id": self.stream_id,
            "event_type": event_type,
            "data": data
        }
        
        # Log to console
        logger.info(f"Stream Event [{event_type}]: {json.dumps(log_entry, default=str)}")
        
        # Write to file (JSONL format - one JSON object per line)
        if self.log_file_handle:
            try:
                self.log_file_handle.write(json.dumps(log_entry, default=str) + "\n")
                self.log_file_handle.flush()  # Ensure data is written immediately
            except Exception as e:
                logger.error(f"Error writing to log file: {e}")
    
    def connect(self):
        """Establish connection to F1 SignalR hub."""
        try:
            logger.info(f"Connecting to F1 SignalR hub: {F1_SIGNALR_URL}")
            
            # Build the SignalR connection with authentication
            # signalrcore uses a different API structure
            def get_access_token():
                return self.access_token
            
            # Build headers with authentication
            headers = {
                "User-Agent": "F1-Dashboard/1.0",
            }
            
            # Add authentication - try both token and cookie approaches
            if self.access_token:
                # If token looks like a cookie string, use Cookie header
                if "=" in self.access_token or self.cookies:
                    headers["Cookie"] = self.cookies or self.access_token
                else:
                    # Otherwise use Bearer token
                    headers["Authorization"] = f"Bearer {self.access_token}"
            
            # Add cookies if available
            if self.cookies:
                headers["Cookie"] = self.cookies
            
            self.connection = HubConnectionBuilder() \
                .with_url(
                    F1_SIGNALR_URL,
                    options={
                        "access_token_factory": get_access_token,
                        "headers": headers
                    }
                ) \
                .configure_logging(logging.INFO) \
                .with_automatic_reconnect({
                    "type": "raw",
                    "keep_alive_interval": 10,
                    "reconnect_interval": 5,
                    "max_attempts": 5
                }) \
                .build()
            
            # Set up event handlers
            self._setup_handlers()
            
            # Start the connection (signalrcore uses synchronous start)
            self.connection.start()
            self.is_connected = True
            self._log_event("connection", {"status": "connected", "url": F1_SIGNALR_URL})
            logger.info("Successfully connected to F1 SignalR hub")
            
        except Exception as e:
            self.is_connected = False
            error_msg = f"Failed to connect to F1 SignalR hub: {str(e)}"
            logger.error(error_msg)
            self._log_event("error", {"error": error_msg, "type": "connection_error"})
            raise
    
    def _setup_handlers(self):
        """Set up SignalR event handlers."""
        if not self.connection:
            return
        
        # Handle connection events
        # Note: signalrcore callbacks may not always receive arguments
        def on_connected(*args):
            message = args[0] if args else None
            self.is_connected = True
            self._log_event("connection", {"status": "connected", "message": message})
        
        def on_disconnected(*args):
            message = args[0] if args else None
            self.is_connected = False
            self._log_event("connection", {"status": "disconnected", "message": message})
        
        # Register connection event handlers
        self.connection.on_open(on_connected)
        self.connection.on_close(on_disconnected)
        
        # Handle generic message events
        # Note: F1's actual event names may vary - these are common SignalR patterns
        # We'll need to adjust based on actual F1 API documentation
        
        # Try to register handlers for common F1 live timing events
        # These are examples and may need adjustment:
        event_handlers = [
            "CarData", "Position", "ExtrapolatedClock", "TimingData",
            "TimingStats", "WeatherData", "TrackStatus", "SessionInfo",
            "RaceControlMessages", "TimingAppData", "ReceiveMessage"
        ]
        
        def create_handler(event_name: str):
            def handler(*args):
                # Handle different argument patterns
                if len(args) == 1:
                    data = args[0]
                else:
                    data = args
                self._log_event("message", {"event_name": event_name, "payload": data})
            return handler
        
        # Register handlers for each event type
        for event_name in event_handlers:
            try:
                handler = create_handler(event_name)
                self.connection.on(event_name, handler)
            except Exception as e:
                logger.warning(f"Could not register handler for {event_name}: {e}")
        
        # Fallback: catch all messages using a generic handler
        def on_any_message(*args):
            if len(args) == 1:
                data = args[0]
            else:
                data = args
            self._log_event("message", {"event_name": "unknown", "payload": data})
        
        # Try to register a catch-all if the library supports it
        try:
            self.connection.on("message", on_any_message)
        except:
            pass
    
    def subscribe_to_events(self, session_key: Optional[int] = None):
        """
        Subscribe to F1 live timing events.
        
        Args:
            session_key: Optional session key to filter events
        """
        if not self.connection or not self.is_connected:
            raise RuntimeError("Not connected to SignalR hub")
        
        try:
            # Subscribe to live timing hub
            # The actual method names may vary - these are examples
            # F1's SignalR hub might use different method names
            subscription_methods = [
                "Subscribe", "SubscribeToTiming", "SubscribeToLiveTiming"
            ]
            
            for method in subscription_methods:
                try:
                    # signalrcore uses invoke() for server method calls
                    if session_key:
                        self.connection.invoke(method, session_key)
                    else:
                        self.connection.invoke(method)
                    logger.info(f"Subscribed to {method}")
                    self._log_event("subscription", {"method": method, "session_key": session_key})
                    break  # If one works, we're done
                except Exception as e:
                    logger.debug(f"Subscription method {method} failed: {e}")
                    continue
            
        except Exception as e:
            error_msg = f"Failed to subscribe to events: {str(e)}"
            logger.error(error_msg)
            self._log_event("error", {"error": error_msg, "type": "subscription_error"})
            # Don't raise - subscription might not be required for all hubs
            logger.warning("Continuing without explicit subscription - events may still be received")
    
    def disconnect(self):
        """Disconnect from SignalR hub and close log file."""
        try:
            if self.connection and self.is_connected:
                self.connection.stop()
                self.is_connected = False
                self._log_event("connection", {"status": "disconnected", "reason": "manual"})
                logger.info("Disconnected from F1 SignalR hub")
        except Exception as e:
            logger.error(f"Error disconnecting: {e}")
        finally:
            if self.log_file_handle:
                self.log_file_handle.close()
                self.log_file_handle = None
                logger.info(f"Closed log file: {self.log_file_path}")
    
    def run(self, session_key: Optional[int] = None):
        """
        Run the streamer (connect, subscribe, and keep alive).
        This runs in a separate thread to avoid blocking.
        
        Args:
            session_key: Optional session key to filter events
        """
        try:
            self.connect()
            self.subscribe_to_events(session_key)
            
            # Keep the connection alive
            # In a real implementation, this would run until interrupted
            logger.info("Stream is running. Waiting for events...")
            self._log_event("stream", {"status": "running"})
            
            # Keep alive loop - signalrcore handles connection management
            # We just need to keep the thread alive
            import time
            while self.is_connected:
                time.sleep(1)
                
        except KeyboardInterrupt:
            logger.info("Stream interrupted by user")
            self._log_event("stream", {"status": "interrupted", "reason": "user"})
        except Exception as e:
            error_msg = f"Stream error: {str(e)}"
            logger.error(error_msg)
            self._log_event("error", {"error": error_msg, "type": "stream_error"})
            raise
        finally:
            self.disconnect()
    
    def get_stream_info(self) -> Dict[str, Any]:
        """Get information about the current stream."""
        return {
            "stream_id": self.stream_id,
            "log_file": str(self.log_file_path) if self.log_file_path else None,
            "is_connected": self.is_connected
        }


# Global dictionary to track active streams
_active_streams: Dict[str, F1SignalRStreamer] = {}


def start_stream(access_token: str, refresh_token: Optional[str] = None, cookies: Optional[str] = None) -> F1SignalRStreamer:
    """
    Start a new F1 SignalR stream.
    
    Args:
        access_token: F1 TV Pro access token
        refresh_token: Optional refresh token
        
    Returns:
        F1SignalRStreamer instance
    """
    streamer = F1SignalRStreamer(access_token, refresh_token, cookies)
    stream_id = streamer.stream_id
    
    # Store the streamer
    _active_streams[stream_id] = streamer
    
    # Start streaming in background thread
    stream_thread = threading.Thread(target=streamer.run, daemon=True)
    stream_thread.start()
    
    return streamer


def get_stream(stream_id: str) -> Optional[F1SignalRStreamer]:
    """Get an active stream by ID."""
    return _active_streams.get(stream_id)


def stop_stream(stream_id: str) -> bool:
    """
    Stop an active stream.
    
    Returns:
        True if stream was found and stopped, False otherwise
    """
    streamer = _active_streams.get(stream_id)
    if streamer:
        streamer.disconnect()
        del _active_streams[stream_id]
        return True
    return False

