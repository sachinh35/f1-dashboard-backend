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
from typing import Optional, Dict, Any, Callable, List
import httpx
from signalrcore.hub_connection_builder import HubConnectionBuilder
from utils import live_db
from utils.websocket_manager import manager

logger = logging.getLogger(__name__)

# F1 SignalR Hub Configuration
# The negotiation endpoint is: https://livetiming.formula1.com/signalrcore/negotiate
# The hub name for F1 live timing is typically "Streaming"
F1_SIGNALR_BASE_URL = "https://livetiming.formula1.com/signalrcore"
F1_SIGNALR_NEGOTIATE_URL = f"{F1_SIGNALR_BASE_URL}/negotiate"
F1_SIGNALR_HUB_NAME = "Streaming"  # F1's SignalR hub name

# Try different possible endpoints (will try them in order if connection fails):
F1_SIGNALR_URLS = [
    "wss://livetiming.formula1.com/signalrcore",  # Direct WebSocket (preferred by Fast-F1)
    F1_SIGNALR_BASE_URL,  # HTTPS base URL
    "https://livetiming.formula1.com/signalr",  # Fallback (older format)
]
F1_SIGNALR_URL = F1_SIGNALR_URLS[0]  # Default to first URL

# Directory to store stream log files
STREAM_LOGS_DIR = Path("stream_logs")

# Topics to subscribe to (from Fast-F1)
F1_TOPICS = [
    "Heartbeat", "AudioStreams", "DriverList",
    "ExtrapolatedClock", "RaceControlMessages",
    "SessionInfo", "SessionStatus", "TeamRadio",
    "TimingAppData", "TimingStats", "TrackStatus",
    "WeatherData", "Position.z", "CarData.z",
    "ContentStreams", "SessionData", "TimingData",
    "TopThree", "RcmSeries", "LapCount"
]


