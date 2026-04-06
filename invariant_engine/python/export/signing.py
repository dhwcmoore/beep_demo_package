"""Ed25519 signing and verification for audit payloads.

The signature covers the same canonical bytes as the SHA-256 integrity
hash (i.e. the payload with the ``integrity`` field removed and keys
sorted).  Hash and signature are therefore always over identical content.

Requires: cryptography >= 41  (already in requirements.txt)
"""
from __future__ import annotations

import base64
from typing import Tuple

from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    NoEncryption,
    PrivateFormat,
    PublicFormat,
    load_pem_private_key,
    load_pem_public_key,
)


def generate_keypair() -> Tuple[str, str]:
    """Return (private_key_pem, public_key_pem) as ASCII strings."""
    private_key = Ed25519PrivateKey.generate()
    private_pem = private_key.private_bytes(
        encoding=Encoding.PEM,
        format=PrivateFormat.PKCS8,
        encryption_algorithm=NoEncryption(),
    ).decode("ascii")
    public_pem = private_key.public_key().public_bytes(
        encoding=Encoding.PEM,
        format=PublicFormat.SubjectPublicKeyInfo,
    ).decode("ascii")
    return private_pem, public_pem


def public_pem_from_private_pem(private_pem: str) -> str:
    """Extract and return the public key PEM from a private key PEM."""
    private_key = load_pem_private_key(private_pem.encode("ascii"), password=None)
    if not isinstance(private_key, Ed25519PrivateKey):
        raise ValueError("PEM does not contain an Ed25519 private key")
    return private_key.public_key().public_bytes(
        encoding=Encoding.PEM,
        format=PublicFormat.SubjectPublicKeyInfo,
    ).decode("ascii")


def sign_payload(canonical_bytes: bytes, private_pem: str) -> str:
    """Return base64-encoded Ed25519 signature over *canonical_bytes*."""
    private_key = load_pem_private_key(private_pem.encode("ascii"), password=None)
    if not isinstance(private_key, Ed25519PrivateKey):
        raise ValueError("PEM does not contain an Ed25519 private key")
    return base64.b64encode(private_key.sign(canonical_bytes)).decode("ascii")


def verify_signature(canonical_bytes: bytes, sig_b64: str, public_pem: str) -> None:
    """Raise ``ValueError`` if the signature does not verify; return normally if valid."""
    from cryptography.exceptions import InvalidSignature

    public_key = load_pem_public_key(public_pem.encode("ascii"))
    if not isinstance(public_key, Ed25519PublicKey):
        raise ValueError("PEM does not contain an Ed25519 public key")
    try:
        public_key.verify(base64.b64decode(sig_b64), canonical_bytes)
    except InvalidSignature as exc:
        raise ValueError("Ed25519 signature verification failed") from exc
