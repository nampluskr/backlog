# Exit codes (SPEC §7). Mirrors the reference EXIT_CODES map.
OK = 0
DATA = 1
ARGS = 2
IO = 3


class BacklogError(Exception):
    """Base for backlog-specific failures."""


class FileReadError(BacklogError):
    """The backlog file could not be read (missing, permission, decode)."""


class DocumentParseError(BacklogError):
    """The backlog file was read but is not valid JSON."""


class FileWriteError(BacklogError):
    """The backlog file could not be written atomically."""