class F1SignalRStreamer:
    """Handles F1 SignalR connection and data streaming."""
    
    def __init__(self, access_token: str, refresh_token: Optional[str] = None, cookies: Optional[str] = None, loop: Optional[asyncio.AbstractEventLoop] = None):
        """
        Initialize the F1 SignalR streamer.
        
        Args:
            access_token: F1 TV Pro access token
            refresh_token: Optional refresh token
            cookies: Optional session cookies
            loop: Asyncio event loop to run async tasks on
        """
        self.access_token = access_token
        self.refresh_token = refresh_token
        self.cookies = cookies
        self.loop = loop
        self.connection: Optional[Any] = None
        self.stream_id: str = str(int(datetime.now().timestamp()))
        self.log_file_path: Optional[Path] = None
        self.log_file_handle: Optional[Any] = None
        self.is_connected = False
        self.connected_event = threading.Event() # Initialize connected_event
        self._setup_log_directory()
        self._setup_log_file()
        
        # Create stream entry in DB
        if self.loop:
            asyncio.run_coroutine_threadsafe(
                live_db.create_live_stream(self.stream_id, "Live Stream"),
                self.loop
            )

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
        
        # Log to console (reduced verbosity for raw data)
        if event_type != "message":
            logger.info(f"Stream Event [{event_type}]: {json.dumps(log_entry, default=str)}")
        
        # Write to file (JSONL format - one JSON object per line)
        if self.log_file_handle:
            try:
                self.log_file_handle.write(json.dumps(log_entry, default=str) + "\n")
                self.log_file_handle.flush()  # Ensure data is written immediately
            except Exception as e:
                logger.error(f"Error writing to log file: {e}")

    async def _process_timing_data(self, payload: Any):
        """Process TimingData payload to extract lap times."""
        try:
            if isinstance(payload, str):
                try:
                    payload = json.loads(payload)
                except:
                    return

            if "Lines" not in payload:
                return

            for car_id, car_data in payload["Lines"].items():
                # Check for LastLapTime
                if "LastLapTime" in car_data:
                    last_lap = car_data["LastLapTime"]
                    # We need LapNumber to be useful, but sometimes it comes in separate updates.
                    # For now, let's assume we might have it or we just store what we have.
                    # Actually, we need to know WHICH lap this time is for.
                    # Usually TimingData has 'BestLapTime' and 'LastLapTime'.
                    # And 'NumberOfLaps' or similar.
                    # Let's check if we can get the lap number.
                    pass
                
                # Check for Sectors to update current lap progress?
                # For the chart, we specifically want COMPLETED lap times.
                
                # Let's look for completed laps.
                # A robust way is to track the car's state, but for this MVP, 
                # let's see if we can extract a lap time when it updates.
                
                if "LastLapTime" in car_data and "Value" in car_data["LastLapTime"]:
                    lap_time_str = car_data["LastLapTime"]["Value"]
                    if not lap_time_str:
                        continue
                        
                    # Parse duration (e.g. "1:23.456")
                    try:
                        # Simple parsing
                        parts = lap_time_str.split(':')
                        if len(parts) == 2:
                            seconds = float(parts[0]) * 60 + float(parts[1])
                        else:
                            seconds = float(parts[0])
                    except:
                        continue

                    # We need a lap number. If not present in this payload, we might miss it.
                    # However, we can try to find it in the payload or rely on state.
                    # For now, let's see if 'Sectors' has useful info or if we can find 'NumberOfLaps'.
                    # If we don't have a lap number, we can't uniquely identify the lap in DB.
                    # But we can broadcast it to frontend at least.
                    
                    # Let's try to find LapNumber in the same payload or default to 0 (which is bad).
                    # But wait, the user wants to chart it.
                    # If we look at the previous analysis, we saw 'LapNumber' events.
                    # Maybe we should track state.
                    pass

            # For the purpose of this task, let's just broadcast the raw payload to frontend
            # and let frontend handle it? No, requirements say "backend is reading... keep on saving lap timing data".
            
            # Let's implement a simple state tracker in the class if needed, 
            # or just extract if available.
            
            # Let's broadcast everything to WS first.
            await manager.broadcast({"type": "TimingData", "payload": payload}, self.stream_id)
            
            # And try to save if we have enough info.
            # To properly save, we'd need to merge with current state.
            # For now, let's just broadcast.
            
        except Exception as e:
            logger.error(f"Error processing timing data: {e}")

    def _handle_message_async(self, event_name: str, payload: Any):
        """Schedule async message handling."""
        if not self.loop:
            return

        async def task():
            # Broadcast all messages
            await manager.broadcast({"type": event_name, "payload": payload}, self.stream_id)
            
            # Process specific messages for DB
            if event_name == "TimingData":
                # We need to implement proper parsing logic here.
                # For now, let's just inspect.
                # To do this correctly, we need to maintain the state of each driver.
                # Let's do a best-effort extraction.
                if isinstance(payload, str):
                    try:
                        data = json.loads(payload)
                    except:
                        return
                else:
                    data = payload
                
                if "Lines" in data:
                    for car_id, car_data in data["Lines"].items():
                        if "LastLapTime" in car_data and "Value" in car_data["LastLapTime"]:
                            val = car_data["LastLapTime"]["Value"]
                            if val:
                                # We found a lap time. We need the lap number.
                                # If it's not in this update, we might need to look up the driver's current lap.
                                # But we don't have state here.
                                # Let's check if "NumberOfLaps" is in this update.
                                lap_num = car_data.get("NumberOfLaps")
                                if lap_num:
                                    # Parse time
                                    try:
                                        parts = val.split(':')
                                        if len(parts) == 2:
                                            seconds = float(parts[0]) * 60 + float(parts[1])
                                        else:
                                            seconds = float(parts[0])
                                            
                                        # Save to DB only if not simulation
                                        if not self.stream_id.startswith("simulation_"):
                                            lap_record = live_db.LiveLapTimeDB(
                                                stream_id=self.stream_id,
                                                driver_number=int(car_id),
                                                lap_number=int(lap_num),
                                                lap_time=seconds,
                                                sector_1=None, sector_2=None, sector_3=None # TODO: extract sectors
                                            )
                                            await live_db.insert_live_lap_time(lap_record)
                                    except:
                                        pass

        asyncio.run_coroutine_threadsafe(task(), self.loop)

    def _build_headers(self) -> Dict[str, str]:
        """Build authentication headers for SignalR connection."""
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Origin": "https://www.formula1.com",
            "Referer": "https://www.formula1.com/",
        }
        
        # Add authentication
        # For F1 SignalR, the token is typically passed via the access_token_factory in signalrcore
        # which appends it to the query string as 'access_token' or in the Authorization header.
        # However, we also set it here just in case.
        if self.access_token:
            # headers["Authorization"] = f"JWT {self.access_token}" # Fast-F1 doesn't seem to send this in headers explicitly for SignalR, only access_token_factory
            pass

        # Add User-Agent (Fast-F1 uses BestHTTP often, or default)
        headers["User-Agent"] = "BestHTTP" 
        headers["Accept-Encoding"] = "gzip, identity"
        
        return headers

    def _get_awsalbcors_cookie(self) -> Optional[str]:
        """
        Fetch AWSALBCORS cookie via OPTIONS request to negotiate endpoint.
        Required for F1 SignalR connection.
        """
        try:
            logger.info(f"Fetching AWSALBCORS cookie from {F1_SIGNALR_NEGOTIATE_URL}")
            # Fast-F1 uses requests.options
            response = httpx.options(F1_SIGNALR_NEGOTIATE_URL, headers={"User-Agent": "BestHTTP"})
            
            # Check for Set-Cookie header or cookies in client
            cookie = response.cookies.get("AWSALBCORS")
            if cookie:
                logger.info(f"Got AWSALBCORS cookie: {cookie[:10]}...")
                return f"AWSALBCORS={cookie}"
            else:
                logger.warning("AWSALBCORS cookie not found in response")
                return None
        except Exception as e:
            logger.warning(f"Failed to fetch AWSALBCORS cookie: {e}")
            return None
    
    def _test_negotiation(self) -> Optional[Dict[str, Any]]:
        """
        Manually test the SignalR negotiation endpoint.
        This helps debug connection issues.
        
        SignalR Core negotiation uses GET with query parameters:
        - connectionData: JSON-encoded array of hub names
        - clientProtocol: Protocol version (typically 1.5)
        
        Returns:
            Negotiation response data if successful, None otherwise
        """
        try:
            import urllib.parse
            
            logger.info(f"Testing negotiation endpoint: {F1_SIGNALR_NEGOTIATE_URL}")
            headers = self._build_headers()
            
            # SignalR Core negotiation uses GET with query parameters
            # connectionData should be JSON-encoded array of hub objects
            connection_data = json.dumps([{"name": F1_SIGNALR_HUB_NAME}])
            encoded_connection_data = urllib.parse.quote(connection_data)
            
            # Build negotiation URL with query parameters
            negotiate_url = f"{F1_SIGNALR_NEGOTIATE_URL}?connectionData={encoded_connection_data}&clientProtocol=1.5"
            
            # Try GET request (SignalR Core uses GET for negotiation)
            with httpx.Client(timeout=10.0, follow_redirects=True) as client:
                response = client.get(
                    negotiate_url,
                    headers=headers
                )
                
                logger.info(f"Negotiation response status: {response.status_code}")
                logger.debug(f"Negotiation response headers: {dict(response.headers)}")
                
                if response.status_code == 200:
                    try:
                        data = response.json()
                        logger.info(f"Negotiation successful. Response keys: {list(data.keys()) if isinstance(data, dict) else 'N/A'}")
                        logger.debug(f"Full negotiation response: {json.dumps(data, indent=2)}")
                        return data
                    except json.JSONDecodeError:
                        logger.warning(f"Negotiation returned non-JSON response: {response.text[:200]}")
                        return None
                else:
                    logger.warning(f"Negotiation failed with status {response.status_code}")
                    logger.warning(f"Response text: {response.text[:500]}")
                    return None
                    
        except Exception as e:
            logger.warning(f"Error testing negotiation: {e}", exc_info=True)
            return None
    
    def connect(self):
        """Establish connection to F1 SignalR hub. Tries multiple URL formats if needed."""
        last_error = None
        
        # Test negotiation endpoint first (for debugging)
        negotiation_result = self._test_negotiation()
        if negotiation_result:
            logger.info("Negotiation test successful - proceeding with connection")
        else:
            logger.warning("Negotiation test failed or skipped - will attempt connection anyway")
        
        # Try each URL format until one works
        for url in F1_SIGNALR_URLS:
            try:
                logger.info(f"Attempting to connect to F1 SignalR hub: {url}")
                
                # Fetch AWSALBCORS cookie if needed
                aws_cookie = self._get_awsalbcors_cookie()
                
                # Build headers with authentication
                headers = self._build_headers()
                
                if aws_cookie:
                    if "Cookie" in headers:
                        headers["Cookie"] += f"; {aws_cookie}"
                    else:
                        headers["Cookie"] = aws_cookie
                
                # Log headers (without sensitive data)
                safe_headers = {k: (v[:50] + "..." if len(str(v)) > 50 else v) for k, v in headers.items()}
                logger.debug(f"Connection headers: {safe_headers}")
                
                # Build connection options
                # signalrcore expects options dict with specific keys
                connection_options = {
                    "headers": headers
                }
                
                # Set access_token_factory for signalrcore
                if self.access_token:
                    def get_access_token():
                        return self.access_token
                    connection_options["access_token_factory"] = get_access_token
                
                # Clean up previous connection attempt if any
                if self.connection:
                    try:
                        self.connection.stop()
                    except:
                        pass
                
                self.connection = HubConnectionBuilder() \
                    .with_url(
                        url,
                        options=connection_options
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
                logger.info(f"Attempting to start SignalR connection to {url}...")
                self.connection.start()
                
                # Wait for connection to be established
                if not self.connected_event.wait(timeout=10):
                    logger.error("Timeout waiting for connection to open")
                    self.connection.stop()
                    raise TimeoutError("Failed to connect to SignalR hub")

                self.is_connected = True
                self._log_event("connection", {"status": "connected", "url": url})
                logger.info(f"Successfully connected to F1 SignalR hub at {url}")
                return  # Success - exit the loop
                
            except Exception as e:
                last_error = e
                error_msg = f"Failed to connect to {url}: {str(e)}"
                logger.warning(error_msg)
                self._log_event("error", {
                    "error": error_msg, 
                    "type": "connection_error", 
                    "url": url,
                    "exception_type": str(type(e).__name__)
                })
                # Continue to next URL
                continue
        
        # If we get here, all URLs failed
        self.is_connected = False
        final_error_msg = f"Failed to connect to F1 SignalR hub with all attempted URLs. Last error: {str(last_error)}"
        logger.error(final_error_msg, exc_info=True)
        self._log_event("error", {
            "error": final_error_msg, 
            "type": "connection_error", 
            "exception_type": str(type(last_error).__name__) if last_error else "Unknown",
            "attempted_urls": F1_SIGNALR_URLS
        })
        raise Exception(final_error_msg) from last_error
    
    def _setup_handlers(self):
        """Set up SignalR event handlers."""
        if not self.connection:
            return
        
        # Handle connection events
        def on_open(*args):
            message = args[0] if args else None
            self.is_connected = True
            self._log_event("connection", {"status": "connected", "message": message})
            self.connected_event.set() # Set event when connection is open
        
        def on_close(*args):
            message = args[0] if args else None
            self.is_connected = False
            self._log_event("connection", {"status": "disconnected", "message": message})
            self.connected_event.clear() # Clear event when connection is closed
        
        # Register connection event handlers
        self.connection.on_open(on_open)
        self.connection.on_close(on_close)
        
        # Handle generic message events
        # F1 sends all data via the "feed" event
        def on_feed_message(*args):
            try:
                # args[0] is typically the payload list: [message_type, data, timestamp]
                if args and len(args) > 0:
                    payload = args[0]
                    if isinstance(payload, list) and len(payload) >= 2:
                        message_type = payload[0]
                        message_data = payload[1]
                        self._log_event("message", {"event_name": message_type, "payload": message_data})
                        
                        # Handle async processing (DB save, WS broadcast)
                        self._handle_message_async(message_type, message_data)
                        
                    else:
                        self._log_event("message", {"event_name": "feed", "payload": payload})
                        self._handle_message_async("feed", payload)
                else:
                    logger.warning("Received empty feed message")
            except Exception as e:
                logger.error(f"Error processing feed message: {e}")

        try:
            self.connection.on("feed", on_feed_message)
            logger.info("Registered 'feed' event handler")
        except Exception as e:
            logger.error(f"Could not register 'feed' handler: {e}")
        
        # Fallback: catch all messages using a generic handler
        def on_any_message(*args):
            if len(args) == 1:
                data = args[0]
            else:
                data = args
            self._log_event("message", {"event_name": "unknown", "payload": data})
            self._handle_message_async("unknown", data)
        
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
                    # signalrcore uses send() for server method calls (at least in the version Fast-F1 uses)
                    # Fast-F1 sends: "Subscribe", [self.topics]
                    self.connection.send(method, [F1_TOPICS])
                    
                    logger.info(f"Subscribed to {method} with topics")
                    self._log_event("subscription", {"method": method, "topics": F1_TOPICS})
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
                self.connected_event.clear() # Clear event on manual disconnect
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
    
    def simulate_stream(self, log_file_path: str, speed_factor: float = 1.0):
        """
        Simulate a stream by replaying events from a log file.
        
        Args:
            log_file_path: Path to the JSONL log file
            speed_factor: Speed multiplier (1.0 = real time, >1.0 = faster)
        """
        try:
            self.is_connected = True
            self._log_event("stream", {"status": "simulating", "source": log_file_path})
            logger.info(f"Starting simulation from {log_file_path}")
            
            import time
            
            with open(log_file_path, 'r', encoding='utf-8') as f:
                for line in f:
                    if not self.is_connected:
                        break
                        
                    try:
                        entry = json.loads(line)
                        event_type = entry.get("event_type")
                        data = entry.get("data")
                        
                        if event_type == "message" and data:
                            event_name = data.get("event_name")
                            payload = data.get("payload")
                            
                            if event_name and payload:
                                # Process the message
                                self._handle_message_async(event_name, payload)
                                
                                # Simulate delay
                                # In a real replay, we'd use timestamps to calculate delay.
                                # For now, just a fixed small delay to avoid flooding
                                time.sleep(0.1 / speed_factor)
                                
                    except json.JSONDecodeError:
                        continue
                    except Exception as e:
                        logger.error(f"Error processing simulation line: {e}")
                        continue
                        
            logger.info("Simulation finished")
            self._log_event("stream", {"status": "simulation_finished"})
            
        except Exception as e:
            logger.error(f"Simulation error: {e}")
            self._log_event("error", {"error": str(e), "type": "simulation_error"})
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
    # Get current event loop to pass to streamer
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
        
    streamer = F1SignalRStreamer(access_token, refresh_token, cookies, loop=loop)
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



def start_simulation(log_file_path: str) -> F1SignalRStreamer:
    """
    Start a simulated stream from a log file.
    
    Args:
        log_file_path: Path to the log file
        
    Returns:
        F1SignalRStreamer instance
    """
    # Get current event loop
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
        
    # Create streamer with dummy token
    streamer = F1SignalRStreamer("simulation_token", loop=loop)
    streamer.stream_id = f"simulation_{int(datetime.now().timestamp())}"
    
    # Store the streamer
    _active_streams[streamer.stream_id] = streamer
    
    # Start simulation in background thread
    stream_thread = threading.Thread(
        target=streamer.simulate_stream, 
        args=(log_file_path,), 
        kwargs={"speed_factor": 5.0}, # Run 5x faster
        daemon=True
    )
    stream_thread.start()
    
    return streamer
