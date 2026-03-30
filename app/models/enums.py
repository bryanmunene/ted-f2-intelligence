from __future__ import annotations

from enum import Enum


class FitLabel(str, Enum):
    YES = "YES"
    CONDITIONAL = "CONDITIONAL"
    NO = "NO"


class PriorityBucket(str, Enum):
    HIGH = "HIGH"
    GOOD = "GOOD"
    WATCHLIST = "WATCHLIST"
    IGNORE = "IGNORE"


class ConfidenceIndicator(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class ScanStatus(str, Enum):
    STARTED = "STARTED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class AuditEventType(str, Enum):
    SCAN_STARTED = "SCAN_STARTED"
    SCAN_COMPLETED = "SCAN_COMPLETED"
    SCAN_FAILED = "SCAN_FAILED"
    NOTICE_SAVED = "NOTICE_SAVED"
    NOTICE_DISMISSED = "NOTICE_DISMISSED"
    NOTE_CREATED = "NOTE_CREATED"
    NOTICE_RESCORED = "NOTICE_RESCORED"

