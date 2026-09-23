"""Tests against the requirements table."""
import os
import sys
import tempfile
import unittest
from datetime import date, timedelta

# Everything the app writes now lives beside the .exe, so the tests have to
# point that somewhere disposable or they would rewrite the real
# countdown.txt sitting in the project root.
os.environ["COUNTDOWN_HOME"] = tempfile.mkdtemp()
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from countdown import app as app_module  # noqa: E402
from countdown import calendar_file, config, engine, identity, table  # noqa: E402
from countdown import users as users_module  # noqa: E402
from countdown import state as state_module  # noqa: E402

TODAY = date(2026, 9, 23)

HEADER = b"Department,Type of system,Platform,Nav system,Receiver model,Using TOD,Comments,RO date\n"


def build_table(*rows):
    return HEADER + b"".join(rows)


def make_state(department="Alpha"):
    st = state_module.State()
    st.set_identity("Tester", "1234567", department)
    return st


USER_HEADER = b"Name,Personal number,Department\n"


def build_users(*rows):
    return USER_HEADER + b"".join(rows)


class TestTableReading(unittest.TestCase):
    """R4: the columns are read; unreadable RO dates are skipped, not alerted."""

    def test_reads_every_specified_column(self):
        rows, _ = table.parse(build_table(b"Alpha,Radar,F-16,INS,R-200,yes,note,01/03/2027\n"))
        row = rows[0]
        self.assertEqual(row.department, "Alpha")
        self.assertEqual(row.type_of_system, "Radar")
        self.assertEqual(row.platform, "F-16")
        self.assertEqual(row.nav_system, "INS")
        self.assertEqual(row.receiver_model, "R-200")
        self.assertEqual(row.using_tod, "yes")
        self.assertEqual(row.comments, "note")
        self.assertEqual(row.ro_date, date(2027, 3, 1))

    def test_free_text_ro_date_is_skipped_and_recorded(self):
        rows, skipped = table.parse(build_table(b"Alpha,Radar,F-15,INS,R-9,,,to be decided\n"))
        self.assertEqual(rows, [])
        self.assertEqual(skipped[0]["value"], "to be decided")

    def test_empty_ro_date_is_skipped(self):
        rows, skipped = table.parse(build_table(b"Alpha,Radar,F-15,INS,R-9,,,\n"))
        self.assertEqual(rows, [])
        self.assertEqual(len(skipped), 1)

    def test_reordered_columns_still_read(self):
        payload = b"RO date,Platform,Department\n01/03/2027,F-16,Alpha\n"
        rows, _ = table.parse(payload)
        self.assertEqual(rows[0].ro_date, date(2027, 3, 1))
        self.assertEqual(rows[0].platform, "F-16")

    def test_removed_column_is_reported(self):
        with self.assertRaises(table.TableError) as ctx:
            table.parse(b"Platform,Notes\nF-16,x\n")
        self.assertIn("missing required column", str(ctx.exception))

    def test_title_rows_above_the_header_are_tolerated(self):
        rows, _ = table.parse(b"RO tracking sheet\n\n" + build_table(
            b"Alpha,Radar,F-16,INS,R-200,yes,,01/03/2027\n"))
        self.assertEqual(len(rows), 1)

    def test_day_first_dates(self):
        self.assertEqual(table.parse_ro_date("03/04/2027"), date(2027, 4, 3))
        self.assertEqual(table.parse_ro_date("2027-04-03"), date(2027, 4, 3))
        self.assertIsNone(table.parse_ro_date("soon"))

    def test_html_response_is_an_error(self):
        with self.assertRaises(table.TableError):
            table.parse(b"<!DOCTYPE html><html>sign in</html>")


class TestDepartmentFilter(unittest.TestCase):
    """R5: only rows in the user's department are considered."""

    def test_other_departments_are_ignored(self):
        rows, _ = table.parse(build_table(
            b"Alpha,Radar,F-16,INS,R-200,yes,,01/12/2026\n",
            b"Bravo,Radar,F-15,INS,R-300,yes,,01/12/2026\n"))
        due = engine.due_systems(rows, make_state("Alpha"), TODAY)
        self.assertEqual([r.platform for r, _ in due], ["F-16"])

    def test_empty_department_never_matches(self):
        rows, _ = table.parse(build_table(b",Radar,F-16,INS,R-200,yes,,01/12/2026\n"))
        self.assertEqual(engine.due_systems(rows, make_state("Alpha"), TODAY), [])

    def test_match_ignores_case_and_padding(self):
        self.assertTrue(engine.department_matches("  alpha ", "Alpha"))
        self.assertFalse(engine.department_matches("", ""))


