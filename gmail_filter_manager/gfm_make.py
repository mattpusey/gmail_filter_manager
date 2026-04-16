#!/usr/bin/env python

from __future__ import print_function

import sys
import xml.dom.minidom
import xml.etree.ElementTree as ET

import ruamel.yaml

from .constants import ACTION_PROPERTIES, YAML_TO_XML


def gfm_make(argv=None):
    if argv is None:
        argv = sys.argv[1:]

    yaml_input = argv[0] if len(argv) > 0 else "mailFilters.yaml"
    if yaml_input in ["-h", "--help", "help"]:
        print("Usage: gfm_make [input.yaml [output.xml]]")
        sys.exit(0)
    xml_output = argv[1] if len(argv) > 1 else "filters.xml"

    yaml = ruamel.yaml.YAML()
    with open(yaml_input, "r") as f:
        data = yaml.load(f)

    if "namespaces" in data:
        namespaces = data["namespaces"]
        if "atom" in namespaces:
            namespaces[""] = namespaces["atom"]
            del namespaces["atom"]
    else:
        namespaces = {
            "": "http://www.w3.org/2005/Atom",
            "apps": "http://schemas.google.com/apps/2006",
        }

    for k, v in namespaces.items():
        ET.register_namespace(k, v)

    named_actions = {}
    filters = []
    for f in data["filters"]:
        f = dict(f)
        if "name" in f:
            name = f.pop("name")
            named_actions[name] = f
        else:
            filters.append(f)

    for f in filters:
        if "action" in f:
            action_name = f["action"]
            if action_name not in named_actions:
                raise ValueError(
                    f"Filter references unknown named action:"
                    f" '{action_name}'."
                    f" Available: {list(named_actions.keys())}"
                )
            explicit_actions = {
                k for k in f if k != "action" and k in ACTION_PROPERTIES
            }
            if explicit_actions:
                raise ValueError(
                    f"Filter with action '{action_name}' also has"
                    f" explicit action properties:"
                    f" {sorted(explicit_actions)}."
                    f" A filter must use either 'action' or"
                    f" explicit actions, not both."
                )
            del f["action"]
            f.update(named_actions[action_name])

    root = ET.Element("feed")
    for f in filters:
        if "label" in f:
            labels = (
                f["label"] if isinstance(f["label"], list) else [f["label"]]
            )
            del f["label"]
        else:
            labels = [None]
        for label in labels:
            entry = ET.SubElement(root, "{" + namespaces[""] + "}" + "entry")
            properties = f
            if label is not None:
                properties["label"] = label
            for k, v in properties.items():
                xml_name = YAML_TO_XML.get(k, k)
                ET.SubElement(
                    entry,
                    "{" + namespaces["apps"] + "}property",
                    attrib={"name": xml_name, "value": v},
                )

    my_filter = xml.dom.minidom.parseString(ET.tostring(root)).toprettyxml(
        indent="  ", encoding="utf-8"
    )
    if sys.version_info.major > 2:
        my_filter = my_filter.decode()

    with open(xml_output, "w") as f:
        f.write(my_filter)


if __name__ == "__main__":
    gfm_make()
