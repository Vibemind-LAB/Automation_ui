"""C4 — Messenger whitelist guard.

Only allow OUTBOUND messages to approved recipients (the user's own number /
contacts), so the autonomous routing system (gap-detector, OpenFang agents, the
brain) can never message arbitrary people. "wenn nur meine nummer erlaubt fuer
messenger".

Flag MESSENGER_WHITELIST_ENABLED (default OFF -> no restriction, current behaviour).
Allowed recipients from env MESSENGER_ALLOWED_RECIPIENTS (comma-separated names
and/or numbers). Matching is normalized:
  - numbers      -> digits only, equal OR one is a >=7-digit suffix of the other
                    (tolerates +49 / 0049 / 0 country-code variations)
  - names/channels-> case-insensitive, trimmed
Fail-safe: any guard error returns ALLOWED (a bug here must never silently drop a
legitimate message); the explicit deny only happens when ENABLED and no match.
"""

from __future__ import annotations

import os
import re
import logging
from typing import List, Tuple

logger = logging.getLogger("messenger.whitelist")

ENABLED = os.environ.get("MESSENGER_WHITELIST_ENABLED", "0") == "1"


def _allowed_raw() -> List[str]:
    raw = os.environ.get("MESSENGER_ALLOWED_RECIPIENTS", "")
    return [x.strip() for x in raw.split(",") if x.strip()]


def _is_number(s: str) -> bool:
    digits = re.sub(r"\D", "", s)
    # treat as a number if it is mostly digits (a phone number, not a name)
    return len(digits) >= 6 and len(digits) >= len(s.replace(" ", "")) - 2


def _norm_number(s: str) -> str:
    return re.sub(r"\D", "", s)


def _norm_name(s: str) -> str:
    return s.strip().lower().lstrip("#@")


def _match(recipient: str, allowed: str) -> bool:
    if _is_number(allowed) and _is_number(recipient):
        a, r = _norm_number(allowed), _norm_number(recipient)
        if not a or not r:
            return False
        if a == r:
            return True
        # compare the last K significant digits so 0170.. (national) and
        # +49170.. (international) of the SAME number match, while different
        # numbers still differ. K=last 9 digits (subscriber part).
        k = min(len(a), len(r), 9)
        return k >= 7 and a[-k:] == r[-k:]
    return _norm_name(recipient) == _norm_name(allowed)


def is_allowed(recipient: str) -> bool:
    """True if this recipient may receive an outbound message."""
    if not ENABLED:
        return True  # guard off -> behave exactly as before
    try:
        allowed = _allowed_raw()
        if not allowed:
            # enabled but nothing whitelisted -> deny all (safe default)
            return False
        rcpt = (recipient or "").strip()
        if not rcpt:
            return False
        return any(_match(rcpt, a) for a in allowed)
    except Exception as exc:  # fail-safe: never silently drop a legit message
        logger.warning("[messenger-whitelist] guard error -> allow: %s", exc)
        return True


def guard(recipient: str) -> Tuple[bool, str]:
    """(allowed, reason). Use at the send path: if not allowed, do NOT send."""
    if is_allowed(recipient):
        return True, "ok"
    return False, (
        f"blocked by messenger whitelist: '{recipient}' is not an approved "
        f"recipient (MESSENGER_ALLOWED_RECIPIENTS). Only the user's own "
        f"number/contacts may be messaged."
    )