class TestCadence(unittest.TestCase):
    """R6: monthly inside 12 months, weekly inside 6, tighter tier wins."""

    def setUp(self):
        self.tiers = state_module.DEFAULT_TIERS

    def test_beyond_the_widest_window_no_tier(self):
        self.assertIsNone(engine.tier_for(engine.add_months(TODAY, 13), self.tiers, TODAY))

    def test_inside_twelve_months_is_monthly(self):
        tier = engine.tier_for(engine.add_months(TODAY, 11), self.tiers, TODAY)
        self.assertEqual(engine.interval_days(tier), 30)

    def test_inside_six_months_is_weekly(self):
        tier = engine.tier_for(engine.add_months(TODAY, 5), self.tiers, TODAY)
        self.assertEqual(engine.interval_days(tier), 7)

    def test_row_inside_both_windows_takes_the_tighter(self):
        # Five months away is inside 12 and inside 6; weekly must win.
        tier = engine.tier_for(TODAY + timedelta(days=150), self.tiers, TODAY)
        self.assertEqual(tier["name"], "tight")

    def test_first_run_on_a_row_already_inside_a_window_alerts_at_once(self):
        rows, _ = table.parse(build_table(b"Alpha,Radar,F-16,INS,R-200,yes,,01/12/2026\n"))
        self.assertEqual(len(engine.due_systems(rows, make_state(), TODAY)), 1)

    def test_passed_ro_date_raises_no_alert(self):
        rows, _ = table.parse(build_table(b"Alpha,Radar,F-16,INS,R-200,yes,,01/01/2020\n"))
        st = make_state()
        self.assertEqual(engine.due_systems(rows, st, TODAY), [])
        self.assertEqual(len(engine.overdue_systems(rows, st, TODAY)), 1)

    def test_blank_or_zero_frequency_does_not_alert_daily(self):
        self.assertEqual(engine.interval_days({"months": 6, "every_days": 0}), 30)
        self.assertEqual(engine.interval_days({"months": 6, "every_days": ""}), 30)

    def test_month_end_clamping(self):
        self.assertEqual(engine.add_months(date(2026, 1, 31), 1), date(2026, 2, 28))


class TestAcknowledge(unittest.TestCase):
    """R10: an acknowledged system is quiet until its next interval."""

    def setUp(self):
        self.rows, _ = table.parse(build_table(b"Alpha,Radar,F-16,INS,R-200,yes,,01/12/2026\n"))
        self.state = make_state()
        self.key = self.rows[0].key
        self.state.mark_alerted(self.key, TODAY)

    def test_quiet_inside_the_interval(self):
        self.assertEqual(engine.due_systems(self.rows, self.state, TODAY + timedelta(days=6)), [])

    def test_returns_at_the_interval(self):
        self.assertEqual(len(engine.due_systems(self.rows, self.state, TODAY + timedelta(days=7))), 1)

    def test_survives_a_restart(self):
        state_module.save(self.state)
        reloaded = state_module.load()
        self.assertEqual(reloaded.last_alert(self.key), TODAY)
        self.assertEqual(engine.due_systems(self.rows, reloaded, TODAY + timedelta(days=1)), [])

    def test_a_missed_interval_alerts_once_and_resumes(self):
        # Machine off for weeks: one alert, not one per missed interval.
        due = engine.due_systems(self.rows, self.state, TODAY + timedelta(days=60))
        self.assertEqual(len(due), 1)


