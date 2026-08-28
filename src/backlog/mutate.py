import copy
import datetime
import re

UPDATABLE_FIELDS = [
    "status", "priority", "category", "title",
    "summary", "where", "parent", "deps", "doc", "note",
]

NULLABLE_FIELDS = ["priority", "summary", "where", "doc", "note", "parent"]

REQUIRED_CREATE_FIELDS = ["title", "category"]

_ID_PREFIX_RE = re.compile(r"^([A-Z]{2,})-\d{3,}$", re.ASCII)


class MutateError(Exception):
    """Base for add/update input problems (maps to exit code ARGS or DATA)."""


class NoUpdateOptionsError(MutateError):
    pass


class MissingRequiredFieldsError(MutateError):
    def __init__(self, missing):
        super().__init__(
            "add requires " + " and ".join("--" + field for field in missing))
        self.missing = missing


class TaskNotFoundError(MutateError):
    def __init__(self, task_id):
        super().__init__('no task with id "' + task_id + '"')
        self.task_id = task_id


class PrefixError(MutateError):
    pass


def today_string():
    return datetime.date.today().isoformat()


def parse_deps_value(raw):
    trimmed = raw.strip()
    if trimmed == "" or trimmed == "none":
        return []
    return [entry.strip() for entry in trimmed.split(",") if entry.strip()]


def _collect_fields(raw_options):
    """Map supplied CLI options to task fields (none->null, deps comma-split)."""
    fields = {}
    for field in UPDATABLE_FIELDS:
        raw = raw_options.get(field)
        if raw is None:
            continue
        if field == "deps":
            fields["deps"] = parse_deps_value(raw)
        elif field in NULLABLE_FIELDS and raw == "none":
            fields[field] = None
        else:
            fields[field] = raw
    return fields


def compute_create_fields(raw_options):
    missing = [field for field in REQUIRED_CREATE_FIELDS if raw_options.get(field) is None]
    if missing:
        raise MissingRequiredFieldsError(missing)
    return _collect_fields(raw_options)


def compute_field_updates(raw_options):
    updates = _collect_fields(raw_options)
    if not updates:
        raise NoUpdateOptionsError(
            "update requires at least one field to change ("
            + ", ".join(UPDATABLE_FIELDS) + ")")
    return updates


def detect_prefix(tasks, explicit_prefix):
    """Return the id prefix to use for a new task.

    An empty backlog needs an explicit --prefix. A non-empty backlog (which
    has already passed validation, so every id shares one prefix) uses that
    prefix; an explicit --prefix that disagrees is an error.
    """
    existing = None
    for task in tasks:
        if not isinstance(task, dict):
            continue
        match = _ID_PREFIX_RE.match(task.get("id")) if isinstance(task.get("id"), str) else None
        if match is not None:
            existing = match.group(1)
            break

    if existing is None:
        if not explicit_prefix:
            raise PrefixError("backlog is empty; --prefix is required for the first task")
        if not re.fullmatch(r"[A-Z]{2,}", explicit_prefix):
            raise PrefixError("--prefix must match [A-Z]{2,}, got " + repr(explicit_prefix))
        return explicit_prefix

    if explicit_prefix and explicit_prefix != existing:
        raise PrefixError(
            "--prefix " + repr(explicit_prefix) + " does not match the existing prefix "
            + repr(existing))
    return existing


def _normalize_digits(digits):
    return digits.lstrip("0") or "0"


def _decimal_key(digits):
    normalized = _normalize_digits(digits)
    return (len(normalized), normalized)


def _increment_decimal(digits):
    chars = list(_normalize_digits(digits))
    i = len(chars) - 1
    while i >= 0:
        if chars[i] == "9":
            chars[i] = "0"
            i -= 1
        else:
            chars[i] = str(int(chars[i]) + 1)
            return "".join(chars)
    return "1" + "".join(chars)


def compute_next_id(tasks, prefix):
    # Work on decimal strings, never int(), so an arbitrarily long numeric
    # suffix cannot hit Python's integer-string conversion limit.
    number_re = re.compile(r"^" + re.escape(prefix) + r"-(\d+)$", re.ASCII)
    highest = "0"
    for task in tasks:
        if not isinstance(task, dict):
            continue
        task_id = task.get("id")
        match = number_re.match(task_id) if isinstance(task_id, str) else None
        if match is None:
            continue
        if _decimal_key(match.group(1)) > _decimal_key(highest):
            highest = match.group(1)
    return prefix + "-" + _increment_decimal(highest).zfill(3)


def build_task(doc, fields, prefix, today):
    """Return (new_doc, new_id). doc is not mutated.

    The caller must re-validate the returned document — enum and referential
    integrity are not checked here.
    """
    new_id = compute_next_id(doc["tasks"], prefix)
    result = copy.deepcopy(doc)

    status = fields.get("status", "todo")
    task = {
        "id": new_id,
        "status": status,
        "priority": fields.get("priority", None),
        "category": fields["category"],
        "title": fields["title"],
        "summary": fields.get("summary", None),
        "where": fields.get("where", None),
        "doc": fields.get("doc", None),
        "note": fields.get("note", None),
        "parent": fields.get("parent", None),
        "deps": fields["deps"] if "deps" in fields else [],
        "done_at": today if status == "done" else None,
    }

    result["tasks"].append(task)
    result["meta"]["updated"] = today
    return result, new_id


def apply_update(doc, task_id, field_updates, today):
    """Return a new document with task_id updated. doc is not mutated."""
    index = None
    for i, task in enumerate(doc["tasks"]):
        if isinstance(task, dict) and task.get("id") == task_id:
            index = i
            break
    if index is None:
        raise TaskNotFoundError(task_id)

    result = copy.deepcopy(doc)
    task = result["tasks"][index]
    task.update(field_updates)

    if "status" in field_updates:
        if task.get("status") == "done":
            if task.get("done_at") is None:
                task["done_at"] = today
        else:
            task["done_at"] = None

    result["meta"]["updated"] = today
    return result
