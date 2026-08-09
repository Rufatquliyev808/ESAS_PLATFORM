from hashlib import sha256
from pathlib import Path

import pytest

from backend.app.storage.artifact_store import (
    ArtifactIntegrityError,
    ArtifactNotFoundError,
    InvalidChecksumError,
    artifact_path,
    get_artifact,
    get_artifact_root,
    has_artifact,
    put_artifact,
)


def checksum_of(content: bytes) -> str:
    return f"sha256:{sha256(content).hexdigest()}"


def test_artifact_path_is_deterministic() -> None:
    content = b"deterministic-png-bytes"
    checksum = checksum_of(content)
    first = artifact_path(checksum, extension="png")
    second = artifact_path(checksum, extension="png")
    assert first == second


def test_artifact_path_uses_sharded_directories() -> None:
    content = b"shard-check"
    checksum = checksum_of(content)
    hex_digest = checksum.removeprefix("sha256:")
    path = artifact_path(checksum, extension="png")
    assert path == get_artifact_root() / hex_digest[0:2] / hex_digest[2:4] / f"{hex_digest}.png"


def test_rejects_checksum_without_sha256_prefix() -> None:
    with pytest.raises(InvalidChecksumError):
        artifact_path("abc123", extension="png")


def test_rejects_checksum_with_wrong_length() -> None:
    with pytest.raises(InvalidChecksumError):
        artifact_path("sha256:abc123", extension="png")


def test_rejects_checksum_with_non_hex_characters() -> None:
    bad = "sha256:" + ("g" * 64)
    with pytest.raises(InvalidChecksumError):
        artifact_path(bad, extension="png")


def test_rejects_empty_extension() -> None:
    content = b"x"
    with pytest.raises(ValueError):
        artifact_path(checksum_of(content), extension="")


def test_put_and_get_roundtrip() -> None:
    content = b"\x89PNG\r\n\x1a\n-some-fake-png-bytes"
    checksum = checksum_of(content)
    put_artifact(checksum, content, extension="png")
    fetched = get_artifact(checksum, extension="png")
    assert fetched == content


def test_put_is_idempotent(tmp_path: Path) -> None:
    content = b"idempotent-content"
    checksum = checksum_of(content)
    first_path = put_artifact(checksum, content, extension="png")
    second_path = put_artifact(checksum, content, extension="png")
    assert first_path == second_path
    assert first_path.read_bytes() == content


def test_put_rejects_content_not_matching_declared_checksum() -> None:
    real_content = b"real-bytes"
    wrong_checksum = checksum_of(b"different-bytes")
    with pytest.raises(ArtifactIntegrityError):
        put_artifact(wrong_checksum, real_content, extension="png")


def test_has_artifact_false_before_put_true_after() -> None:
    content = b"presence-check"
    checksum = checksum_of(content)
    assert has_artifact(checksum, extension="png") is False
    put_artifact(checksum, content, extension="png")
    assert has_artifact(checksum, extension="png") is True


def test_get_raises_not_found_when_missing() -> None:
    content = b"never-stored"
    checksum = checksum_of(content)
    with pytest.raises(ArtifactNotFoundError):
        get_artifact(checksum, extension="png")


def test_get_detects_corruption_when_verify_true() -> None:
    content = b"will-be-corrupted"
    checksum = checksum_of(content)
    path = put_artifact(checksum, content, extension="png")
    path.write_bytes(b"corrupted-bytes-do-not-match-checksum")
    with pytest.raises(ArtifactIntegrityError):
        get_artifact(checksum, extension="png", verify=True)


def test_get_skips_verification_when_verify_false() -> None:
    content = b"will-be-corrupted-2"
    checksum = checksum_of(content)
    path = put_artifact(checksum, content, extension="png")
    path.write_bytes(b"corrupted-again")
    fetched = get_artifact(checksum, extension="png", verify=False)
    assert fetched == b"corrupted-again"


def test_isolated_test_artifact_root_is_not_the_real_production_directory() -> None:
    from backend.app.storage.artifact_store import DEFAULT_ARTIFACT_ROOT
    assert get_artifact_root() != DEFAULT_ARTIFACT_ROOT