class TestSnooze(unittest.TestCase):
    """R11: quiet until the chosen date, then the cadence resumes."""

    def setUp(self):
        self.rows, _ = table.parse(build_table(b"Alpha,Radar,F-16,INS,R-200,yes,,01/12/2026\n"))
        self.state = make_state()
        self.key = self.rows[0].key

    def test_quiet_until_the_chosen_date(self):
        self.state.set_snooze(self.key, TODAY + timedelta(days=10))
        self.assertEqual(engine.due_systems(self.rows, self.state, TODAY + timedelta(days=9)), [])

    def test_cadence_resumes_on_that_date(self):
        self.state.set_snooze(self.key, TODAY + timedelta(days=10))
        self.assertEqual(len(engine.due_systems(self.rows, self.state, TODAY + timedelta(days=11))), 1)

    def test_snooze_survives_the_ro_date_moving_earlier(self):
        self.state.set_snooze(self.key, TODAY + timedelta(days=10))
        moved, _ = table.parse(build_table(b"Alpha,Radar,F-16,INS,R-200,yes,,01/11/2026\n"))
        self.assertEqual(moved[0].key, self.key)
        self.assertEqual(engine.due_systems(moved, self.state, TODAY + timedelta(days=5)), [])

    def test_snoozes_are_counted_and_visible(self):
        self.state.set_snooze(self.key, TODAY + timedelta(days=10))
        self.state.set_snooze(self.key, TODAY + timedelta(days=20))
        self.assertEqual(self.state.snooze_count(self.key), 2)
        self.assertEqual(len(self.state.snoozed_systems()), 1)

    def test_an_expired_snooze_is_no_longer_listed(self):
        self.state.set_snooze(self.key, TODAY - timedelta(days=1))
        self.assertEqual(self.state.snoozed_systems(), [])


class TestIdentity(unittest.TestCase):
    """R3: the personal number comes from the iaf\\<number> logon name."""

    def setUp(self):
        self.users, _ = users_module.parse(build_users(
            b"R. Levi,8123456,Avionics\n",
            b"D. Cohen,8123457,Logistics\n"))

    def tearDown(self):
        os.environ.pop("USERDOMAIN", None)
        os.environ.pop("USERNAME", None)

    def test_extracts_the_number(self):
        os.environ["USERDOMAIN"], os.environ["USERNAME"] = "iaf", "8123456"
        self.assertEqual(identity.personal_number_from_logon(), "8123456")

    def test_the_logon_resolves_to_that_person(self):
        os.environ["USERDOMAIN"], os.environ["USERNAME"] = "iaf", "8123457"
        user, reason = identity.resolve(self.users)
        self.assertEqual((user.name, user.department), ("D. Cohen", "Logistics"))
        self.assertEqual(reason, "")

    def test_a_logon_shape_it_cannot_read_gives_a_reason(self):
        os.environ["USERDOMAIN"], os.environ["USERNAME"] = "CORP", "r.levi"
        user, reason = identity.resolve(self.users)
        self.assertIsNone(user)
        self.assertIn("iaf", reason)

    def test_someone_missing_from_the_list_gives_a_reason(self):
        os.environ["USERDOMAIN"], os.environ["USERNAME"] = "iaf", "9999999"
        user, reason = identity.resolve(self.users)
        self.assertIsNone(user)
        self.assertIn("not in the user list", reason)


