import argparse
import os
import sys

from backlog import errors
from backlog import mutate
from backlog import query
from backlog.document_io import read_document, write_document
from backlog.validate import validate_document

DEFAULT_FILE = os.path.join(".", "backlog.json")

# Nullable string fields shared by add and update. "none" on the command line
# is stored as JSON null.
OPTIONAL_STRING_FIELDS = ["summary", "where", "doc", "note", "parent"]


def build_parser():
    parser = argparse.ArgumentParser(
        prog="backlog",
        description="backlog.json을 작업 SSOT로 다루는 CLI",
    )
    parser.add_argument(
        "--file",
        default=DEFAULT_FILE,
        metavar="PATH",
        help="backlog 파일 경로 (기본 ./backlog.json)",
    )

    subparsers = parser.add_subparsers(dest="command", metavar="COMMAND")
    subparsers.required = True

    subparsers.add_parser("validate", help="문서 전체를 검증한다")

    list_parser = subparsers.add_parser("list", help="작업 목록을 조회한다")
    list_parser.add_argument("--status")
    list_parser.add_argument("--priority")
    list_parser.add_argument("--category")
    list_parser.add_argument("--format", choices=["table", "json"], default="table")

    show_parser = subparsers.add_parser("show", help="한 작업의 전체 필드를 조회한다")
    show_parser.add_argument("id")
    show_parser.add_argument("--format", choices=["text", "json"], default="text")

    add_parser = subparsers.add_parser("add", help="작업을 추가한다")
    add_parser.add_argument("--title", required=True)
    add_parser.add_argument("--category", required=True)
    add_parser.add_argument("--status")
    add_parser.add_argument("--priority")
    add_parser.add_argument("--deps")
    add_parser.add_argument("--prefix")
    for field in OPTIONAL_STRING_FIELDS:
        add_parser.add_argument("--" + field)

    update_parser = subparsers.add_parser("update", help="기존 작업을 수정한다")
    update_parser.add_argument("id")
    update_parser.add_argument("--title")
    update_parser.add_argument("--category")
    update_parser.add_argument("--status")
    update_parser.add_argument("--priority")
    update_parser.add_argument("--deps")
    for field in OPTIONAL_STRING_FIELDS:
        update_parser.add_argument("--" + field)

    return parser


def _load_document(path):
    """Read and parse a document, translating errors to (doc, exit_code).

    Returns (doc, None) on success, or (None, exit_code) after printing the
    error to stderr.
    """
    try:
        return read_document(path), None
    except errors.FileReadError as err:
        sys.stderr.write("Error: " + str(err) + "\n")
        return None, errors.IO
    except errors.DocumentParseError as err:
        sys.stderr.write("Error: " + str(err) + "\n")
        return None, errors.DATA


def cmd_validate(args):
    doc, exit_code = _load_document(args.file)
    if exit_code is not None:
        return exit_code

    result = validate_document(doc)
    if result["valid"]:
        sys.stdout.write("VALID " + str(result["task_count"]) + " task(s)\n")
        return errors.OK

    sys.stderr.write("INVALID: " + str(len(result["errors"]))
                     + " problem(s) found in '" + args.file + "'\n")
    for error in result["errors"]:
        sys.stderr.write("  - " + error["path"] + ": " + error["message"]
                         + " [" + error["code"] + "]\n")
    return errors.DATA


def _has_task_array(doc):
    return isinstance(doc, dict) and isinstance(doc.get("tasks"), list)


def _load_for_query(path):
    """Load a document for a read-only query command.

    list/show tolerate referential-integrity problems and render best-effort,
    but a root that is not an object with a tasks array has nothing to show.
    """
    doc, exit_code = _load_document(path)
    if exit_code is not None:
        return None, exit_code
    if not _has_task_array(doc):
        sys.stderr.write("Error: '" + path + "' is not a valid backlog document "
                         "(root must be an object with a tasks array)\n")
        return None, errors.DATA
    return doc, None


