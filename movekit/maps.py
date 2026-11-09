"""Values picked by map name prefix (bhop_, surf_), shared by the tools that change with the map."""


def prefix_value(name, table, default=None):
    """table[prefix] for the first prefix map `name` starts with (any case), else `default`.
    None for a name that isn't known (CS:S's "Connected to" line)."""
    if name is None:
        return None
    for prefix, value in table.items():
        if name.lower().startswith(prefix.lower()):
            return value
    return default
