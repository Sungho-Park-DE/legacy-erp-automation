"""Policy values and adapter choices, in one place (docs/concepts/volatile.md)."""
import os
from datetime import timedelta

SIGHTING_NEEDED = 2
SIGHTING_QUIET = timedelta(seconds=60)

CALL_BEFORE = timedelta(seconds=10)
CALL_AFTER = timedelta(minutes=10)

RELOGIN_MAX = 1

RESTART_MAX_IN_A_ROW = 3
RESTART_MAX_PER_HOUR = 4

ERP = os.environ.get("LEA_ERP", "fake")
CATALOG = os.environ.get("LEA_CATALOG", "fake")
PHONE = os.environ.get("LEA_PHONE", "fake")
SCREEN = os.environ.get("LEA_SCREEN", "fake")

EDIT_UPDATE_REQUEST = "update"
EDIT_DANGEROUS_REQUESTS = frozenset({"delete", "finalize", "print", "save"})
