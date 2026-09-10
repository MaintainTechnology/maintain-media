import io
import sys
from pathlib import Path

import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

sys.path.insert(0, str(Path(__file__).parents[2] / "ops/aws"))
from backup_crypto import CHUNK, BackupError, EncryptWriter, decrypt_stream
from backup_runtime import _artifact_path


@pytest.fixture(scope="module")
def recipient():
    return rsa.generate_private_key(public_exponent=65537, key_size=3072)


def encrypted(data, recipient):
    output = io.BytesIO()
    writer = EncryptWriter(output, recipient.public_key())
    writer.write(data)
    writer.finish()
    return output.getvalue()


@pytest.mark.parametrize("data", [b"", b"private synthetic fixture", b"x" * (CHUNK + 30)], ids=["empty", "small", "multiframe"])
def test_authenticated_roundtrip(data, recipient):
    content = encrypted(data, recipient)
    target = io.BytesIO()
    assert decrypt_stream(io.BytesIO(content), target, recipient) == len(data)
    assert target.getvalue() == data
    if data:
        assert data[:100] not in content


@pytest.mark.parametrize("mutation", ["truncate", "trailing", "tamper", "missing-final"])
def test_modified_stream_rejected(mutation, recipient):
    content = encrypted(b"sensitive synthetic fixture", recipient)
    if mutation == "truncate":
        content = content[:-1]
    elif mutation == "trailing":
        content += b"extra"
    elif mutation == "missing-final":
        content = content[:-21]
    else:
        content = content[:-25] + bytes([content[-25] ^ 1]) + content[-24:]
    with pytest.raises(BackupError):
        decrypt_stream(io.BytesIO(content), io.BytesIO(), recipient)


def test_wrong_key_and_limits(recipient):
    other = rsa.generate_private_key(public_exponent=65537, key_size=3072)
    content = encrypted(b"x" * 100, recipient)
    with pytest.raises(BackupError, match="RECIPIENT"):
        decrypt_stream(io.BytesIO(content), io.BytesIO(), other)
    with pytest.raises(BackupError, match="LIMIT"):
        decrypt_stream(io.BytesIO(content), io.BytesIO(), recipient, maximum=50)
    writer = EncryptWriter(io.BytesIO(), recipient.public_key(), maximum=50)
    with pytest.raises(BackupError, match="LIMIT"):
        writer.write(b"x" * 51)


def test_artifact_traversal_rejected_before_read(tmp_path):
    root = tmp_path / "data"
    root.mkdir()
    private = tmp_path / "outside"
    private.write_bytes(b"must never read")
    with pytest.raises(BackupError, match="PATH_INVALID"):
        _artifact_path(root, root / ".." / private.name)
