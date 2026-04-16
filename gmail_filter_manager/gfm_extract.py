#!/usr/bin/env python

from __future__ import print_function

import sys
import xml.etree.ElementTree as ET
from collections import Counter

import ruamel.yaml
from ruamel.yaml.scalarstring import DoubleQuotedScalarString

from .constants import ACTION_PROPERTIES, XML_TO_YAML, generate_action_set_name


def extract_named_actions(filters):
    """Detect duplicate action sets and factor them into named entries."""
    split_filters = []
    for f in filters:
        criteria = {k: v for k, v in f.items() if k not in ACTION_PROPERTIES}
        actions = {k: v for k, v in f.items() if k in ACTION_PROPERTIES}
        split_filters.append((criteria, actions))

    action_counts = Counter()
    for _, actions in split_filters:
        if actions:
            key = frozenset(actions.items())
            action_counts[key] += 1

    existing_names = set()
    key_to_name = {}
    for action_key, count in action_counts.items():
        if count >= 2 and len(action_key) >= 2:
            actions_dict = dict(action_key)
            name = generate_action_set_name(actions_dict, existing_names)
            existing_names.add(name)
            key_to_name[action_key] = name

    if not key_to_name:
        return filters

    named_entries = []
    for action_key, name in key_to_name.items():
        entry = {"name": DoubleQuotedScalarString(name)}
        for k, v in sorted(dict(action_key).items()):
            entry[k] = v
        named_entries.append(entry)

    new_filters = list(named_entries)
    for criteria, actions in split_filters:
        action_key = frozenset(actions.items())
        if action_key in key_to_name:
            result = dict(criteria)
            result["action"] = DoubleQuotedScalarString(
                key_to_name[action_key]
            )
            new_filters.append(result)
        else:
            new_filters.append({**criteria, **actions})

    return new_filters


def gfm_extract(argv=None):
    if argv is None:
        argv = sys.argv[1:]

    xml_input = argv[0] if len(argv) > 0 else "mailFilters.xml"
    if xml_input in ["-h", "--help", "help"]:
        print("Usage: gfm_extract [input.xml [output.yaml]]")
        sys.exit(0)
    yaml_output = argv[1] if len(argv) > 1 else "mailFilters.yaml"

    namespaces = {
        str(x[0]) if x[0] != "" else "atom": x[1]
        for _, x in ET.iterparse(xml_input, events=["start-ns"])
    }

    tree = ET.parse(xml_input)
    root = tree.getroot()

    filters = []
    for e in root.findall("./atom:entry", namespaces):
        properties = {}
        for p in e.findall("./apps:property", namespaces):
            name = XML_TO_YAML.get(p.get("name"), p.get("name"))
            value = p.get("value")
            properties[name] = DoubleQuotedScalarString(value)
        if "size" not in properties:
            for noneed in ["sizeOperator", "sizeUnit"]:
                if noneed in properties:
                    del properties[noneed]
        filters.append(properties)

    filters = extract_named_actions(filters)

    data = {"namespaces": namespaces, "filters": filters}

    yaml = ruamel.yaml.YAML()
    yaml.indent(mapping=2, sequence=4, offset=2)
    with open(yaml_output, "w") as stream:
        yaml.dump(data, stream=stream)


if __name__ == "__main__":
    gfm_extract()
