"""Resolving the signed in user's personal number (R3).

The Windows logon name has the form `iaf\\<personal number>`. State lives under
%APPDATA%, which is already per user, so a second user signing in on the same
machine gets his own first run rather than inheriting the first user's setup.
"""
import logging
import os
import re

log = logging.getLogger(__name__)

LOGON_PATTERN = re.compile(r"^\s*(?:iaf[\\/])?(\d{3,})\s*$", re.IGNORECASE)


def logon_name() -> str:
    domain = os.environ.get("USERDOMAIN", "")
    user = os.environ.get("USERNAME") or os.environ.get("USER") or ""
    return f"{domain}\\{user}" if domain else user


def personal_number_from_logon():
    """The number from `iaf\\<number>`, or None when the name is another shape."""
    match = LOGON_PATTERN.match(logon_name())
    if match:
        return match.group(1)
    log.info("logon name %r is not in the iaf\\<personal number> form", logon_name())
    return None


def resolve(state):
    """The personal number to use, preferring the logon name over the typed one.

    The spec notes the number is collected twice. The logon name wins because it
    cannot be mistyped; the typed value is kept so a mismatch stays visible in
    the admin window.
    """
    from_logon = personal_number_from_logon()
    typed = state.data.get("personal_number_typed", "")
    if from_logon:
        if typed and typed != from_logon:
            log.warning("typed personal number %s differs from logon %s", typed, from_logon)
        return from_logon
    return typed
