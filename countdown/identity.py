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


def resolve(users, personal_number=None):
    """Find the signed in person in the directory.

    Returns (user, reason). `user` is None when nobody matches, and `reason`
    says why, for the log and the maintenance window.
    """
    from . import users as users_module

    number = personal_number or personal_number_from_logon()
    if not number:
        return None, (f"the logon name {logon_name()!r} is not of the form "
                      "iaf\\<personal number>, so there is no number to look up")
    user = users_module.find(users, number)
    if user is None:
        return None, f"personal number {number} is not in the user list"
    if not user.department:
        return None, f"personal number {number} has no department in the user list"
    return user, ""
