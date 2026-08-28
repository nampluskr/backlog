import json
import os
import uuid

from backlog.errors import DocumentParseError, FileReadError, FileWriteError


def _reject_constant(token):
    raise ValueError("non-standard JSON constant: " + token)


def read_document(path):
    """Read and json.loads a backlog document.

    I/O failures raise FileReadError; JSON syntax failures raise
    DocumentParseError, so callers can map them to different exit codes.
    """
    try:
        with open(path, "r", encoding="utf-8") as handle:
            text = handle.read()
    except OSError as err:
        raise FileReadError("failed to read file: " + path + " (" + str(err) + ")")
    except UnicodeDecodeError as err:
        raise FileReadError("failed to read file: " + path + " (" + str(err) + ")")

    try:
        # parse_constant rejects NaN / Infinity / -Infinity, which json accepts
        # by default but strict JSON (and the reference JSON.parse) does not.
        return json.loads(text, parse_constant=_reject_constant)
    except ValueError as err:
        raise DocumentParseError("failed to parse JSON in " + path + ": " + str(err))


def write_document(path, doc):
    """Serialize doc and atomically replace path.

    Writes to a unique temp file in the same directory, then os.replace over
    the original. On any failure the original file is left byte-for-byte
    untouched and the temp file is cleaned up best-effort.
    """
    directory = os.path.dirname(path) or "."
    base = os.path.basename(path)
    temp_name = "." + base + "." + str(os.getpid()) + "-" + uuid.uuid4().hex + ".tmp"
    temp_path = os.path.join(directory, temp_name)

    try:
        text = json.dumps(doc, ensure_ascii=False, allow_nan=False, indent=2) + "\n"
    except ValueError as err:
        raise FileWriteError("failed to write file: " + path + " (" + str(err) + ")")

    try:
        # "x" refuses to overwrite an existing temp file (unreachable given
        # the uuid, but costs nothing to guard). UnicodeError covers a
        # document holding an unencodable string (e.g. a lone surrogate).
        with open(temp_path, "x", encoding="utf-8") as handle:
            handle.write(text)
    except (OSError, UnicodeError) as err:
        _cleanup(temp_path)
        raise FileWriteError("failed to write file: " + path + " (" + str(err) + ")")

    try:
        os.replace(temp_path, path)
    except OSError as err:
        _cleanup(temp_path)
        raise FileWriteError("failed to write file: " + path + " (" + str(err) + ")")


def _cleanup(temp_path):
    try:
        os.remove(temp_path)
    except OSError:
        pass
