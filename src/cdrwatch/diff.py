"""Line-set diff between two extracted snapshots."""

from cdrwatch.models import Change


def _lines(text: str) -> list[str]:
    return [line for line in text.splitlines() if line.strip()]


def compare(source_id: str, old: str | None, new: str) -> Change | None:
    """Return added/removed lines, or None for a baseline or an equal line set."""
    if old is None:
        return None
    old_lines = _lines(old)
    new_lines = _lines(new)
    old_set = set(old_lines)
    new_set = set(new_lines)
    if old_set == new_set:
        return None
    added = tuple(dict.fromkeys(line for line in new_lines if line not in old_set))
    removed = tuple(dict.fromkeys(line for line in old_lines if line not in new_set))
    return Change(source_id=source_id, added=added, removed=removed)
