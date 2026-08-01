import pytest

from open_webui.utils.update_versions import normalize_version, version_is_newer


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("v0.1.2", "0.1.2"), ("0.1.2", "0.1.2"), (" 1.20.3 ", "1.20.3")],
)
def test_normalize_version_accepts_three_part_versions(raw, expected):
    assert normalize_version(raw) == expected


@pytest.mark.parametrize(
    "raw", ["", "latest", "1.2", "1.2.3-beta", "1.2.3;rm -rf /"]
)
def test_normalize_version_rejects_non_release_values(raw):
    with pytest.raises(ValueError, match="invalid release version"):
        normalize_version(raw)


def test_version_is_newer_compares_numerically():
    assert version_is_newer("0.1.10", "0.1.2") is True
    assert version_is_newer("0.1.2", "0.1.2") is False
    assert version_is_newer("0.1.1", "0.1.2") is False
