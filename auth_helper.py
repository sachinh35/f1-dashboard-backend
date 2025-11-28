import json
import threading
import urllib.parse
import webbrowser
import logging
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Optional

import jwt
import platformdirs
import requests
from jwt.algorithms import RSAAlgorithm
from jwt.exceptions import InvalidTokenError, PyJWTError

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Constants
JWKS_URL = "https://api.formula1.com/static/jwks.json"
USER_DATA_DIR = Path(platformdirs.user_data_dir("f1-dashboard", ensure_exists=True))
AUTH_DATA_FILE = USER_DATA_DIR / "f1auth.json"

# Global state for auth server
_auth_finished = threading.Event()
_subscription_token: Optional[str] = None


class AuthHandler(BaseHTTPRequestHandler):
    def _send_cors_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')

    def do_OPTIONS(self):
        self.send_response(200)
        self._send_cors_headers()
        self.end_headers()

    def do_POST(self):
        if self.path == '/auth':
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            try:
                data = json.loads(post_data.decode('utf-8'))
                
                # The F1 login page sends back a cookie string in "loginSession"
                cookie = data.get("loginSession")
                if not cookie:
                    raise ValueError("No loginSession in response")
                    
                decoded_string = urllib.parse.unquote(cookie)
                parsed_data = json.loads(decoded_string)

                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self._send_cors_headers()
                self.end_headers()
                self.wfile.write(json.dumps({"status": "ok"}).encode())

                global _subscription_token
                # Extract subscription token
                if "data" in parsed_data and "subscriptionToken" in parsed_data["data"]:
                    _subscription_token = parsed_data["data"]["subscriptionToken"]
                else:
                    logger.error("Could not find subscriptionToken in response data")
                    
                _auth_finished.set()
                
            except Exception as e:
                logger.error(f"Error processing auth request: {e}")
                self.send_response(400)
                self.end_headers()


def _get_jwk_from_jwks_uri(jwks_uri, kid):
    """Fetch the JWKS data and find the key with matching kid."""
    response = requests.get(jwks_uri)
    response.raise_for_status()
    jwks = response.json()

    for key in jwks['keys']:
        if key['kid'] == kid:
            return key
    raise ValueError("Public key not found in JWKS for given kid.")


def verify_token(token: str) -> bool:
    """Verify the JWT token against F1's public keys."""
    try:
        # Decode headers to get the kid
        unverified_header = jwt.get_unverified_header(token)
        kid = unverified_header.get('kid')
        
        if not kid:
            logger.error("Token header does not contain 'kid'")
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
        logger.error(f"Token verification failed: {e}")
        return False


def run_auth_flow():
    """Run the browser-based authentication flow."""
    server_address = ('127.0.0.1', 0)
    httpd = HTTPServer(server_address, AuthHandler)
    port = httpd.server_port

    auth_url = f'https://f1login.fastf1.dev?port={port}'
    print(f'\nOpening browser to authenticate with F1 TV Pro...')
    print(f'If browser does not open, please visit:\n{auth_url}\n')

    webbrowser.open(auth_url)

    _auth_finished.clear()
    server_thread = threading.Thread(target=httpd.serve_forever)
    server_thread.daemon = True
    server_thread.start()
    
    try:
        # Wait for auth to complete (timeout after 5 minutes)
        if _auth_finished.wait(timeout=300):
            if _subscription_token:
                logger.info("Authentication successful! Verifying token...")
                if verify_token(_subscription_token):
                    logger.info("Token verified successfully.")
                    
                    # Save token to file
                    AUTH_DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
                    with open(AUTH_DATA_FILE, 'w') as f:
                        f.write(_subscription_token)
                    logger.info(f"Token saved to {AUTH_DATA_FILE}")
                    print(f"\nSUCCESS: Authentication complete. Token saved.")
                    return True
                else:
                    logger.error("Token verification failed.")
            else:
                logger.error("Authentication finished but no token received.")
        else:
            logger.error("Authentication timed out.")
            
    except KeyboardInterrupt:
        logger.info("Authentication interrupted by user.")
    finally:
        httpd.shutdown()
        
    return False


if __name__ == "__main__":
    run_auth_flow()
