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

ACTION_PROPERTIES = frozenset(
    {
        "shouldArchive",
        "shouldMarkAsRead",
        "shouldStar",
        "label",
        "forwardTo",
        "shouldTrash",
        "shouldNeverSpam",
        "shouldAlwaysMarkAsImportant",
        "shouldNeverMarkAsImportant",
        "smartLabelToApply",
    }
)


def generate_action_set_name(actions_dict, existing_names):
    """Generate a human-readable name for a set of actions."""
    keys = sorted(actions_dict.keys())

    if len(keys) <= 2:
        base = "_and_".join(keys)
    else:
        base = f"{keys[0]}_plus_{len(keys) - 1}"

    name = base
    counter = 2
    while name in existing_names:
        name = f"{base}_{counter}"
        counter += 1

    return name
