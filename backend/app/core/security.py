import hmac
import hashlib
from typing import Optional


def verify_github_signature(
    payload_bytes: bytes,
    signature_header: Optional[str],
    secret: str
) -> bool:
    """
    Verify HMAC SHA-256 webhook signature from GitHub (X-Hub-Signature-256 header).
    Uses hmac.compare_digest to defend against timing attacks.
    """
    if not signature_header or not secret:
        return False

    if not signature_header.startswith("sha256="):
        return False

    expected_signature = signature_header.split("sha256=", 1)[1]
    mac = hmac.new(secret.encode("utf-8"), msg=payload_bytes, digestmod=hashlib.sha256)
    computed_signature = mac.hexdigest()

    return hmac.compare_digest(computed_signature, expected_signature)
