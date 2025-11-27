"""
F1 TV Pro Authentication Utility
Simple email/password authentication using F1's /authenticate/by-password endpoint.
"""
import httpx
import logging
import os
from typing import Dict, Any

logger = logging.getLogger(__name__)

# F1 TV Pro authentication endpoint
F1_AUTH_URL = "https://api.formula1.com/v1/account/subscriber/authenticate/by-password"

# F1 API Key - must be set via environment variable F1_API_KEY
F1_API_KEY = os.getenv("F1_API_KEY", "")


async def authenticate_f1tv(email: str, password: str) -> Dict[str, Any]:
    """
    Authenticate with F1 TV Pro using email and password.
    
    Args:
        email: F1 TV Pro account email
        password: F1 TV Pro account password
        
    Returns:
        Dictionary containing access_token, cookies, and other auth data
        
    Raises:
        Exception: If authentication fails or F1_API_KEY is not set
    """
    if not F1_API_KEY:
        error_msg = (
            "F1_API_KEY environment variable is required. "
            "Please set it before running the application.\n"
            "To find the API key:\n"
            "1. Open https://www.formula1.com in a browser\n"
            "2. Open Developer Tools (F12) -> Network tab\n"
            "3. Filter by 'api.formula1.com'\n"
            "4. Make any API request (e.g., try to log in)\n"
            "5. Check the request headers for the 'apikey' value\n"
            "6. Set it: export F1_API_KEY='your_key_here'"
        )
        logger.error(error_msg)
        raise Exception(error_msg)
    
    try:
        logger.info("Authenticating with F1 TV Pro for email: %s", email)
        
        async with httpx.AsyncClient() as client:
            # Build headers
            headers = {
                "Content-Type": "application/json",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Origin": "https://www.formula1.com",
                "Referer": "https://www.formula1.com/",
                "apikey": F1_API_KEY,
            }
            
            response = await client.post(
                F1_AUTH_URL,
                headers=headers,
                json={
                    "Login": email,
                    "Password": password,
                },
            )
            
            response.raise_for_status()
            data = response.json()
            
            # Extract cookies from response headers
            cookies = response.headers.get("set-cookie", "")
            
            # Extract token from response
            access_token = ""
            
            # Try various possible token fields
            if isinstance(data, dict):
                if "token" in data:
                    access_token = data["token"]
                elif "data" in data and isinstance(data["data"], dict):
                    if "token" in data["data"]:
                        access_token = data["data"]["token"]
                    elif "subscriptionToken" in data["data"]:
                        access_token = data["data"]["subscriptionToken"]
                elif "SubscriptionToken" in data:
                    access_token = data["SubscriptionToken"]
                elif "Data" in data and isinstance(data["Data"], dict):
                    if "SubscriptionToken" in data["Data"]:
                        access_token = data["Data"]["SubscriptionToken"]
            
            # Fallback to cookies if no token found in response
            if not access_token:
                if cookies:
                    access_token = cookies
                else:
                    # Last resort: use response data as string
                    access_token = str(data)
            
            logger.info("F1 TV Pro authentication successful")
            
            return {
                "access_token": access_token,
                "cookies": cookies,
                "data": data,
                "success": True,
            }
            
    except httpx.HTTPStatusError as e:
        error_msg = f"F1 TV Pro authentication failed with status {e.response.status_code}: {e.response.text}"
        logger.error(error_msg)
        raise Exception(error_msg)
    except Exception as e:
        error_msg = f"F1 TV Pro authentication error: {str(e)}"
        logger.error(error_msg)
        raise Exception(error_msg)
