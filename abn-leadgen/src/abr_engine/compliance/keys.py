"""Separated encryption and HMAC material. Retired lookup keys preserve erased opt-outs."""

import base64
import hashlib
import hmac
import json
import os
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from cryptography.fernet import Fernet
from psycopg.types.json import Jsonb

from abr_engine.config import Settings


@dataclass
class KeyStore:
    encryption_key: bytes = field(repr=False)
    lookup_keys: dict[int, bytes] = field(repr=False)
    active_version: int = 1
    signing_key: str = field(default="", repr=False)
    compromised: bool = False
    dependencies: set[int] = field(default_factory=set)
    path: Path | None = field(default=None, repr=False)
    wrapping_key: bytes | None = field(default=None, repr=False)
    _loaded_digest: str | None = field(default=None, repr=False)

    def __post_init__(self):
        self.validate_material()

    def validate_material(self):
        try:
            encryption_material = base64.b64decode(self.encryption_key, altchars=b"-_", validate=True)
            Fernet(self.encryption_key)
        except (ValueError, TypeError) as exc:
            raise ValueError("Invalid encryption material") from exc
        if len(encryption_material) != 32 or self.active_version not in self.lookup_keys:
            raise ValueError("Active key version or encryption material invalid")
        if not self.lookup_keys or any(
            type(v) is not int or v <= 0 or not isinstance(k, bytes) or len(k) < 32
            for v, k in self.lookup_keys.items()
        ):
            raise ValueError("Positive lookup versions and at least 256-bit material required")
        if len(self.signing_key.encode()) < 32:
            raise ValueError("Signing material must be at least 256 bits")
        material = [encryption_material, self.signing_key.encode(), *self.lookup_keys.values()]
        if self.signing_key.encode() == self.encryption_key or len(set(material)) != len(material):
            raise ValueError("Encryption, lookup and signing material must be separate")
        if self.wrapping_key:
            try:
                wrapping = base64.b64decode(self.wrapping_key, altchars=b"-_", validate=True)
                Fernet(self.wrapping_key)
            except (ValueError, TypeError) as exc:
                raise ValueError("Invalid external key-store wrapping material") from exc
            if wrapping in material or self.wrapping_key == self.encryption_key:
                raise ValueError("Key-store wrapping material must be separate")

    def validate_dependencies(self, conn):
        """Freeze on missing prior keys before source matching or action checks."""
        from abr_engine.db import lock

        lock(conn, "control-authority")
        rows = conn.execute(
            "SELECT key_version FROM suppression_alias UNION SELECT key_version FROM suppression_event "
            "WHERE key_version IS NOT NULL UNION SELECT key_version FROM lead_source_link "
            "UNION SELECT token_key_version AS key_version FROM contact_record"
        ).fetchall()
        required = {row["key_version"] for row in rows} | self.dependencies
        if required - self.lookup_keys.keys():
            self.compromised = True
            raise ValueError("Authority frozen: retained records require unavailable lookup versions")
        # Version membership alone is insufficient: changing bytes under an existing
        # version also makes historical opt-outs unmatchable. Persist non-secret key
        # fingerprints before controlled writes; never reuse a known version.
        fingerprints = {str(v): hashlib.sha256(key).hexdigest() for v, key in self.lookup_keys.items()}
        registered = conn.execute(
            "SELECT value FROM system_state WHERE name='lookup_key_fingerprints'"
        ).fetchone()
        previous = registered["value"] if registered else {}
        if any(version in previous and previous[version] != value for version, value in fingerprints.items()):
            self.compromised = True
            raise ValueError("Authority frozen: lookup material changed under a known version")
        conn.execute(
            "INSERT INTO system_state(name,value) VALUES('lookup_key_fingerprints',%s) "
            "ON CONFLICT(name) DO UPDATE SET value=EXCLUDED.value",
            (Jsonb(previous | fingerprints),),
        )

    def save(self, path: Path | None = None):
        """Atomically persist an encrypted envelope; wrapping key lives outside the file.

        Exclusive sibling lock plus content CAS rejects concurrent/stale writers. The
        deployment must additionally restrict Windows ACLs and protect the external key.
        """
        self.validate_material()
        target = path or self.path
        if target is None or not target.is_absolute() or not self.wrapping_key:
            raise ValueError("Absolute key-store path and external wrapping key required")
        target.parent.mkdir(parents=True, exist_ok=True)
        lock_path = target.with_name(target.name + ".lock")
        lock_fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        temporary = None
        try:
            current = target.read_bytes() if target.exists() else None
            current_digest = hashlib.sha256(current).hexdigest() if current is not None else None
            if current_digest != self._loaded_digest:
                raise ValueError("Key-store changed; reload before mutation")
            payload = {
                "encryption_key": self.encryption_key.decode(),
                "lookup_keys": {str(v): base64.b64encode(k).decode() for v, k in self.lookup_keys.items()},
                "active_version": self.active_version,
                "signing_key": self.signing_key,
                "compromised": self.compromised,
            }
            encrypted = (
                Fernet(self.wrapping_key).encrypt(json.dumps(payload, sort_keys=True).encode()).decode()
            )
            encoded = json.dumps({"format": "fernet-v1", "payload": encrypted}, sort_keys=True).encode()
            fd, temporary = tempfile.mkstemp(prefix=target.name + ".", dir=target.parent)
            with os.fdopen(fd, "wb") as stream:
                stream.write(encoded)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, target)
            temporary = None
            self.path, self._loaded_digest = target, hashlib.sha256(encoded).hexdigest()
        finally:
            os.close(lock_fd)
            lock_path.unlink(missing_ok=True)
            if temporary:
                Path(temporary).unlink(missing_ok=True)

    def encrypt(self, value: str) -> str:
        return Fernet(self.encryption_key).encrypt(value.encode()).decode()

    def decrypt(self, value: str) -> str:
        return Fernet(self.encryption_key).decrypt(value.encode()).decode()

    def token(self, namespace: str, value: str, version: int | None = None) -> str:
        namespace = "phone" if namespace in {"mobile", "landline"} else namespace
        if version is not None and version != self.active_version:
            raise ValueError("Prior lookup versions are lookup-only")
        return self._token(namespace, value, self.active_version)

    def _token(self, namespace: str, value: str, version: int) -> str:
        namespace = "phone" if namespace in {"mobile", "landline"} else namespace
        return hmac.new(
            self.lookup_keys[version], (namespace + "\0" + value).encode(), hashlib.sha256
        ).hexdigest()

    def matches(self, namespace: str, value: str) -> list[tuple[int, str]]:
        return [(version, self._token(namespace, value, version)) for version in sorted(self.lookup_keys)]

    def rotate(self, version: int, material: bytes, conn=None):
        if conn is not None:
            self.validate_dependencies(conn)
        if version in self.lookup_keys or len(material) < 32:
            raise ValueError("New unique key version and 256-bit material required")
        prior_keys, prior_version = self.lookup_keys.copy(), self.active_version
        try:
            self.lookup_keys[version] = material
            self.active_version = version
            self.validate_material()
            if conn is not None:
                self.validate_dependencies(conn)
            if self.path:
                self.save()
        except (ValueError, OSError):
            self.lookup_keys, self.active_version = prior_keys, prior_version
            raise

    def retire(self, version: int, conn):
        self.validate_dependencies(conn)
        if version == self.active_version:
            raise ValueError("Cannot retire active key")
        count = conn.execute(
            "SELECT (SELECT count(*) FROM suppression_alias WHERE key_version=%s) + "
            "(SELECT count(*) FROM suppression_event WHERE key_version=%s) + "
            "(SELECT count(*) FROM lead_source_link WHERE key_version=%s) + "
            "(SELECT count(*) FROM contact_record WHERE token_key_version=%s) AS n",
            (version, version, version, version),
        ).fetchone()["n"]
        if count or version in self.dependencies:
            raise ValueError("Retained restrictions depend on this lookup key")
        old_material = self.lookup_keys.pop(version)
        try:
            if self.path:
                self.save()
        except (ValueError, OSError):
            self.lookup_keys[version] = old_material
            raise