def cmd_list(args):
    doc, exit_code = _load_for_query(args.file)
    if exit_code is not None:
        return exit_code

    filter_errors = query.validate_filters(
        doc.get("enums"),
        status=args.status,
        priority=args.priority,
        category=args.category,
    )
    if filter_errors:
        sys.stderr.write("Error: " + "; ".join(filter_errors) + "\n")
        return errors.DATA

    tasks = query.filter_and_sort_tasks(
        doc["tasks"],
        status=args.status,
        priority=args.priority,
        category=args.category,
    )
    if args.format == "json":
        sys.stdout.write(query.render_tasks_json(tasks))
    else:
        sys.stdout.write(query.render_table(tasks))
    return errors.OK


def cmd_show(args):
    doc, exit_code = _load_for_query(args.file)
    if exit_code is not None:
        return exit_code

    task = query.find_task_by_id(doc["tasks"], args.id)
    if task is None:
        sys.stderr.write('Error: no task with id "' + args.id + '"\n')
        return errors.DATA

    if args.format == "json":
        sys.stdout.write(query.render_task_json(task))
    else:
        sys.stdout.write(query.render_task_text(task))
    return errors.OK


def _print_validation_errors(headline, result):
    sys.stderr.write(headline + "\n")
    for error in result["errors"]:
        sys.stderr.write("  - " + error["path"] + ": " + error["message"]
                         + " [" + error["code"] + "]\n")


def _load_and_prevalidate(path, verb):
    """Read, parse and fully validate a document before a write command.

    Returns (doc, None) or (None, exit_code) after reporting to stderr.
    """
    doc, exit_code = _load_document(path)
    if exit_code is not None:
        return None, exit_code
    result = validate_document(doc)
    if not result["valid"]:
        _print_validation_errors(
            "Error: cannot " + verb + " -- '" + path + "' is already invalid ("
            + str(len(result["errors"])) + " problem(s)):", result)
        return None, errors.DATA
    return doc, None


def _postvalidate_and_write(path, verb, next_doc):
    result = validate_document(next_doc)
    if not result["valid"]:
        _print_validation_errors(
            "Error: " + verb + " would make '" + path + "' invalid ("
            + str(len(result["errors"])) + " problem(s)):", result)
        return errors.DATA
    try:
        write_document(path, next_doc)
    except errors.FileWriteError as err:
        sys.stderr.write("Error: " + str(err) + "\n")
        return errors.IO
    return errors.OK


def cmd_add(args):
    options = vars(args)
    try:
        fields = mutate.compute_create_fields(options)
    except mutate.MissingRequiredFieldsError as err:
        sys.stderr.write("Error: " + str(err) + "\n")
        return errors.ARGS

    doc, exit_code = _load_and_prevalidate(args.file, "add")
    if exit_code is not None:
        return exit_code

    try:
        prefix = mutate.detect_prefix(doc["tasks"], args.prefix)
    except mutate.PrefixError as err:
        sys.stderr.write("Error: " + str(err) + "\n")
        return errors.ARGS

    next_doc, new_id = mutate.build_task(doc, fields, prefix, mutate.today_string())

    exit_code = _postvalidate_and_write(args.file, "add", next_doc)
    if exit_code == errors.OK:
        sys.stdout.write(new_id + "\n")
    return exit_code


def cmd_update(args):
    options = vars(args)
    try:
        updates = mutate.compute_field_updates(options)
    except mutate.NoUpdateOptionsError as err:
        sys.stderr.write("Error: " + str(err) + "\n")
        return errors.ARGS

    doc, exit_code = _load_and_prevalidate(args.file, "update")
    if exit_code is not None:
        return exit_code

    try:
        next_doc = mutate.apply_update(doc, args.id, updates, mutate.today_string())
    except mutate.TaskNotFoundError as err:
        sys.stderr.write("Error: " + str(err) + "\n")
        return errors.DATA

    exit_code = _postvalidate_and_write(args.file, "update", next_doc)
    if exit_code == errors.OK:
        sys.stdout.write("Updated " + args.id + "\n")
    return exit_code


HANDLERS = {
    "validate": cmd_validate,
    "list": cmd_list,
    "show": cmd_show,
    "add": cmd_add,
    "update": cmd_update,
}


def main(argv=None):
    if argv is None:
        argv = sys.argv[1:]
    parser = build_parser()
    args = parser.parse_args(argv)
    handler = HANDLERS[args.command]
    return handler(args)
