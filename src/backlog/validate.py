import datetime
import re

# re.ASCII so \d matches only ASCII 0-9, not Unicode decimal digits — the
# reference JavaScript regex is ASCII-only.
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$", re.ASCII)
ID_RE = re.compile(r"^[A-Z]{2,}-\d{3,}$", re.ASCII)

# Error codes mirror the reference validate.mjs, plus ID_PREFIX_MIXED (D-2).
ROOT_NOT_OBJECT = "ROOT_NOT_OBJECT"
SCHEMA_VERSION_INVALID = "SCHEMA_VERSION_INVALID"
REQUIRED_FIELD_MISSING = "REQUIRED_FIELD_MISSING"
TYPE_MISMATCH = "TYPE_MISMATCH"
DATE_FORMAT_INVALID = "DATE_FORMAT_INVALID"
ENUM_INVALID = "ENUM_INVALID"
ID_FORMAT_INVALID = "ID_FORMAT_INVALID"
DUPLICATE_ID = "DUPLICATE_ID"
TITLE_EMPTY = "TITLE_EMPTY"
REF_MISSING = "REF_MISSING"
SELF_REFERENCE = "SELF_REFERENCE"
DUPLICATE_DEPS_ENTRY = "DUPLICATE_DEPS_ENTRY"
DONE_AT_MISMATCH = "DONE_AT_MISMATCH"
ID_PREFIX_MIXED = "ID_PREFIX_MIXED"

REQUIRED_TASK_FIELDS = [
    "id", "status", "priority", "category", "title",
    "summary", "where", "doc", "note", "parent", "deps", "done_at",
]


def _is_object(value):
    return isinstance(value, dict)


def _is_string_or_null(value):
    return value is None or isinstance(value, str)


def _is_string(value):
    # json never yields bool for a string position, but guard anyway.
    return isinstance(value, str)


def _is_valid_date_string(value):
    if not isinstance(value, str) or not DATE_RE.match(value):
        return False
    try:
        datetime.date.fromisoformat(value)
    except ValueError:
        return False
    return True


def validate_document(doc):
    """Return {"valid": bool, "errors": [{code, path, message}], "task_count": int}."""
    errors = []

    def push(code, path, message):
        errors.append({"code": code, "path": path, "message": message})

    if not _is_object(doc):
        push(ROOT_NOT_OBJECT, "$", "document root must be a JSON object")
        return {"valid": False, "errors": errors, "task_count": 0}

    if "$schema_version" not in doc:
        push(REQUIRED_FIELD_MISSING, "$schema_version", "missing required field $schema_version")
    elif doc["$schema_version"] != "1":
        push(SCHEMA_VERSION_INVALID, "$schema_version",
             'schema_version must be the string "1", got ' + repr(doc["$schema_version"]))

    _validate_meta(doc, push)
    enums_status, enums_priority, enums_category = _validate_enums(doc, push)

    tasks = None
    if "tasks" not in doc:
        push(REQUIRED_FIELD_MISSING, "tasks", "missing required field tasks")
    elif not isinstance(doc["tasks"], list):
        push(TYPE_MISMATCH, "tasks", "tasks must be an array")
    else:
        tasks = doc["tasks"]

    task_count = len(doc["tasks"]) if isinstance(doc.get("tasks"), list) else 0

    if tasks is None:
        return {"valid": len(errors) == 0, "errors": errors, "task_count": task_count}

    id_set = set()          # format-valid ids only; referential-integrity target set
    seen_id_strings = set()  # every string id seen, regardless of format
    prefixes = set()

    _validate_tasks_pass1(
        tasks, push, enums_status, enums_priority, enums_category,
        id_set, seen_id_strings, prefixes,
    )

    if len(prefixes) > 1:
        push(ID_PREFIX_MIXED, "tasks",
             "task ids use more than one prefix: " + ", ".join(sorted(prefixes)))

    _validate_tasks_pass2(tasks, push, id_set)

    return {"valid": len(errors) == 0, "errors": errors, "task_count": task_count}


def _validate_meta(doc, push):
    if "meta" not in doc:
        push(REQUIRED_FIELD_MISSING, "meta", "missing required field meta")
        return
    meta = doc["meta"]
    if not _is_object(meta):
        push(TYPE_MISMATCH, "meta", "meta must be an object")
        return
    if "updated" not in meta:
        push(REQUIRED_FIELD_MISSING, "meta.updated", "missing required field meta.updated")
    elif not _is_valid_date_string(meta["updated"]):
        push(DATE_FORMAT_INVALID, "meta.updated", "meta.updated must be a YYYY-MM-DD date string")
    if "context_doc" not in meta:
        push(REQUIRED_FIELD_MISSING, "meta.context_doc", "missing required field meta.context_doc")
    elif not _is_string_or_null(meta["context_doc"]):
        push(TYPE_MISMATCH, "meta.context_doc", "meta.context_doc must be a string or null")
    if "note" not in meta:
        push(REQUIRED_FIELD_MISSING, "meta.note", "missing required field meta.note")
    elif not _is_string_or_null(meta["note"]):
        push(TYPE_MISMATCH, "meta.note", "meta.note must be a string or null")


