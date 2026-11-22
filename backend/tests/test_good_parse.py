import json

import pytest

from app.good.parse import GoodArtifact, GoodFormatError, GoodWeapon, parse_good
from helpers import FIXTURES


def raw(**over) -> bytes:
    body = {"format": "GOOD", "version": 2, "source": "X"}
    body.update(over)
    return json.dumps(body).encode()


def test_parses_the_sample():
    f = parse_good((FIXTURES / "good_sample.json").read_bytes())
    assert f.version == 2 and f.source == "Test_Scanner"
    assert f.materials["Mora"] == 1234567 and len(f.materials) == 6
    assert f.weapons[0] == GoodWeapon("FavoniusSword", 90, 6, 3, "Bennett", True)
    assert len(f.weapons) == 4
    assert f.artifacts[0] == GoodArtifact("GladiatorsFinale", "flower", 5, 20, "hp",
                                          (("critRate_", 3.9), ("atk_", 5.8)), "TravelerAnemo", True)
    assert len(f.artifacts) == 3


@pytest.mark.parametrize("version", [1, 2, 3])
def test_supported_versions(version):
    assert parse_good(raw(version=version)).version == version


def test_missing_blocks_are_empty_and_unknown_fields_ignored():
    f = parse_good(raw(materials={"Mora": 5}, somethingNew={"a": 1}))
    assert f.materials == {"Mora": 5} and f.weapons == [] and f.artifacts == []


def test_utf8_bom_is_accepted():
    assert parse_good(b"\xef\xbb\xbf" + raw()).version == 2


def test_source_is_truncated_and_optional():
    assert parse_good(raw(source="S" * 100)).source == "S" * 64
    body = json.loads(raw())
    del body["source"]
    assert parse_good(json.dumps(body).encode()).source is None


@pytest.mark.parametrize("content, message", [
    (b"not json", "Not a GOOD file (could not read JSON)"),
    (b"\xff\xfe\x00", "Not a GOOD file (could not read JSON)"),
    (b"[1, 2]", "Not a GOOD file"),
    (json.dumps({"format": "XYZ", "version": 2}).encode(), "Not a GOOD file"),
    (json.dumps({"format": "GOOD", "version": 9}).encode(), "Unsupported GOOD version 9"),
    (json.dumps({"format": "GOOD", "version": "2"}).encode(), "Unsupported GOOD version 2"),
])
def test_whole_file_errors(content, message):
    with pytest.raises(GoodFormatError) as e:
        parse_good(content)
    assert str(e.value) == message


@pytest.mark.parametrize("over, block", [
    ({"materials": [1, 2]}, "materials"),
    ({"materials": {"Mora": -1}}, "materials"),
    ({"materials": {"Mora": True}}, "materials"),
    ({"materials": {"Mora": "5"}}, "materials"),
    ({"weapons": {"a": 1}}, "weapons"),
    ({"weapons": [{"key": "X"}]}, "weapons"),
    ({"weapons": [{"key": "", "level": 1, "refinement": 1}]}, "weapons"),
    ({"artifacts": [{"setKey": "A", "slotKey": "boots", "rarity": 5, "level": 0, "mainStatKey": "hp"}]}, "artifacts"),
    ({"artifacts": [{"setKey": "A", "slotKey": "flower", "rarity": 5, "level": 0}]}, "artifacts"),
    ({"artifacts": [{"setKey": "A", "slotKey": "flower", "rarity": 5, "level": 0, "mainStatKey": "hp",
                     "substats": "x"}]}, "artifacts"),
])
def test_block_errors_name_the_block(over, block):
    with pytest.raises(GoodFormatError) as e:
        parse_good(raw(**over))
    assert block in str(e.value)


def test_deeply_nested_json_is_a_format_error():
    with pytest.raises(GoodFormatError, match="could not read JSON"):
        parse_good(b"[" * 100_000)
