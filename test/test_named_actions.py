import os
import tempfile

import pytest
import ruamel.yaml

from gmail_filter_manager.constants import generate_action_set_name
from gmail_filter_manager.gfm_extract import extract_named_actions, gfm_extract
from gmail_filter_manager.gfm_make import gfm_make

# --- Unit tests for extract_named_actions ---


def _dqs(s):
    """Shortcut to create DoubleQuotedScalarString."""
    from ruamel.yaml.scalarstring import DoubleQuotedScalarString

    return DoubleQuotedScalarString(s)


def test_no_duplicates_returns_unchanged():
    filters = [
        {"from": "a@example.com", "shouldTrash": "true"},
        {"from": "b@example.com", "shouldStar": "true"},
    ]
    result = extract_named_actions(filters)
    assert result == filters


def test_duplicates_are_factored_out():
    filters = [
        {"from": "a@example.com", "shouldTrash": "true", "label": "junk"},
        {"from": "b@example.com", "shouldTrash": "true", "label": "junk"},
        {"from": "c@example.com", "shouldStar": "true"},
    ]
    result = extract_named_actions(filters)

    # First entry should be the named action set
    assert "name" in result[0]
    assert result[0]["shouldTrash"] == "true"
    assert result[0]["label"] == "junk"

    # Next two should reference it
    assert result[1]["from"] == "a@example.com"
    assert result[1]["action"] == result[0]["name"]
    assert "shouldTrash" not in result[1]
    assert "label" not in result[1]

    assert result[2]["from"] == "b@example.com"
    assert result[2]["action"] == result[0]["name"]

    # Last should be unchanged
    assert result[3]["from"] == "c@example.com"
    assert result[3]["shouldStar"] == "true"
    assert "action" not in result[3]


def test_multiple_different_duplicates():
    filters = [
        {"from": "a@example.com", "shouldTrash": "true"},
        {"from": "b@example.com", "shouldTrash": "true"},
        {"from": "c@example.com", "shouldStar": "true"},
        {"from": "d@example.com", "shouldStar": "true"},
    ]
    result = extract_named_actions(filters)

    # Should have 2 named entries + 4 filters = 6 total
    assert len(result) == 6
    named = [f for f in result if "name" in f]
    assert len(named) == 2


def test_empty_actions_not_deduplicated():
    filters = [
        {"from": "a@example.com"},
        {"from": "b@example.com"},
    ]
    result = extract_named_actions(filters)
    assert len(result) == 2
    assert all("name" not in f for f in result)


# --- Unit tests for generate_action_set_name ---


def test_name_generation_two_keys():
    name = generate_action_set_name(
        {"label": "x", "shouldTrash": "true"}, set()
    )
    assert name == "label_and_shouldTrash"


def test_name_generation_three_keys():
    name = generate_action_set_name(
        {"label": "x", "shouldTrash": "true", "shouldStar": "true"}, set()
    )
    assert name == "label_plus_2"


def test_name_generation_collision():
    existing = {"label_and_shouldTrash"}
    name = generate_action_set_name(
        {"label": "x", "shouldTrash": "true"}, existing
    )
    assert name == "label_and_shouldTrash_2"


def test_name_generation_single_key():
    name = generate_action_set_name({"shouldTrash": "true"}, set())
    assert name == "shouldTrash"


# --- Integration tests: gfm_make with named actions ---


def _make_yaml_file(data):
    """Write data to a temp YAML file and return the path."""
    yaml = ruamel.yaml.YAML()
    yaml.indent(mapping=2, sequence=4, offset=2)
    fd, path = tempfile.mkstemp(suffix=".yaml")
    os.close(fd)
    with open(path, "w") as f:
        yaml.dump(data, f)
    return path


def _read_xml(path):
    """Read XML file contents."""
    with open(path) as f:
        return f.read()


