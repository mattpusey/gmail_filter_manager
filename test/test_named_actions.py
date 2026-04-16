import os
import tempfile

import pytest
import ruamel.yaml

from gmail_filter_manager.constants import generate_action_set_name
from gmail_filter_manager.gfm_extract import extract_named_actions, gfm_extract
from gmail_filter_manager.gfm_make import gfm_make

# --- Unit tests for extract_named_actions ---


def test_no_duplicates_returns_unchanged():
    filters = [
        {"from": "a@example.com", "trash": "true"},
        {"from": "b@example.com", "star": "true"},
    ]
    result = extract_named_actions(filters)
    assert result == filters


def test_duplicates_are_factored_out():
    filters = [
        {"from": "a@example.com", "trash": "true", "label": "junk"},
        {"from": "b@example.com", "trash": "true", "label": "junk"},
        {"from": "c@example.com", "star": "true"},
    ]
    result = extract_named_actions(filters)

    # First entry should be the named action set
    assert "name" in result[0]
    assert result[0]["trash"] == "true"
    assert result[0]["label"] == "junk"

    # Next two should reference it
    assert result[1]["from"] == "a@example.com"
    assert result[1]["action"] == result[0]["name"]
    assert "trash" not in result[1]
    assert "label" not in result[1]

    assert result[2]["from"] == "b@example.com"
    assert result[2]["action"] == result[0]["name"]

    # Last should be unchanged
    assert result[3]["from"] == "c@example.com"
    assert result[3]["star"] == "true"
    assert "action" not in result[3]


