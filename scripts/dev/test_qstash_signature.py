import time
import hmac
import hashlib
import base64
import json
import urllib.request
import os
from dotenv import load_dotenv

load_dotenv()

# We need to simulate the signing process QStash uses.
# QStash signs the raw body with HMAC-SHA256 and creates a JWT.
# Actually, the upstash-qstash library verifies a JWT. 
# We can just use the qstash python library to generate a valid signature?
# No, `qstash.Receiver` only verifies. But we can construct the JWT manually.
import jwt 

def create_qstash_signature(body: str, signing_key: str, url: str) -> str:
    """Generate a valid QStash JWT signature."""
    now = int(time.time())
    
    # QStash hashes the body using SHA-256
    body_hash = hashlib.sha256(body.encode('utf-8')).digest()
    body_hash_b64 = base64.urlsafe_b64encode(body_hash).decode('utf-8').rstrip('=')
    
    payload = {
        "iss": "Upstash",
        "sub": url,
        "exp": now + 300,
        "nbf": now - 300,
        "iat": now,
        "jti": "test-jti-123",
        "body": body_hash_b64
    }
    
    token = jwt.encode(payload, signing_key, algorithm="HS256")
    return token

def test_local_endpoint():
    current_key = os.getenv("QSTASH_CURRENT_SIGNING_KEY", "sig_test123")
    url = "http://localhost:10000/api/v1/admin/score-now"
    body = ""
    
    # Generate signature
    signature = create_qstash_signature(body, current_key, url)
    
    print(f"Generated signature: {signature}")
    
    req = urllib.request.Request(url, data=body.encode('utf-8'), method="POST")
    req.add_header("Upstash-Signature", signature)
    
    try:
        with urllib.request.urlopen(req) as response:
            print("Success!", response.read().decode('utf-8'))
    except Exception as e:
        if hasattr(e, 'read'):
            print("Failed:", e.read().decode('utf-8'))
        else:
            print("Error:", e)

if __name__ == "__main__":
    test_local_endpoint()
