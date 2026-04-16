CRITERIA_PROPERTIES = frozenset(
    {
        "from",
        "to",
        "subject",
        "hasTheWord",
        "doesNotHaveTheWord",
        "hasAttachment",
        "excludeChats",
        "size",
        "sizeOperator",
        "sizeUnit",
    }
)

XML_TO_YAML = {
    "shouldArchive": "archive",
    "shouldMarkAsRead": "markRead",
    "shouldStar": "star",
    "shouldTrash": "trash",
    "shouldNeverSpam": "neverSpam",
    "shouldAlwaysMarkAsImportant": "important",
    "shouldNeverMarkAsImportant": "notImportant",
    "smartLabelToApply": "smartLabel",
}

YAML_TO_XML = {v: k for k, v in XML_TO_YAML.items()}

ACTION_PROPERTIES = frozenset(
    {
        "archive",
        "markRead",
        "star",
        "label",
        "forwardTo",
        "trash",
        "neverSpam",
        "important",
        "notImportant",
        "smartLabel",
    }
)


def generate_action_set_name(actions_dict, existing_names):
    """Generate a human-readable name for a set of actions."""
    label_value = actions_dict.get("label")
    other_keys = sorted(k for k in actions_dict if k != "label")

    if label_value is not None:
        parts = [label_value] + other_keys
    else:
        parts = other_keys

    if len(parts) <= 2:
        base = "_and_".join(parts)
    else:
        base = f"{parts[0]}_plus_{len(parts) - 1}"

    name = base
    counter = 2
    while name in existing_names:
        name = f"{base}_{counter}"
        counter += 1

    return name