def test_multiple_different_duplicates():
    filters = [
        {"from": "a@example.com", "trash": "true", "notImportant": "true"},
        {"from": "b@example.com", "trash": "true", "notImportant": "true"},
        {"from": "c@example.com", "star": "true", "markRead": "true"},
        {"from": "d@example.com", "star": "true", "markRead": "true"},
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


def test_single_action_duplicates_not_extracted():
    filters = [
        {"from": "a@example.com", "trash": "true"},
        {"from": "b@example.com", "trash": "true"},
    ]
    result = extract_named_actions(filters)
    assert len(result) == 2
    assert all("name" not in f for f in result)
    assert all("action" not in f for f in result)


# --- Unit tests for generate_action_set_name ---


def test_name_generation_two_keys():
    name = generate_action_set_name(
        {"label": "x", "trash": "true"}, set()
    )
    assert name == "x_and_trash"


def test_name_generation_three_keys():
    name = generate_action_set_name(
        {"label": "x", "trash": "true", "star": "true"}, set()
    )
    assert name == "x_plus_2"


def test_name_generation_collision():
    existing = {"x_and_trash"}
    name = generate_action_set_name(
        {"label": "x", "trash": "true"}, existing
    )
    assert name == "x_and_trash_2"


def test_name_generation_single_key():
    name = generate_action_set_name({"trash": "true"}, set())
    assert name == "trash"


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
            {"name": "junk", "label": "junk", "trash": "true"},
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

        # Both entries should have the expanded XML actions
        assert xml_content.count('name="shouldTrash"') == 2
        assert xml_content.count('name="label" value="junk"') == 2

        # Both should have their criteria
        assert 'value="a@example.com"' in xml_content
        assert 'value="b@example.com"' in xml_content

        # action/name metadata should NOT appear as a property
        assert 'name="action"' not in xml_content
        assert 'name="name"' not in xml_content
    finally:
        os.unlink(yaml_path)
        os.unlink(xml_path)


def test_gfm_make_expands_short_names_to_xml():
    """Short YAML names are expanded to long XML names."""
    data = {
        "filters": [
            {
                "from": "a@example.com",
                "archive": "true",
                "markRead": "true",
                "star": "true",
                "trash": "true",
                "notSpam": "true",
                "important": "true",
                "notImportant": "true",
                "smartLabel": "^smartlabel_personal",
            },
        ]
    }
    yaml_path = _make_yaml_file(data)
    fd, xml_path = tempfile.mkstemp(suffix=".xml")
    os.close(fd)
    try:
        gfm_make([yaml_path, xml_path])
        xml_content = _read_xml(xml_path)
        assert 'name="shouldArchive"' in xml_content
        assert 'name="shouldMarkAsRead"' in xml_content
        assert 'name="shouldStar"' in xml_content
        assert 'name="shouldTrash"' in xml_content
        assert 'name="shouldNeverSpam"' in xml_content
        assert 'name="shouldAlwaysMarkAsImportant"' in xml_content
        assert 'name="shouldNeverMarkAsImportant"' in xml_content
        assert 'name="smartLabelToApply"' in xml_content
    finally:
        os.unlink(yaml_path)
        os.unlink(xml_path)


def test_gfm_make_backward_compat():
    """YAML with old long names still produces correct XML."""
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
            {"name": "junk", "trash": "true"},
            {
                "from": "a@example.com",
                "action": "junk",
                "star": "true",
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

        # First entry should be the named action set with short names
        named = [f for f in filters if "name" in f]
        assert len(named) == 1
        assert named[0]["trash"] == "true"
        assert named[0]["label"] == "junk"
        assert "shouldTrash" not in named[0]

        # Two filters should reference it
        refs = [f for f in filters if "action" in f]
        assert len(refs) == 2
        assert all(r["action"] == named[0]["name"] for r in refs)
        assert refs[0]["from"] == "a@example.com"
        assert refs[1]["from"] == "b@example.com"

        # One filter should have inline short-named actions
        inline = [
            f for f in filters if "name" not in f and "action" not in f
        ]
        assert len(inline) == 1
        assert inline[0]["from"] == "c@example.com"
        assert inline[0]["star"] == "true"
        assert "shouldStar" not in inline[0]
    finally:
        os.unlink(xml_path)
        os.unlink(yaml_path)


def test_gfm_extract_condenses_names():
    """XML long names are condensed to short YAML names."""
    xml_content = """\
<?xml version='1.0' encoding='UTF-8'?>
<feed xmlns='http://www.w3.org/2005/Atom'
      xmlns:apps='http://schemas.google.com/apps/2006'>
  <entry>
    <apps:property name='from' value='a@example.com'/>
    <apps:property name='shouldArchive' value='true'/>
    <apps:property name='shouldMarkAsRead' value='true'/>
    <apps:property name='shouldStar' value='true'/>
    <apps:property name='shouldTrash' value='true'/>
    <apps:property name='shouldNeverSpam' value='true'/>
    <apps:property name='shouldAlwaysMarkAsImportant' value='true'/>
    <apps:property name='shouldNeverMarkAsImportant' value='true'/>
    <apps:property name='smartLabelToApply' value='^smartlabel_personal'/>
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

        f = data["filters"][0]
        assert f["archive"] == "true"
        assert f["markRead"] == "true"
        assert f["star"] == "true"
        assert f["trash"] == "true"
        assert f["notSpam"] == "true"
        assert f["important"] == "true"
        assert f["notImportant"] == "true"
        assert f["smartLabel"] == "^smartlabel_personal"
        # Long names should not be present
        assert "shouldArchive" not in f
        assert "shouldTrash" not in f
        assert "smartLabelToApply" not in f
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

        # All original data should be present with long XML names
        assert 'value="a@example.com"' in xml_output
        assert 'value="b@example.com"' in xml_output
        assert 'value="c@example.com"' in xml_output
        assert xml_output.count('name="shouldTrash" value="true"') == 2
        assert xml_output.count('name="label" value="junk"') == 2
        assert xml_output.count('name="shouldStar" value="true"') == 1

        # No named action metadata or short names in XML
        assert 'name="action"' not in xml_output
        assert 'name="name"' not in xml_output
        assert 'name="trash"' not in xml_output
        assert 'name="star"' not in xml_output
    finally:
        os.unlink(xml_path)
        os.unlink(yaml_path)
        os.unlink(xml_path2)