def _validate_enums(doc, push):
    if "enums" not in doc:
        push(REQUIRED_FIELD_MISSING, "enums", "missing required field enums")
        return None, None, None
    enums = doc["enums"]
    if not _is_object(enums):
        push(TYPE_MISMATCH, "enums", "enums must be an object")
        return None, None, None
    for key in ["status", "priority", "category"]:
        if key not in enums:
            push(REQUIRED_FIELD_MISSING, "enums." + key, "missing required field enums." + key)
        elif not isinstance(enums[key], list):
            push(TYPE_MISMATCH, "enums." + key, "enums." + key + " must be an array")
    status = enums["status"] if isinstance(enums.get("status"), list) else None
    priority = enums["priority"] if isinstance(enums.get("priority"), list) else None
    category = enums["category"] if isinstance(enums.get("category"), list) else None
    return status, priority, category


def _validate_tasks_pass1(tasks, push, enums_status, enums_priority, enums_category,
                          id_set, seen_id_strings, prefixes):
    for i, task in enumerate(tasks):
        base = "tasks[" + str(i) + "]"

        if not _is_object(task):
            push(TYPE_MISMATCH, base, "task must be an object")
            continue

        for field in REQUIRED_TASK_FIELDS:
            if field not in task:
                push(REQUIRED_FIELD_MISSING, base + "." + field,
                     "missing required field " + base + "." + field)

        if "id" in task:
            if not _is_string(task["id"]):
                push(TYPE_MISMATCH, base + ".id", "id must be a string")
            else:
                task_id = task["id"]
                if task_id in seen_id_strings:
                    push(DUPLICATE_ID, base + ".id", "duplicate id " + repr(task_id))
                seen_id_strings.add(task_id)
                if not ID_RE.match(task_id):
                    push(ID_FORMAT_INVALID, base + ".id",
                         "id must match ^[A-Z]{2,}-\\d{3,}$, got " + repr(task_id))
                else:
                    id_set.add(task_id)
                    prefixes.add(task_id.split("-", 1)[0])

        if "status" in task:
            if not _is_string(task["status"]):
                push(TYPE_MISMATCH, base + ".status", "status must be a string")
            elif enums_status is not None and task["status"] not in enums_status:
                push(ENUM_INVALID, base + ".status",
                     "status " + repr(task["status"]) + " is not in enums.status")

        if "priority" in task:
            if task["priority"] is not None and not _is_string(task["priority"]):
                push(TYPE_MISMATCH, base + ".priority", "priority must be a string or null")
            elif (task["priority"] is not None and enums_priority is not None
                  and task["priority"] not in enums_priority):
                push(ENUM_INVALID, base + ".priority",
                     "priority " + repr(task["priority"]) + " is not in enums.priority")

        if "category" in task:
            if not _is_string(task["category"]):
                push(TYPE_MISMATCH, base + ".category", "category must be a string")
            elif enums_category is not None and task["category"] not in enums_category:
                push(ENUM_INVALID, base + ".category",
                     "category " + repr(task["category"]) + " is not in enums.category")

        if "title" in task:
            if not _is_string(task["title"]):
                push(TYPE_MISMATCH, base + ".title", "title must be a string")
            elif len(task["title"]) == 0:
                push(TITLE_EMPTY, base + ".title", "title must not be empty")

        for field in ["summary", "where", "doc", "note"]:
            if field in task and not _is_string_or_null(task[field]):
                push(TYPE_MISMATCH, base + "." + field, field + " must be a string or null")

        if "parent" in task and not _is_string_or_null(task["parent"]):
            push(TYPE_MISMATCH, base + ".parent", "parent must be a string or null")

        if "deps" in task:
            if not isinstance(task["deps"], list):
                push(TYPE_MISMATCH, base + ".deps", "deps must be an array")
            else:
                for j, entry in enumerate(task["deps"]):
                    if not _is_string(entry):
                        push(TYPE_MISMATCH, base + ".deps[" + str(j) + "]",
                             "deps entries must be strings")

        if "done_at" in task and task["done_at"] is not None \
                and not _is_valid_date_string(task["done_at"]):
            push(DATE_FORMAT_INVALID, base + ".done_at",
                 "done_at must be a YYYY-MM-DD date string or null")

        if "status" in task and "done_at" in task and _is_string(task["status"]):
            is_done = task["status"] == "done"
            has_done_at = task["done_at"] is not None
            if is_done != has_done_at:
                push(DONE_AT_MISMATCH, base + ".done_at",
                     'status is "done" but done_at is null' if is_done
                     else "status is " + repr(task["status"]) + " but done_at is not null")


def _validate_tasks_pass2(tasks, push, id_set):
    for i, task in enumerate(tasks):
        if not _is_object(task):
            continue
        base = "tasks[" + str(i) + "]"
        own_id = task["id"] if _is_string(task.get("id")) else None

        if _is_string(task.get("parent")):
            if own_id is not None and task["parent"] == own_id:
                push(SELF_REFERENCE, base + ".parent", "task cannot reference itself as parent")
            elif task["parent"] not in id_set:
                push(REF_MISSING, base + ".parent",
                     "parent " + repr(task["parent"]) + " does not reference an existing task")

        if isinstance(task.get("deps"), list):
            seen_deps = set()
            for j, entry in enumerate(task["deps"]):
                if not _is_string(entry):
                    continue
                dep_path = base + ".deps[" + str(j) + "]"
                if own_id is not None and entry == own_id:
                    push(SELF_REFERENCE, dep_path, "task cannot reference itself in deps")
                elif entry not in id_set:
                    push(REF_MISSING, dep_path,
                         "deps entry " + repr(entry) + " does not reference an existing task")
                if entry in seen_deps:
                    push(DUPLICATE_DEPS_ENTRY, dep_path, "duplicate deps entry " + repr(entry))
                seen_deps.add(entry)
