import json
import re
import unicodedata

ID_SPLIT_RE = re.compile(r"^([A-Z]{2,})-(\d{3,})$", re.ASCII)

TASK_FIELD_ORDER = [
    "id", "status", "priority", "category", "title",
    "summary", "where", "parent", "deps", "doc", "done_at", "note",
]

TABLE_HEADERS = ["ID", "STATUS", "PRIORITY", "CATEGORY", "TITLE"]


def _sort_key(task):
    task_id = task.get("id") if isinstance(task, dict) else None
    match = ID_SPLIT_RE.match(task_id) if isinstance(task_id, str) else None
    if match is None:
        # Malformed ids sort after every well-formed one.
        return (1, "", (0, ""))
    # Order by numeric value without int() (which has a digit-string limit):
    # normalize leading zeros, then compare by (length, digits) which is the
    # numeric order for non-negative integers.
    digits = match.group(2).lstrip("0") or "0"
    return (0, match.group(1), (len(digits), digits))


def filter_and_sort_tasks(tasks, status=None, priority=None, category=None):
    """AND-combine the given filters (None = no-op) and sort by (prefix, number).

    priority "none" matches tasks whose priority is null.
    """
    result = []
    for task in tasks:
        if not isinstance(task, dict):
            # list is best-effort on invalid documents; a non-object task
            # entry matches no filter and is dropped rather than crashing.
            continue
        if status is not None and task.get("status") != status:
            continue
        if category is not None and task.get("category") != category:
            continue
        if priority is not None:
            if priority == "none":
                # A missing priority is not JSON null.
                if not ("priority" in task and task["priority"] is None):
                    continue
            elif task.get("priority") != priority:
                continue
        result.append(task)
    result.sort(key=_sort_key)
    return result


def validate_filters(enums, status=None, priority=None, category=None):
    """Check filter values against the document's own enums (best-effort).

    Missing or malformed enum arrays are skipped, not rejected. Returns a
    list of human-readable error messages (empty when all filters are valid).
    """
    errors = []
    enums = enums if isinstance(enums, dict) else {}
    for field, value in [("status", status), ("category", category)]:
        if value is None:
            continue
        allowed = enums.get(field)
        if isinstance(allowed, list) and value not in allowed:
            errors.append("--" + field + " " + repr(value) + " is not in enums." + field)
    if priority is not None and priority != "none":
        allowed = enums.get("priority")
        if isinstance(allowed, list) and priority not in allowed:
            errors.append("--priority " + repr(priority) + " is not in enums.priority")
    return errors


def _display_width(text):
    # Wide/fullwidth code points occupy two terminal cells.
    width = 0
    for char in text:
        if unicodedata.combining(char) or unicodedata.category(char) in ("Mn", "Me", "Cf"):
            continue
        width += 2 if unicodedata.east_asian_width(char) in ("W", "F") else 1
    return width


def _pad(text, width):
    return text + " " * max(0, width - _display_width(text))


def _one_line(text):
    # Control characters (tab, newline, ...) would break the fixed-width
    # table's row/column structure; collapse each to a single space.
    return "".join(" " if unicodedata.category(char) == "Cc" else char for char in text)


def _table_cells(task):
    priority = task.get("priority")
    priority = "(none)" if priority is None else str(priority)
    return [
        _one_line(str(task.get("id", ""))),
        _one_line(str(task.get("status", ""))),
        _one_line(priority),
        _one_line(str(task.get("category", ""))),
        _one_line(str(task.get("title", ""))),
    ]


def render_table(tasks):
    """Fixed-width space-aligned table. The last column (TITLE) is not truncated.

    An empty task list prints the header row only.
    """
    rows = [_table_cells(task) for task in tasks]
    widths = []
    for i, header in enumerate(TABLE_HEADERS):
        widths.append(max([_display_width(header)] + [_display_width(row[i]) for row in rows]))

    def pad_row(cells):
        parts = []
        for i, cell in enumerate(cells):
            if i == len(cells) - 1:
                parts.append(cell)
            else:
                parts.append(_pad(cell, widths[i]))
        return "  ".join(parts)

    lines = [pad_row(TABLE_HEADERS)] + [pad_row(row) for row in rows]
    return "\n".join(lines) + "\n"


def render_tasks_json(tasks):
    ordered = [_ordered_task(task) if isinstance(task, dict) else task for task in tasks]
    return json.dumps(ordered, ensure_ascii=False, indent=2) + "\n"


def find_task_by_id(tasks, task_id):
    for task in tasks:
        if isinstance(task, dict) and task.get("id") == task_id:
            return task
    return None


def _format_value(field, value):
    if field == "deps":
        if isinstance(value, list) and value:
            return ", ".join(str(entry) for entry in value)
        return "(none)"
    return "(none)" if value is None else str(value)


def render_task_text(task):
    lines = [field + ": " + _format_value(field, task.get(field)) for field in TASK_FIELD_ORDER]
    return "\n".join(lines) + "\n"


def _ordered_task(task):
    ordered = {field: task[field] for field in TASK_FIELD_ORDER if field in task}
    # Preserve any extra keys a best-effort (unvalidated) task may carry.
    for key, value in task.items():
        if key not in ordered:
            ordered[key] = value
    return ordered


def render_task_json(task):
    return json.dumps(_ordered_task(task), ensure_ascii=False, indent=2) + "\n"
