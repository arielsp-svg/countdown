"""Add to calendar (R9).

An .ics file is written and handed to the shell, which opens it in whatever
calendar the machine has set as default (Outlook, in practice). This needs no
Outlook automation, no profile access and no extra dependency.
"""
import logging
import os
import tempfile
import uuid
from datetime import date, timedelta

log = logging.getLogger(__name__)


def _escape(text: str) -> str:
    return (str(text or "")
            .replace("\\", "\\\\").replace(";", "\\;")
            .replace(",", "\\,").replace("\n", "\\n"))


def build(row) -> str:
    start = row.ro_date
    end = start + timedelta(days=1)  # all day event, DTEND is exclusive
    stamp = date.today().strftime("%Y%m%d") + "T000000Z"
    description = "; ".join(
        f"{label}: {value}" for label, value in [
            ("Department", row.department),
            ("Type of system", row.type_of_system),
            ("Platform", row.platform),
            ("Nav system", row.nav_system),
            ("Receiver model", row.receiver_model),
            ("Using TOD", row.using_tod),
            ("Comments", row.comments),
        ] if str(value or "").strip()
    )
    return "\r\n".join([
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Countdown//RO dates//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "BEGIN:VEVENT",
        f"UID:{uuid.uuid4()}@countdown",
        f"DTSTAMP:{stamp}",
        f"DTSTART;VALUE=DATE:{start.strftime('%Y%m%d')}",
        f"DTEND;VALUE=DATE:{end.strftime('%Y%m%d')}",
        f"SUMMARY:RO date - {_escape(row.label)}",
        f"DESCRIPTION:{_escape(description)}",
        "BEGIN:VALARM",
        "TRIGGER:-P7D",
        "ACTION:DISPLAY",
        "DESCRIPTION:RO date in one week",
        "END:VALARM",
        "END:VEVENT",
        "END:VCALENDAR",
        "",
    ])


def open_in_calendar(row) -> bool:
    safe = "".join(c for c in row.label if c.isalnum() or c in " -_")[:40].strip() or "system"
    path = os.path.join(tempfile.gettempdir(), f"RO {safe} {row.ro_date.isoformat()}.ics")
    try:
        with open(path, "w", encoding="utf-8", newline="") as fh:
            fh.write(build(row))
    except OSError as exc:
        log.warning("could not write the calendar file: %s", exc)
        return False
    try:
        os.startfile(path)  # Windows only, by design
        return True
    except AttributeError:
        log.info("calendar file written to %s (no shell handler on this platform)", path)
        return False
    except OSError as exc:
        log.warning("could not open the calendar file: %s", exc)
        return False