def test_gfm_make_expands_named_actions():
    data = {
        "filters": [
            {"name": "junk", "label": "junk", "shouldTrash": "true"},
            {"from": "a@example.com", "action": "junk"},
            {"from": "b@example.com", "action": "junk"},
        ]
    }
    yaml_path = _make_yaml_file(data)
    fd, xml_path = tempfile.mkstemp(suffix=".xml")
    os.close(fd)
    try:
        gfm_make([yaml_path, xml_path])
        xml_content = _read_xml(xml_path)

        # Should have 2 entries (named action set is not emitted)
        assert xml_content.count("<entry>") == 2

        # Both entries should have the expanded actions
        assert xml_content.count('name="shouldTrash"') == 2
        assert xml_content.count('name="label" value="junk"') == 2

        # Both should have their criteria
        assert 'value="a@example.com"' in xml_content
        assert 'value="b@example.com"' in xml_content

        # action itself should NOT appear as a property
        assert 'name="action"' not in xml_content
        assert 'name="name"' not in xml_content
    finally:
        os.unlink(yaml_path)
        os.unlink(xml_path)


def test_gfm_make_backward_compat():
    """YAML without named actions works as before."""
    data = {
        "filters": [
            {"from": "a@example.com", "shouldTrash": "true"},
        ]
    }
    yaml_path = _make_yaml_file(data)
    fd, xml_path = tempfile.mkstemp(suffix=".xml")
    os.close(fd)
    try:
        gfm_make([yaml_path, xml_path])
        xml_content = _read_xml(xml_path)
        assert xml_content.count("<entry>") == 1
        assert 'name="from" value="a@example.com"' in xml_content
        assert 'name="shouldTrash" value="true"' in xml_content
    finally:
        os.unlink(yaml_path)
        os.unlink(xml_path)


def test_gfm_make_unknown_action_raises():
    data = {
        "filters": [
            {"from": "a@example.com", "action": "nonexistent"},
        ]
    }
    yaml_path = _make_yaml_file(data)
    fd, xml_path = tempfile.mkstemp(suffix=".xml")
    os.close(fd)
    try:
        with pytest.raises(ValueError, match="unknown named action"):
            gfm_make([yaml_path, xml_path])
    finally:
        os.unlink(yaml_path)
        os.unlink(xml_path)


def test_gfm_make_mixed_action_raises():
    data = {
        "filters": [
            {"name": "junk", "shouldTrash": "true"},
            {
                "from": "a@example.com",
                "action": "junk",
                "shouldStar": "true",
            },
        ]
    }
    yaml_path = _make_yaml_file(data)
    fd, xml_path = tempfile.mkstemp(suffix=".xml")
    os.close(fd)
    try:
        with pytest.raises(ValueError, match="explicit action properties"):
            gfm_make([yaml_path, xml_path])
    finally:
        os.unlink(yaml_path)
        os.unlink(xml_path)


def test_gfm_make_named_action_with_multi_label():
    data = {
        "filters": [
            {"name": "multi", "label": ["LabelA", "LabelB"]},
            {"from": "a@example.com", "action": "multi"},
        ]
    }
    yaml_path = _make_yaml_file(data)
    fd, xml_path = tempfile.mkstemp(suffix=".xml")
    os.close(fd)
    try:
        gfm_make([yaml_path, xml_path])
        xml_content = _read_xml(xml_path)
        # Multi-label creates separate entries
        assert xml_content.count("<entry>") == 2
        assert 'value="LabelA"' in xml_content
        assert 'value="LabelB"' in xml_content
    finally:
        os.unlink(yaml_path)
        os.unlink(xml_path)


# --- Integration tests: gfm_extract deduplication ---


DUPLICATE_XML = """\
<?xml version='1.0' encoding='UTF-8'?>
<feed xmlns='http://www.w3.org/2005/Atom'
      xmlns:apps='http://schemas.google.com/apps/2006'>
  <entry>
    <apps:property name='from' value='a@example.com'/>
    <apps:property name='shouldTrash' value='true'/>
    <apps:property name='label' value='junk'/>
  </entry>
  <entry>
    <apps:property name='from' value='b@example.com'/>
    <apps:property name='shouldTrash' value='true'/>
    <apps:property name='label' value='junk'/>
  </entry>
  <entry>
    <apps:property name='from' value='c@example.com'/>
    <apps:property name='shouldStar' value='true'/>
  </entry>
</feed>
"""


