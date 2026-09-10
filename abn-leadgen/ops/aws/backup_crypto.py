"""Bounded authenticated backup stream; backup hosts need only an RSA public key.

Every frame authenticates its ordinal and header. A mandatory final frame detects
truncation; decryption is for private quarantine staging, never an active target.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import struct
from typing import BinaryIO

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

MAGIC = b"ABRBACKUP1\n"
CHUNK = 4 * 1024 * 1024
MAX_PLAINTEXT = 100 * 1024**3


class BackupError(RuntimeError):
    pass


def public_key(data: bytes):
    key = serialization.load_pem_public_key(data)
    if not isinstance(key, rsa.RSAPublicKey) or key.key_size < 3072:
        raise BackupError("BACKUP_RSA_3072_OR_STRONGER_REQUIRED")
    return key


def fingerprint(key) -> str:
    key = key.public_key() if isinstance(key, rsa.RSAPrivateKey) else key
    return hashlib.sha256(key.public_bytes(serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo)).hexdigest()


class EncryptWriter:
    def __init__(self, target: BinaryIO, key, *, maximum=MAX_PLAINTEXT):
        if not isinstance(key, rsa.RSAPublicKey) or key.key_size < 3072 or not 1 <= maximum <= MAX_PLAINTEXT:
            raise BackupError("BACKUP_ENCRYPTION_CONFIGURATION_INVALID")
        self.target, self.maximum = target, maximum
        material = AESGCM.generate_key(bit_length=256)
        self.cipher, self.nonce = AESGCM(material), os.urandom(8)
        header = json.dumps({"format": "rsa-oaep-sha256-aes256gcm-frames-v1", "recipient": fingerprint(key),
            "wrapped_key": base64.b64encode(key.encrypt(material, padding.OAEP(mgf=padding.MGF1(hashes.SHA256()), algorithm=hashes.SHA256(), label=MAGIC))).decode(),
            "nonce_prefix": base64.b64encode(self.nonce).decode()}, sort_keys=True, separators=(",", ":")).encode()
        self.aad = hashlib.sha256(header).digest()
        self.buffer = bytearray()
        self.total = self.index = 0
        self.finished = False
        target.write(MAGIC + struct.pack("!I", len(header)) + header)

    def write(self, content: bytes) -> int:
        if self.finished:
            raise BackupError("BACKUP_STREAM_ALREADY_FINISHED")
        if self.total + len(content) > self.maximum:
            raise BackupError("BACKUP_PLAINTEXT_LIMIT")
        self.total += len(content)
        view = memoryview(content)
        while view:
            count = min(CHUNK - len(self.buffer), len(view))
            self.buffer.extend(view[:count])
            view = view[count:]
            if len(self.buffer) == CHUNK:
                self._frame(bytes(self.buffer), 0)
                self.buffer.clear()
        return len(content)

    def _frame(self, data, final):
        ordinal = struct.pack("!I", self.index)
        encrypted = self.cipher.encrypt(self.nonce + ordinal, data, self.aad + ordinal + bytes([final]))
        self.target.write(bytes([final]) + struct.pack("!I", len(encrypted)) + encrypted)
        self.index += 1

    def finish(self):
        if self.finished:
            raise BackupError("BACKUP_STREAM_ALREADY_FINISHED")
        if self.buffer:
            self._frame(bytes(self.buffer), 0)
            self.buffer.clear()
        self._frame(b"", 1)
        self.target.flush()
        self.finished = True

    def flush(self):
        self.target.flush()


def _exact(stream, count):
    chunks = bytearray()
    while len(chunks) < count:
        part = stream.read(count - len(chunks))
        if not part:
            raise BackupError("BACKUP_TRUNCATED")
        chunks.extend(part)
    return bytes(chunks)


def decrypt_stream(source: BinaryIO, target: BinaryIO, private_key, *, maximum=MAX_PLAINTEXT):
    if (not isinstance(private_key, rsa.RSAPrivateKey) or private_key.key_size < 3072
        or not 1 <= maximum <= MAX_PLAINTEXT):
        raise BackupError("BACKUP_PRIVATE_KEY_REQUIRED")
    try:
        if _exact(source, len(MAGIC)) != MAGIC:
            raise BackupError("BACKUP_FORMAT_INVALID")
        length = struct.unpack("!I", _exact(source, 4))[0]
        if not 1 <= length <= 16384:
            raise BackupError("BACKUP_HEADER_LIMIT")
        encoded = _exact(source, length)
        header = json.loads(encoded)
        if header["format"] != "rsa-oaep-sha256-aes256gcm-frames-v1" or header["recipient"] != fingerprint(private_key):
            raise BackupError("BACKUP_RECIPIENT_MISMATCH")
        material = private_key.decrypt(base64.b64decode(header["wrapped_key"], validate=True), padding.OAEP(mgf=padding.MGF1(hashes.SHA256()), algorithm=hashes.SHA256(), label=MAGIC))
        nonce = base64.b64decode(header["nonce_prefix"], validate=True)
        if len(nonce) != 8 or len(material) != 32:
            raise BackupError("BACKUP_FORMAT_INVALID")
        cipher, aad = AESGCM(material), hashlib.sha256(encoded).digest()
        total = index = 0
        while True:
            final = _exact(source, 1)[0]
            length = struct.unpack("!I", _exact(source, 4))[0]
            if final not in (0, 1) or not 16 <= length <= CHUNK + 16 or final and length != 16:
                raise BackupError("BACKUP_FRAME_INVALID")
            ordinal = struct.pack("!I", index)
            plaintext = cipher.decrypt(nonce + ordinal, _exact(source, length), aad + ordinal + bytes([final]))
            total += len(plaintext)
            if total > maximum:
                raise BackupError("BACKUP_PLAINTEXT_LIMIT")
            if final:
                if source.read(1):
                    raise BackupError("BACKUP_TRAILING_BYTES")
                target.flush()
                return total
            target.write(plaintext)
            index += 1
    except BackupError:
        raise
    except Exception:  # noqa: BLE001 -- intentionally redact all cryptographic provider diagnostics
        raise BackupError("BACKUP_AUTHENTICATION_FAILED") from None