def load_keys(settings: Settings, *, wrapping_key: bytes | None = None, conn=None) -> KeyStore:
    if settings.mode == "fixture":
        # Deliberately public deterministic material; fixture records and tokens are synthetic only.
        return KeyStore(
            base64.urlsafe_b64encode(hashlib.sha256(b"fixture-encryption-only").digest()),
            {1: hashlib.sha256(b"fixture-lookup-only").digest()},
            signing_key="fixture-signing-only-not-for-production-0000000000",
        )
    assert settings.key_file is not None
    wrapping_key = wrapping_key or os.environ.get("ABR_KEYSTORE_WRAPPING_KEY", "").encode()
    if not wrapping_key:
        raise ValueError("Live key store requires externally supplied wrapping material")
    return load_stored_keys(settings.key_file, wrapping_key=wrapping_key, conn=conn)


def load_stored_keys(path: Path, *, wrapping_key: bytes, conn=None) -> KeyStore:
    """Read a persistent encrypted store; custody of the wrapping key is external."""
    if not path.is_absolute() or not wrapping_key:
        raise ValueError("Absolute key store and external wrapping material required")
    content = path.read_bytes()
    envelope = json.loads(content)
    if envelope.get("format") != "fernet-v1":
        raise ValueError("Live key store must use an encrypted envelope")
    data = json.loads(Fernet(wrapping_key).decrypt(envelope["payload"].encode()))
    store = KeyStore(
        data["encryption_key"].encode(),
        {int(k): base64.b64decode(v, validate=True) for k, v in data["lookup_keys"].items()},
        data["active_version"],
        data["signing_key"],
        data.get("compromised", False),
        path=path,
        wrapping_key=wrapping_key,
        _loaded_digest=hashlib.sha256(content).hexdigest(),
    )
    if conn is not None:
        store.validate_dependencies(conn)
    return store
