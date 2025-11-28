"""
F1 TV Pro Authentication Utility
"""
import logging
import os
from pathlib import Path
from typing import Dict, Any, Optional

import httpx
import jwt
import platformdirs
import requests
from jwt.algorithms import RSAAlgorithm

logger = logging.getLogger(__name__)

# F1 TV Pro authentication endpoint (Legacy/Password)
F1_AUTH_URL = "https://api.formula1.com/v1/account/subscriber/authenticate/by-password"
JWKS_URL = "https://api.formula1.com/static/jwks.json"

# Token storage
USER_DATA_DIR = Path(platformdirs.user_data_dir("f1-dashboard", ensure_exists=True))
AUTH_DATA_FILE = USER_DATA_DIR / "f1auth.json"

# F1 API Key - must be set via environment variable F1_API_KEY (for password auth)
F1_API_KEY = os.getenv("F1_API_KEY", "")


def _get_jwk_from_jwks_uri(jwks_uri, kid):
    """Fetch the JWKS data and find the key with matching kid."""
    response = requests.get(jwks_uri)
    response.raise_for_status()
    jwks = response.json()

    for key in jwks['keys']:
        if key['kid'] == kid:
            return key
    raise ValueError("Public key not found in JWKS for given kid.")


def validate_subscription_token(token: str) -> bool:
    """
    Verify the JWT token against F1's public keys.
    """
    try:
        # Decode headers to get the kid
        unverified_header = jwt.get_unverified_header(token)
        kid = unverified_header.get('kid')
        
        if not kid:
            return False
            
        jwk = _get_jwk_from_jwks_uri(JWKS_URL, kid)

        # Convert JWK to public key
        public_key = RSAAlgorithm.from_jwk(jwk)

        # Verify and decode the token
        jwt.decode(
            token,
            key=public_key,
            algorithms=["RS256"],
            verify=True
        )
        return True
    except Exception as e:
        logger.warning(f"Token validation failed: {e}")
        return False


def get_saved_token() -> Optional[str]:
    """Retrieve the saved subscription token from file."""
    if AUTH_DATA_FILE.exists():
        try:
            with open(AUTH_DATA_FILE, 'r') as f:
                token = f.read().strip()
                if token:
                    return token
        except Exception as e:
            logger.error(f"Error reading auth file: {e}")
    return None


async def authenticate_f1tv(email: str = "", password: str = "") -> Dict[str, Any]:
    """
    Authenticate with F1 TV Pro.
    
    Prioritizes:
    1. Saved subscription token (verified)
    2. Email/Password (Legacy/Unreliable)
    """
    # 1. Try saved token
    token = get_saved_token()
    if token:
        if validate_subscription_token(token):
            logger.info("Using valid saved subscription token")
            return {
                "access_token": token,
                "success": True,
                "method": "token"
            }
        else:
            logger.warning("Saved token is invalid or expired")

    # 2. Try password auth (Legacy)
    if email and password:
        if not F1_API_KEY:
            raise Exception("F1_API_KEY required for password authentication")
            
        try:
            logger.info("Attempting password authentication for %s", email)
            async with httpx.AsyncClient() as client:
                headers = {
                    "Content-Type": "application/json",
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    "Origin": "https://www.formula1.com",
                    "apikey": F1_API_KEY,
                }
                
                response = await client.post(
                    F1_AUTH_URL,
                    headers=headers,
                    json={"Login": email, "Password": password},
                )
                response.raise_for_status()
                data = response.json()
                
                # Extract token logic (simplified from previous version)
                access_token = ""
                if isinstance(data, dict):
                    if "data" in data and "subscriptionToken" in data["data"]:
                        access_token = data["data"]["subscriptionToken"]
                    elif "SubscriptionToken" in data:
                        access_token = data["SubscriptionToken"]
                
                if access_token:
                    return {
                        "access_token": access_token,
                        "success": True,
                        "method": "password"
                    }
                    
        except Exception as e:
            logger.error(f"Password authentication failed: {e}")
            
    raise Exception("Authentication failed. Please use 'python auth_helper.py' to generate a new token.")