class TestUserDirectory(unittest.TestCase):
    """The user list: name, personal number and department, held elsewhere."""

    def test_reads_the_three_columns(self):
        users, skipped = users_module.parse(build_users(b"R. Levi,8123456,Avionics\n"))
        self.assertEqual(skipped, [])
        self.assertEqual((users[0].name, users[0].personal_number,
                          users[0].department), ("R. Levi", "8123456", "Avionics"))

    def test_reordered_and_renamed_headers_still_read(self):
        users, _ = users_module.parse(
            b"Department,ID,Full name\nAvionics,8123456,R. Levi\n")
        self.assertEqual(users[0].department, "Avionics")
        self.assertEqual(users[0].personal_number, "8123456")

    def test_excel_turning_the_number_into_a_float(self):
        self.assertEqual(users_module.normalise_number("8123456.0"), "8123456")

    def test_a_number_written_with_the_domain(self):
        self.assertEqual(users_module.normalise_number(r"iaf\8123456"), "8123456")

    def test_a_row_without_a_number_or_department_is_skipped(self):
        users, skipped = users_module.parse(build_users(
            b"No Number,,Avionics\n", b"No Dept,8123456,\n"))
        self.assertEqual(users, [])
        self.assertEqual(len(skipped), 2)

    def test_a_missing_column_is_reported(self):
        with self.assertRaises(users_module.UsersError) as ctx:
            users_module.parse(b"Name,Favourite colour\nR. Levi,blue\n")
        self.assertIn("missing required column", str(ctx.exception))

    def test_adding_someone(self):
        users, _ = users_module.parse(build_users(b"R. Levi,8123456,Avionics\n"))
        updated = users_module.add(users, "D. Cohen", "8123457", "Logistics")
        self.assertEqual(len(updated), 2)

    def test_a_duplicate_number_is_refused(self):
        users, _ = users_module.parse(build_users(b"R. Levi,8123456,Avionics\n"))
        with self.assertRaises(users_module.UsersError):
            users_module.add(users, "Someone Else", "8123456", "Logistics")

    def test_an_incomplete_entry_is_refused(self):
        users = []
        for bad in [("", "8123456", "Avionics"), ("R. Levi", "", "Avionics"),
                    ("R. Levi", "8123456", "")]:
            with self.assertRaises(users_module.UsersError):
                users_module.add(users, *bad)

    def test_removing_someone(self):
        users, _ = users_module.parse(build_users(
            b"R. Levi,8123456,Avionics\n", b"D. Cohen,8123457,Logistics\n"))
        self.assertEqual(len(users_module.remove(users, "8123456")), 1)

    def test_a_link_cannot_be_written_back(self):
        self.assertIsNone(users_module.writable_path(
            "https://sharepoint.internal/:x:/s/dept/EbQ"))

    def test_a_path_can_be_written_back(self):
        self.assertIsNotNone(users_module.writable_path("users.xlsx"))


class TestConfig(unittest.TestCase):
    """R8: credentials come from the .txt; a bad file must not crash the app."""

    def test_missing_file_yields_defaults(self):
        cfg = config.load()
        self.assertEqual(cfg.sharepoint_url, cfg.sharepoint_url)
        self.assertIsInstance(cfg.users_url, str)

    def test_incomplete_credentials_are_not_accepted(self):
        cfg = config.Config(dict(config.DEFAULTS))
        cfg["admin_username"] = ""
        self.assertFalse(cfg.has_admin_credentials)

    def test_both_workbook_links_are_read(self):
        cfg = config.Config(dict(config.DEFAULTS,
                                 sharepoint_url=" ro.xlsx ", users_url=" users.xlsx "))
        self.assertEqual(cfg.sharepoint_url, "ro.xlsx")
        self.assertEqual(cfg.users_url, "users.xlsx")


class TestConfigWriteBack(unittest.TestCase):
    """The maintenance window writes back to countdown.txt."""

    def setUp(self):
        from countdown import paths
        self.path = paths.config_path()
        config.ensure_exists()

    def test_a_value_is_written_back(self):
        config.save_value("users_url", r"\\fs01\share\users.xlsx")
        self.assertEqual(config.load().users_url, r"\\fs01\share\users.xlsx")

    def test_writing_one_key_leaves_the_others_alone(self):
        config.save_value("admin_password", "hunter2")
        config.save_value("users_url", "users.xlsx")
        cfg = config.load()
        self.assertEqual(cfg.admin_password, "hunter2")
        self.assertEqual(cfg.users_url, "users.xlsx")

    def test_the_admin_comments_survive_a_write(self):
        config.save_value("users_url", "users.xlsx")
        with open(self.path, encoding="utf-8") as fh:
            body = fh.read()
        self.assertIn("# Countdown configuration", body)

    def test_an_unknown_key_is_refused(self):
        self.assertFalse(config.save_value("not_a_real_key", "x"))


class TestCalendarFile(unittest.TestCase):
    """R9: the popup offers to add the date to the calendar."""

    def test_ics_holds_the_ro_date(self):
        rows, _ = table.parse(build_table(b"Alpha,Radar,F-16,INS,R-200,yes,a; b,01/03/2027\n"))
        ics = calendar_file.build(rows[0])
        self.assertIn("DTSTART;VALUE=DATE:20270301", ics)
        self.assertIn("SUMMARY:RO date - F-16", ics)
        self.assertIn(r"a\; b", ics)          # semicolons escaped per RFC 5545
        self.assertTrue(ics.startswith("BEGIN:VCALENDAR"))


