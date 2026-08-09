from hashlib import sha256
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_ARTIFACT_ROOT = PROJECT_ROOT / "storage" / "artifacts"
_artifact_root = DEFAULT_ARTIFACT_ROOT


class InvalidChecksumError(ValueError):
    pass


class ArtifactNotFoundError(LookupError):
    pass


class ArtifactIntegrityError(RuntimeError):
    pass


def get_artifact_root() -> Path:
    return _artifact_root


def configure_artifact_root(artifact_root: Path | None) -> None:
    """Mirrors `connection.py`'s `configure_database_path()` -- lets tests
    and scratch verification point the store at an isolated directory
    without touching the real production artifact tree.
    """
    global _artifact_root
    _artifact_root = DEFAULT_ARTIFACT_ROOT if artifact_root is None else artifact_root.resolve()


def _parse_checksum(checksum: str) -> str:
    normalized = checksum.strip()
    if not normalized.startswith("sha256:"):
        raise InvalidChecksumError("checksum must be in 'sha256:<hex>' form")
    hex_digest = normalized[len("sha256:") :]
    if len(hex_digest) != 64 or any(char not in "0123456789abcdef" for char in hex_digest.lower()):
        raise InvalidChecksumError("checksum must contain a 64-character hex sha256 digest")
    return hex_digest.lower()


def artifact_path(checksum: str, *, extension: str) -> Path:
    """Deterministically derive an artifact's on-disk path from its
    checksum -- the same checksum and extension always resolve to the same
    path, so no separate "location" column is ever needed in the database.
    """
    normalized_extension = extension.strip().lstrip(".")
    if not normalized_extension:
        raise ValueError("extension must not be empty")
    hex_digest = _parse_checksum(checksum)
    return (
        get_artifact_root()
        / hex_digest[0:2]
        / hex_digest[2:4]
        / f"{hex_digest}.{normalized_extension}"
    )


def has_artifact(checksum: str, *, extension: str) -> bool:
    return artifact_path(checksum, extension=extension).is_file()


def put_artifact(checksum: str, content: bytes, *, extension: str) -> Path:
    """Idempotently write `content` under its content-addressed path. If an
    artifact already exists at that path, this is a no-op (content-addressed
    storage means the same checksum can only ever mean the same bytes).
    Does not re-verify pre-existing files on every write -- that is what
    `get_artifact(verify=True)` is for.
    """
    expected_hex = _parse_checksum(checksum)
    actual_hex = sha256(content).hexdigest()
    if actual_hex != expected_hex:
        raise ArtifactIntegrityError(
            "content does not match the declared checksum -- refusing to store it"
        )

    path = artifact_path(checksum, extension=extension)
    if path.is_file():
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_bytes(content)
    tmp_path.replace(path)
    return path


def get_artifact(checksum: str, *, extension: str, verify: bool = True) -> bytes:
    path = artifact_path(checksum, extension=extension)
    if not path.is_file():
        raise ArtifactNotFoundError(f"no artifact stored for checksum {checksum}")
    content = path.read_bytes()
    if verify:
        expected_hex = _parse_checksum(checksum)
        actual_hex = sha256(content).hexdigest()
        if actual_hex != expected_hex:
            raise ArtifactIntegrityError(
                f"artifact at {path} does not match its declared checksum -- possible corruption"
            )
    return content
