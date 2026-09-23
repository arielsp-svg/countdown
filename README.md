# Countdown

RO dates for systems live only in a SharePoint table, and the table is silent.
Countdown reads that table once a day and pops an alert when a system in your
department is coming up on its RO date.

## What you ship

Two files, in one folder, no installer:

```
Countdown.exe
countdown.txt
```

## Build the .exe

PyInstaller cannot cross compile, so the .exe has to be produced on Windows.

**On a Windows machine** — Python 3.9 or newer installed, then:

```
build.bat
```

The result is `dist\Countdown.exe`, next to `dist\countdown.txt`.

**Without a Windows machine** — push this folder to GitHub. The workflow in
`.github/workflows/build.yml` runs the tests and builds the .exe on a Windows
runner; download it from the run's artifacts.

## Before handing it out

Open `countdown.txt` and set:

| Key | What it does |
|---|---|
| `admin_username`, `admin_password` | Checked before the maintenance window opens (R8) |
| `sharepoint_url` | Anonymous direct link to the RO table, .xlsx or .csv (R4) |
| `departments` | The closed list on the first run window (R2). Leave blank to take the list from the table's own department column instead |

## How it behaves

- **First launch** registers the .exe under `HKCU\...\CurrentVersion\Run`, so it
  starts with Windows (R1). The value is rewritten on every launch, so moving
  the folder or copying the .exe to another machine repairs itself.
- **First run window** asks for name, personal number and department. Nothing
  runs in the background until all three are given (R2).
- **Every 24 hours** the table is downloaded and read. Only rows in your
  department count (R4, R5).
- **Alerts** fire monthly inside 12 months of the RO date and weekly inside 6
  months. A row inside both windows uses the tighter one (R6).
- **The popup** shows the platform and the RO date, offers to add the date to
  your calendar, and carries *I read, understood, close window* and
  *Remind me later* (R9, R10, R11).
- **Nothing else is ever visible.** No tray icon, no console, no window (R12).

## Maintenance window

Run `Countdown.exe` again while it is already running — or run it with
`--admin` — and the credential prompt appears. Past it are four tabs:

- **Alert tiers** — the threshold in months and the frequency in days per tier.
  Changes apply at the next daily run (R7).
- **Snoozed systems** — what has been put off, until when, and how many times.
- **Skipped rows** — rows whose RO date cell holds free text, so the table owner
  can fix the cell.
- **Status** — last read, resolved personal number, file locations.

## Where things live

| | |
|---|---|
| Configuration | `countdown.txt`, next to the .exe |
| State | `%APPDATA%\Countdown\state.json` |
| Log | `%APPDATA%\Countdown\countdown.log` |

## Decisions taken on the spec's Open Questions

The spec leaves these open. Each one is implemented as stated below and can be
changed; the code points at the requirement it serves.

| Question | Decided as |
|---|---|
| **State has no home** (R13) | `countdown.txt` holds only what an admin edits. Everything the app writes — identity, tiers, alert history, snoozes — goes to `%APPDATA%\Countdown\state.json`. The delivered folder stays as R13 specifies. Being per user, it also settles "a different user signs in on the same machine": he gets his own first run. |
| **Personal number collected twice** | The field stays, prefilled from the logon name. On a mismatch the logon value wins, because it cannot be mistyped; the typed value is kept and shown in the maintenance window. A logon name not of the form `iaf\<number>` falls back to the typed value. |
| **Snooze ceiling** | At most 90 days per snooze and at most 3 snoozes per system, after which the button is refused. Bounded above by the RO date and below by tomorrow, so the picker cannot produce an invalid date. Snoozes are per user, and every live one is listed in the maintenance window. |
| **Department list source** | `departments` in the .txt, falling back to the table's own department column. |
| **Add to calendar** | An .ics file handed to the shell, which opens it in the default calendar. No Outlook automation, no extra dependency. |
| **Link unreachable or layout changed** | Retry quietly in 2 hours. The user is not interrupted for an infrastructure problem; the failure goes to the log. |
| **Several systems due the same day** | One popup per system, shown one after another, soonest RO date first. |
| **RO date already passed** | No alert. Overdue rows are counted in the log rather than nagging daily. |
| **Rows skipped for a text RO date** | Silent to the user, listed in the maintenance window's *Skipped rows* tab. |
| **First run window closed unfilled** | Nothing is saved and the app does not start. The window returns at the next Windows startup. |
| **Machine off for weeks** | One alert on the next run, then the cadence resumes. Missed intervals do not stack. |
| **Popup closed with the X** | Not an acknowledgement. The system is offered again at the next daily run. |

## Risks carried forward from the spec

- **Antivirus and policy.** An unsigned single .exe that writes a `Run` key is
  what endpoint tooling is built to stop. If the key is denied the app logs it
  and still runs for the session; it just will not come back after a reboot.
  Signing the .exe, or allow-listing it, is the real mitigation.
- **Cleartext credentials.** `countdown.txt` sits next to the .exe and any user
  on the machine can read and edit it. This is what R13 and R8 ask for together;
  the owner of the systems should confirm it is acceptable.

## Tests

```
python -m unittest discover -s tests -v
```

36 tests, one class per requirement, covering the edge cases named in the table:
free text and empty RO dates, renamed and reordered columns, the tighter tier
winning, a missed interval, an RO date moving while a snooze is live, and a
logon name that is not `iaf\<number>`.