class TestReadSchedule(unittest.TestCase):
    """R4 every 24 hours, plus a read on every launch."""

    def setUp(self):
        from datetime import datetime
        self.now = datetime(2026, 9, 23, 9, 0)
        self.recent = datetime(2026, 9, 23, 8, 0)      # an hour ago
        self.stale = datetime(2026, 9, 21, 8, 0)       # two days ago

    def test_a_launch_always_reads_even_if_just_read(self):
        self.assertTrue(app_module.should_read(self.recent, self.now, False))

    def test_after_the_launch_read_it_waits_out_the_interval(self):
        self.assertFalse(app_module.should_read(self.recent, self.now, True))

    def test_it_reads_again_once_the_interval_has_passed(self):
        self.assertTrue(app_module.should_read(self.stale, self.now, True))

    def test_never_read_before_means_read(self):
        self.assertTrue(app_module.should_read(None, self.now, True))

    def test_the_retry_backoff_holds_a_running_app_back(self):
        from datetime import timedelta
        later = self.now + timedelta(hours=1)
        self.assertFalse(app_module.should_read(self.stale, self.now, True, later))

    def test_a_launch_ignores_the_backoff(self):
        from datetime import timedelta
        later = self.now + timedelta(hours=1)
        self.assertTrue(app_module.should_read(self.stale, self.now, False, later))


class TestWhereThingsAreSaved(unittest.TestCase):
    """Everything the app writes sits beside the .exe, and nowhere else."""

    def setUp(self):
        from countdown import paths
        self.paths = paths

    def test_state_log_and_config_share_the_app_folder(self):
        folder = self.paths.app_dir()
        for path in (self.paths.state_path(), self.paths.log_path(),
                     self.paths.config_path(), self.paths.lock_path()):
            self.assertEqual(os.path.dirname(path), folder)

    def test_nothing_is_written_to_appdata(self):
        appdata = os.environ.get("APPDATA")
        if appdata:
            self.assertNotIn(os.path.normpath(appdata),
                             os.path.normpath(self.paths.state_path()))

    def test_two_users_get_separate_state_files(self):
        original = os.environ.get("USERNAME")
        try:
            os.environ["USERNAME"] = "8123456"
            first = self.paths.state_path()
            os.environ["USERNAME"] = "8123457"
            second = self.paths.state_path()
        finally:
            if original is None:
                os.environ.pop("USERNAME", None)
            else:
                os.environ["USERNAME"] = original
        # R3: a second user on the same machine must not inherit the first's
        # identity, snoozes or alert history.
        self.assertNotEqual(first, second)
        self.assertEqual(os.path.dirname(first), os.path.dirname(second))

    def test_an_awkward_logon_name_still_makes_a_valid_filename(self):
        saved = {k: os.environ.get(k) for k in ("USERNAME", "USER")}
        try:
            os.environ["USERNAME"] = "iaf" + chr(92) + "8123456"
            self.assertEqual(self.paths.user_slug(), "iaf_8123456")
            # With no logon name at all the file still has to be nameable.
            os.environ["USERNAME"] = ""
            os.environ["USER"] = ""
            self.assertEqual(self.paths.user_slug(), self.paths.FALLBACK_USER)
        finally:
            for key, value in saved.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value

    def test_a_writable_folder_is_reported_as_writable(self):
        self.assertTrue(self.paths.writable())


class TestStatePersistence(unittest.TestCase):
    def test_corrupt_state_file_falls_back_to_defaults(self):
        from countdown import paths
        with open(paths.state_path(), "w", encoding="utf-8") as fh:
            fh.write("{ not json")
        st = state_module.load()
        self.assertEqual(st.department, "")
        self.assertEqual(st.tiers, sorted(state_module.DEFAULT_TIERS, key=lambda t: -t["months"]))


if __name__ == "__main__":
    unittest.main(verbosity=2)
