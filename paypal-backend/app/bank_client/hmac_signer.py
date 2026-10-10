import time
import hmac
import hashlib


def sign_request(method: str, path: str, body: str, timestamp: str, secret: str) -> str:
    message = f"{method}\n{path}\n{body}\n{timestamp}"
    return hmac.new(secret.encode("utf-8"), message.encode("utf-8"), hashlib.sha256).hexdigest()


def build_bank_headers(
    method: str, path: str, body_str: str, api_key: str, hmac_secret: str, request_id: str = ""
) -> dict:
    timestamp = str(int(time.time()))
    signature = sign_request(method, path, body_str, timestamp, hmac_secret)
    headers = {
        "X-Api-Key": api_key,
        "X-Timestamp": timestamp,
        "X-Signature": signature,
        "Content-Type": "application/json",
    }
    if request_id:
        headers["X-Request-ID"] = request_id
    return headers