def test_gfm_extract_deduplicates():
    fd_xml, xml_path = tempfile.mkstemp(suffix=".xml")
    os.close(fd_xml)
    fd_yaml, yaml_path = tempfile.mkstemp(suffix=".yaml")
    os.close(fd_yaml)
    try:
        with open(xml_path, "w") as f:
            f.write(DUPLICATE_XML)

        gfm_extract([xml_path, yaml_path])

        yaml = ruamel.yaml.YAML()
        with open(yaml_path) as f:
            data = yaml.load(f)

        filters = data["filters"]

        # First entry should be the named action set
        named = [f for f in filters if "name" in f]
        assert len(named) == 1
        assert named[0]["shouldTrash"] == "true"
        assert named[0]["label"] == "junk"

        # Two filters should reference it
        refs = [f for f in filters if "action" in f]
        assert len(refs) == 2
        assert all(r["action"] == named[0]["name"] for r in refs)
        assert refs[0]["from"] == "a@example.com"
        assert refs[1]["from"] == "b@example.com"

        # One filter should have inline actions
        inline = [
            f for f in filters if "name" not in f and "action" not in f
        ]
        assert len(inline) == 1
        assert inline[0]["from"] == "c@example.com"
        assert inline[0]["shouldStar"] == "true"
    finally:
        os.unlink(xml_path)
        os.unlink(yaml_path)


def test_gfm_extract_no_duplicates():
    """No duplicates means no named entries are created."""
    xml_content = """\
<?xml version='1.0' encoding='UTF-8'?>
<feed xmlns='http://www.w3.org/2005/Atom'
      xmlns:apps='http://schemas.google.com/apps/2006'>
  <entry>
    <apps:property name='from' value='a@example.com'/>
    <apps:property name='shouldTrash' value='true'/>
  </entry>
  <entry>
    <apps:property name='from' value='b@example.com'/>
    <apps:property name='shouldStar' value='true'/>
  </entry>
</feed>
"""
    fd_xml, xml_path = tempfile.mkstemp(suffix=".xml")
    os.close(fd_xml)
    fd_yaml, yaml_path = tempfile.mkstemp(suffix=".yaml")
    os.close(fd_yaml)
    try:
        with open(xml_path, "w") as f:
            f.write(xml_content)

        gfm_extract([xml_path, yaml_path])

        yaml = ruamel.yaml.YAML()
        with open(yaml_path) as f:
            data = yaml.load(f)

        filters = data["filters"]
        assert all("name" not in f for f in filters)
        assert all("action" not in f for f in filters)
        assert len(filters) == 2
    finally:
        os.unlink(xml_path)
        os.unlink(yaml_path)


# --- Round-trip test ---


def test_round_trip():
    """XML -> YAML (with dedup) -> XML preserves all filter data."""
    fd_xml, xml_path = tempfile.mkstemp(suffix=".xml")
    os.close(fd_xml)
    fd_yaml, yaml_path = tempfile.mkstemp(suffix=".yaml")
    os.close(fd_yaml)
    fd_xml2, xml_path2 = tempfile.mkstemp(suffix=".xml")
    os.close(fd_xml2)
    try:
        with open(xml_path, "w") as f:
            f.write(DUPLICATE_XML)

        # XML -> YAML
        gfm_extract([xml_path, yaml_path])

        # YAML -> XML
        gfm_make([yaml_path, xml_path2])

        xml_output = _read_xml(xml_path2)

        # Should have 3 entries (named action expanded back)
        assert xml_output.count("<entry>") == 3

        # All original data should be present
        assert 'value="a@example.com"' in xml_output
        assert 'value="b@example.com"' in xml_output
        assert 'value="c@example.com"' in xml_output
        assert xml_output.count('name="shouldTrash" value="true"') == 2
        assert xml_output.count('name="label" value="junk"') == 2
        assert xml_output.count('name="shouldStar" value="true"') == 1

        # No named action metadata in XML
        assert 'name="action"' not in xml_output
        assert 'name="name"' not in xml_output
    finally:
        os.unlink(xml_path)
        os.unlink(yaml_path)
        os.unlink(xml_path2)
