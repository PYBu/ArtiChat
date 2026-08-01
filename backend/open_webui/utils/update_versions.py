import re


RELEASE_VERSION_PATTERN = re.compile(r"^\d+\.\d+\.\d+$")


def normalize_version(value: str) -> str:
    normalized = str(value or "").strip()
    if normalized.startswith("v"):
        normalized = normalized[1:]
    if not RELEASE_VERSION_PATTERN.fullmatch(normalized):
        raise ValueError("invalid release version")
    return normalized


def version_tuple(value: str) -> tuple[int, int, int]:
    return tuple(int(part) for part in normalize_version(value).split("."))


def version_is_newer(candidate: str, current: str) -> bool:
    return version_tuple(candidate) > version_tuple(current)
