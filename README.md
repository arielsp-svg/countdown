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
runner; download it from the run's artifacts, or from the release.

**On macOS or Linux, with Docker** — build through Wine:

```
docker run --rm --platform linux/amd64 -v "$PWD":/src -w /src tobix/pywine:3.12 sh -c \
  'wine python -m pip install -q -r requirements.txt pyinstaller==6.11.1 &&
   wine python -m PyInstaller --clean --noconfirm Countdown.spec'
```

The result is the same `dist/Countdown.exe`. On Apple Silicon this runs under
x86 emulation, so expect it to be slow.

## An example table

`demo/example-ro-table.xlsx` is a sample of the table the app reads. It is laid
out the way a maintained sheet would be: a title row above the header, the RO
dates held as real Excel date cells rather than text, and the eight columns in
their natural order.

Nine rows, each one showing a behaviour from the requirements:

| Row | Shows |
|---|---|
| F-16 Barak, 4 months out | Inside 6 months, so the weekly tier (R6) |
| F-15 Ra'am, 10 months out | Inside 12 months, so the monthly tier (R6) |
| C-130 Shimshon, 18 months out | Beyond both windows, no alert |
| Apache AH-64, 3 months past | RO date already gone, no alert |
| Blackhawk, `to be confirmed` | Unreadable RO date: skipped, listed for the admin (R4) |
| Beechcraft 200, empty cell | Same, skipped |
| Three rows in other departments | Filtered out for an Avionics user (R5) |

Point `sharepoint_url` at it to try the app against a real .xlsx:

```
sharepoint_url = demo/example-ro-table.xlsx
```

The dates are written relative to the day the file was generated, so the
committed copy ages. Regenerate it whenever it goes stale:

```
python demo/make_example_xlsx.py
```

## Try it on a Mac

The app is plain Python and tkinter, so it runs from source on macOS. Two things
are Windows only and simply log that they were skipped: registering for startup
(R1) and, on Windows, handing the .ics to Outlook — on a Mac it opens in
Calendar instead.

```
demo/try-on-mac.sh
```

The first run creates `.venv`, installs `openpyxl`, and writes a sandbox under
`demo/sandbox`: its own `countdown.txt` and a sample table whose RO dates are
generated relative to today. Everything the app writes stays in that folder, so
your real home directory and any live configuration are untouched.

Pick **Avionics** at the first run window. The sample table then produces:

| Row | What it shows |
|---|---|
| F-16 Barak, 4 months out | Inside 6 months, so the weekly tier: an alert right away |
| F-15 Ra'am, 10 months out | Inside 12 months, so the monthly tier: an alert right away |
| C-130 Shimshon, 18 months out | Beyond both windows, no alert |
| Apache AH-64, 3 months past | RO date already gone, no alert (R6) |
| Blackhawk, `to be confirmed` | Unreadable RO date, skipped and listed in the admin window (R4) |
| Beechcraft, Logistics | Another department, filtered out (R5) |

Other things worth trying:

```
demo/try-on-mac.sh --reset    # wipe the sandbox, so the first run window returns
demo/try-on-mac.sh --admin    # the maintenance window; sign in as admin / secret
```

In the maintenance window, change the tight tier to 12 months and reset, or set
a frequency to zero, to see R7's edge cases handled. Snooze a system and it
appears under **Snoozed systems**; the Blackhawk row appears under
**Skipped rows**.

`COUNTDOWN_HOME` is what redirects the configuration and state into that
sandbox. Nothing on a delivered Windows machine sets it.

## On an airgapped machine

Nothing needs installing. The .exe carries its own Python runtime
(`python312.dll`), the C runtime (`VCRUNTIME140.dll`, `ucrtbase.dll`), tkinter
and `openpyxl` inside it. Its import table asks the operating system for five
libraries only, and every one of them is part of a stock Windows install:

```
ADVAPI32.dll   COMCTL32.dll   GDI32.dll   KERNEL32.dll   USER32.dll
```

So there is no Python to deploy, no Visual C++ redistributable, and no .NET.
Copy the two files onto the machine and run them.

The table source is whatever the closed network offers. `sharepoint_url`
accepts any of these:

| Form | Example |
|---|---|
| An internal SharePoint link | `https://sharepoint.internal/:x:/s/dept/EbQ...` |
| A UNC share | `\\\\fs01\\shared\\ro-dates.xlsx` |
| A mapped drive or local folder | `D:\\tables\\ro-dates.xlsx` |
| A file beside the .exe | `ro-dates.xlsx` |

The one thing an airgap does not solve is code signing. An unsigned .exe that
writes a `Run` key is exactly the shape endpoint tooling blocks, and on a closed
network there is usually no reputation service to appeal to. Getting the binary
allow-listed, or signed with an internal certificate, is worth settling before
rollout.

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
- **On every launch, and every 24 hours after that**, the table is read. Only
  rows in your department count (R4, R5). R4 asks for the 24 hour cadence; the
  read on launch is added on top, because the app starts with Windows and a
  machine that was off for a week would otherwise wait out the rest of the
  interval on a stale timestamp. Reading is not alerting: R6, R10 and R11 still
  decide whether anything is shown, so reopening the app refreshes the data
  without producing extra popups.
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

## The interface

The windows are drawn on a canvas rather than themed with ttk. ttk cannot round
a corner, it looks different on every platform, and R13 rules out a widget
toolkit as a dependency, so `countdown/ui/design.py` holds a small set of pieces
- surfaces, pill buttons, fields, a closed list, a month view - built on nothing
but tkinter.

The app follows the Windows light and dark setting, reading
`AppsUseLightTheme` the way a native application would, and picks up Segoe UI
Variable Display where it exists.

## Tests

```
python -m unittest discover -s tests -v
```

36 tests, one class per requirement, covering the edge cases named in the table:
free text and empty RO dates, renamed and reordered columns, the tighter tier
winning, a missed interval, an RO date moving while a snooze is live, and a
logon name that is not `iaf\<number>`.
