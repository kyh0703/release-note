import pytest

from release_note.errors import ConfigError
from release_note.versioning import TaggingVersion


def test_parse_tagging_version_supports_leading_v_and_suffix() -> None:
    version = TaggingVersion.parse("v6.2.0-b4h19")

    assert version.raw == "6.2.0-b4h19"
    assert version.semantic == "6.2.0"
    assert version.suffix == "b4h19"
    assert version.has_v_prefix is True


def test_next_patch_drops_suffix_and_increments_patch() -> None:
    version = TaggingVersion.parse("6.2.0-hotfix-h1")

    assert version.next_patch_name() == "6.2.1"
    assert version.previous_patch is None


def test_render_exposes_template_values() -> None:
    version = TaggingVersion.parse("6.2.3-b4h19")

    rendered = version.render("IPRON v{raw} -> {next_patch} -> {tag_version}")

    assert rendered == "IPRON v6.2.3-b4h19 -> 6.2.4 -> 6.2.3b4h19"


def test_invalid_tagging_version_raises() -> None:
    with pytest.raises(ConfigError, match="tagging-version"):
        TaggingVersion.parse("release-6.2")


def test_ordering_key_supports_natural_suffix_order() -> None:
    older = TaggingVersion.parse("6.2.0-b4h9")
    newer = TaggingVersion.parse("6.2.0-b4h10")

    assert older.ordering_key() < newer.ordering_key()


def test_next_patch_keeps_leading_v_prefix() -> None:
    version = TaggingVersion.parse("v5.1.1-b3h75")

    assert version.next_patch_name() == "v5.1.2"
    assert version.previous_patch == "v5.1.0"
