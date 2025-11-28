import asyncio
import logging
import sys
from utils import f1_auth, live_stream

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

async def verify_connection():
    try:
        logger.info("1. Testing Authentication...")
        # This should pick up the saved token
        auth_result = await f1_auth.authenticate_f1tv()
        
        if not auth_result.get("success"):
            logger.error("Authentication failed!")
            return
            
        token = auth_result["access_token"]
        logger.info(f"Authentication successful. Method: {auth_result.get('method')}")
        logger.info(f"Token (first 20 chars): {token[:20]}...")
        
        logger.info("\n2. Testing SignalR Connection...")
        # Start the stream
        streamer = live_stream.start_stream(access_token=token)
        
        # Wait a bit to see if we get connected
        logger.info("Waiting 10 seconds for connection and events...")
        await asyncio.sleep(10)
        
        info = streamer.get_stream_info()
        logger.info(f"\nStream Status: {'Connected' if info['is_connected'] else 'Disconnected'}")
        logger.info(f"Log file: {info['log_file']}")
        
        if info['is_connected']:
            logger.info("SUCCESS: SignalR connection established!")
        else:
            logger.error("FAILURE: Could not establish SignalR connection.")
            
        # Cleanup
        live_stream.stop_stream(info['stream_id'])
        
    except Exception as e:
        logger.exception(f"Verification failed: {e}")

if __name__ == "__main__":
    asyncio.run(verify_connection())
