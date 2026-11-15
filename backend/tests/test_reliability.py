"""起動・通知・ディスク識別・収集失敗・NVMe・ポート・容量マップの回帰テスト。"""

from __future__ import annotations

import socket
import subprocess
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.alert_policy import decide_alert, dedupe_key_for, keys_to_resolve, legacy_dedupe_key
from app.collectors.capacity import CapacityCollectionError, parse_volume_payload
from app.collectors.disks import DiskCollectionError, ensure_disk_rows
from app.collectors.inventory import inventory_error_message
from app.config import parse_listen_port
from app.disk_identity import disk_stable_id
from app.engine.risk import evaluate
from app.net_bind import port_is_free
from app.schedule import (
    classify_scan_outcome,
    daily_is_due,
    startup_covers_daily,
    startup_should_delay_daily,
)
from app.space_schedule import space_map_due
from app.space_scan import drive_type_included


def _settings() -> dict:
    return {"capacity_warn_pct": 10, "capacity_critical_pct": 5}


def _healthy_disk(**smart: object) -> dict:
    payload = {
        "overall": "PASSED",
        "smart_status": "PASSED",
        "attributes": {},
    }
    payload.update(smart)
    return {
        "device_id": "0",
        "stable_id": "sn:ABC|mdl:TEST",
        "model": "Test NVMe",
        "health_status": "Healthy",
        "os_health_status": "Healthy",
        "smart": payload,
    }


class AlertPolicyTests(unittest.TestCase):
    def test_same_level_with_different_numbers_does_not_notify(self) -> None:
        previous = {
            "level": "Watch",
            "title": "容量不足: C:",
            "message": "C: の空き容量が 9.0%（40 GB）です",
            "kind": "capacity",
            "target": "C:",
        }
        current = {
            "level": "Watch",
            "title": "容量不足: C:",
            "message": "C: の空き容量が 8.2%（36 GB）です",
            "kind": "capacity",
            "target": "C:",
        }
        self.assertEqual(dedupe_key_for(previous), dedupe_key_for(current))
        record, notify = decide_alert(current, "Watch", previous["message"])
        self.assertFalse(record)
        self.assertFalse(notify)

    def test_same_level_new_reason_kind_notifies_once(self) -> None:
        record, notify = decide_alert(
            {"level": "Watch", "kind": "disk", "target": "x", "message": "SSD摩耗度: 91%"},
            "Watch",
            "温度高め: 61°C",
        )
        self.assertTrue(record)
        self.assertTrue(notify)

    def test_resolved_key_can_notify_again_at_the_same_level(self) -> None:
        self.assertEqual(keys_to_resolve({"capacity|C:": "Watch", "disk|sn:1": "OK"}, set()), ["capacity|C:"])
        record, notify = decide_alert(
            {"level": "Watch", "kind": "capacity", "target": "C:", "message": "空き 9%"},
            "OK",
            "前回までの注意は、今回のスキャンでは見当たりませんでした。",
        )
        self.assertTrue(record)
        self.assertTrue(notify)

    def test_legacy_capacity_title_gets_a_stable_key(self) -> None:
        self.assertEqual(legacy_dedupe_key("容量不足: C:", None), ("capacity", "capacity|C:"))

    def test_notify_only_when_level_worsens(self) -> None:
        alert = {"level": "Critical", "kind": "disk", "target": "sn:ABC|mdl:TEST"}
        record, notify = decide_alert(alert, "Watch")
        self.assertTrue(record)
        self.assertTrue(notify)
        record, notify = decide_alert({"level": "Watch", "kind": "disk", "target": "x"}, "Critical")
        self.assertTrue(record)
        self.assertFalse(notify)

    def test_unknown_is_recorded_without_toast(self) -> None:
        record, notify = decide_alert(
            {"level": "Unknown", "kind": "collection", "target": "disks"},
            None,
        )
        self.assertTrue(record)
        self.assertFalse(notify)


class DiskIdentityTests(unittest.TestCase):
    def test_serial_and_model_ignore_windows_disk_number(self) -> None:
        first = disk_stable_id(
            {"device_id": "0", "model": "Samsung SSD", "serial": "S3Z1"}
        )
        replugged = disk_stable_id(
            {"device_id": "3", "model": "Samsung SSD", "serial": " s3z1 "}
        )
        other = disk_stable_id(
            {"device_id": "3", "model": "Samsung SSD", "serial": "OTHER"}
        )
        self.assertEqual(first, replugged)
        self.assertNotEqual(first, other)
        self.assertTrue(first.startswith("sn:"))

    def test_placeholder_serial_falls_back(self) -> None:
        ident = disk_stable_id(
            {
                "device_id": "1",
                "model": "USB Disk",
                "serial": "00000000",
                "pnp_device_id": "USB\\VID_1234\\ABC",
            }
        )
        self.assertTrue(ident.startswith("pnp:"))

    def test_model_and_size_when_serial_missing(self) -> None:
        ident = disk_stable_id(
            {
                "device_id": "2",
                "model": "WDC WD10",
                "serial": "",
                "size_bytes": 1000,
                "bus_type": "SATA",
                "media_type": "HDD",
            }
        )
        self.assertTrue(ident.startswith("fb:"))
        self.assertIn("1000", ident)


class KnownDiskTests(unittest.TestCase):
    def setUp(self) -> None:
        import app.db as db

        self.db = db
        self.tmp = tempfile.TemporaryDirectory()
        self._old_db = db.DB_PATH
        self._old_dir = db.DATA_DIR
        data = Path(self.tmp.name)
        db.DATA_DIR = data
        db.DB_PATH = data / "health.db"
        db.init_db()

    def tearDown(self) -> None:
        self.db.DB_PATH = self._old_db
        self.db.DATA_DIR = self._old_dir
        self.tmp.cleanup()

    def test_first_scan_is_baseline_without_new_disk_alerts(self) -> None:
        disk = {"device_id": "0", "model": "Samsung SSD", "serial": "S3Z1"}
        changes = self.db.upsert_known_disks([disk])
        self.assertTrue(changes["baseline"])
        self.assertEqual(changes["appeared"], [])
        self.assertEqual(changes["disappeared"], [])

    def test_replug_keeps_history_and_does_not_look_new(self) -> None:
        original = {"device_id": "0", "model": "Samsung SSD", "serial": "S3Z1"}
        self.db.upsert_known_disks([original])
        stable = original["stable_id"]
        self.db.save_disk_history([{"device_id": "0", "stable_id": stable, "model": "Samsung SSD"}])
        moved = {"device_id": "4", "model": "Samsung SSD", "serial": "S3Z1"}
        changes = self.db.upsert_known_disks([moved])
        self.assertFalse(changes["baseline"])
        self.assertEqual(changes["appeared"], [])
        self.assertEqual(changes["disappeared"], [])
        history = self.db.get_disk_history(moved["stable_id"])
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["device_id"], moved["stable_id"])

    def test_legacy_number_row_follows_serial(self) -> None:
        now = "2026-01-01T00:00:00+00:00"
        with self.db.connect() as conn:
            conn.execute(
                """
                INSERT INTO known_disks (device_id, model, serial, first_seen, last_seen)
                VALUES ('0', 'Samsung SSD', 'S3Z1', ?, ?)
                """,
                (now, now),
            )
            conn.execute(
                """
                INSERT INTO disk_history
                (created_at, device_id, model, health_status, free_pct, risk_level, smart_json)
                VALUES (?, '0', 'Samsung SSD', 'Healthy', 50, 'OK', '{}')
                """,
                (now,),
            )
        changes = self.db.upsert_known_disks(
            [{"device_id": "2", "model": "Samsung SSD", "serial": "S3Z1"}]
        )
        self.assertEqual(changes["appeared"], [])
        self.assertEqual(changes["disappeared"], [])
        stable = disk_stable_id({"device_id": "2", "model": "Samsung SSD", "serial": "S3Z1"})
        history = self.db.get_disk_history(stable)
        self.assertEqual(len(history), 1)

    def test_swapped_numbers_follow_model_when_serial_missing(self) -> None:
        now = "2026-01-01T00:00:00+00:00"
        with self.db.connect() as conn:
            conn.execute(
                "INSERT INTO known_disks (device_id, model, serial, first_seen, last_seen) VALUES ('0', 'Alpha', '', ?, ?)",
                (now, now),
            )
            conn.execute(
                "INSERT INTO known_disks (device_id, model, serial, first_seen, last_seen) VALUES ('1', 'Beta', '', ?, ?)",
                (now, now),
            )
        changes = self.db.upsert_known_disks(
            [
                {"device_id": "0", "model": "Beta", "serial": "", "size_bytes": 2, "bus_type": "SATA", "media_type": "HDD"},
                {"device_id": "1", "model": "Alpha", "serial": "", "size_bytes": 1, "bus_type": "SATA", "media_type": "HDD"},
            ]
        )
        self.assertEqual(changes["appeared"], [])
        self.assertEqual(changes["disappeared"], [])

    def test_identical_disks_without_serial_keep_ids_when_numbers_swap(self) -> None:
        def plain(number: str) -> dict:
            return {
                "device_id": number,
                "model": "Bar",
                "serial": "",
                "size_bytes": 100,
                "bus_type": "SATA",
                "media_type": "HDD",
            }

        self.db.upsert_known_disks([plain("0"), plain("1")])
        changes = self.db.upsert_known_disks([plain("1"), plain("0")])
        self.assertEqual(changes["appeared"], [])
        self.assertEqual(changes["disappeared"], [])

    def test_serial_id_does_not_fall_back_to_pnp_when_serial_disappears(self) -> None:
        base = {
            "device_id": "0",
            "model": "Foo",
            "serial": "",
            "pnp_device_id": r"USB\VID\ABC",
        }
        self.db.upsert_known_disks([base])
        self.db.upsert_known_disks([{**base, "serial": "S1"}])
        changes = self.db.upsert_known_disks([base])
        self.assertEqual(changes["appeared"], [])
        self.assertEqual(changes["disappeared"], [])
        with self.db.connect() as conn:
            stored = [str(row["device_id"]) for row in conn.execute("SELECT device_id FROM known_disks")]
        self.assertEqual(stored, [stored[0]])
        self.assertEqual(len(stored), 1)
        self.assertTrue(stored[0].startswith("sn:"))

    def test_old_alerts_without_keys_are_backfilled(self) -> None:
        with self.db.connect() as conn:
            conn.execute(
                """
                INSERT INTO alerts (created_at, level, title, message, device_id, notified)
                VALUES ('2026-11-15T00:00:00+00:00', 'Watch', '容量不足: C:', '空き 9%', NULL, 1)
                """
            )
        self.db.init_db()
        self.assertEqual(self.db.get_latest_alert_levels().get("capacity|C:"), "Watch")

    def test_same_message_does_not_duplicate_alert_rows(self) -> None:
        alert = {
            "level": "Watch",
            "title": "容量不足: C:",
            "message": "空き 9%",
            "kind": "capacity",
            "target": "C:",
        }
        key = dedupe_key_for(alert)
        record, notify = decide_alert(alert, None)
        self.assertTrue(record and notify)
        self.db.add_alert(alert["level"], alert["title"], alert["message"], None, True, "capacity", key)
        latest = self.db.get_latest_alert_levels()
        record, notify = decide_alert({**alert, "message": "空き 8%"}, latest[key])
        self.assertFalse(record)
        self.assertEqual(len(self.db.get_recent_alerts()), 1)


class RiskTests(unittest.TestCase):
    def test_nvme_critical_warning_is_critical(self) -> None:
        result = evaluate(
            {"disks": [_healthy_disk(critical_warning=4)], "volumes": []},
            _settings(),
        )
        self.assertEqual(result["overall_status"], "Critical")
        self.assertTrue(any("重大警告" in reason for reason in result["disks"][0]["reasons"]))

    def test_zero_critical_warning_is_not_a_problem(self) -> None:
        result = evaluate(
            {"disks": [_healthy_disk(critical_warning=0)], "volumes": []},
            _settings(),
        )
        self.assertEqual(result["disks"][0]["risk_level"], "OK")

    def test_available_spare_at_or_below_threshold_is_replace_soon(self) -> None:
        low = evaluate(
            {
                "disks": [_healthy_disk(available_spare=10, available_spare_threshold=10)],
                "volumes": [],
            },
            _settings(),
        )
        self.assertEqual(low["disks"][0]["risk_level"], "ReplaceSoon")
        ok = evaluate(
            {
                "disks": [_healthy_disk(available_spare=11, available_spare_threshold=10)],
                "volumes": [],
            },
            _settings(),
        )
        self.assertEqual(ok["disks"][0]["risk_level"], "OK")
        ignored = evaluate(
            {"disks": [_healthy_disk(available_spare=1)], "volumes": []},
            _settings(),
        )
        self.assertEqual(ignored["disks"][0]["risk_level"], "OK")

    def test_critical_warning_outranks_spare(self) -> None:
        result = evaluate(
            {
                "disks": [
                    _healthy_disk(
                        critical_warning=1,
                        available_spare=5,
                        available_spare_threshold=10,
                    )
                ],
                "volumes": [],
            },
            _settings(),
        )
        self.assertEqual(result["overall_status"], "Critical")

    def test_collection_failures_are_unknown_not_ok(self) -> None:
        result = evaluate(
            {
                "disks": [],
                "volumes": [],
                "disk_collection_error": "物理ディスクを取得できませんでした",
                "volume_collection_error": "空き容量の取得に失敗しました",
            },
            _settings(),
        )
        self.assertEqual(result["overall_status"], "Unknown")
        self.assertIn("disk_collection_error", result)
        self.assertIn("volume_collection_error", result)
        kinds = {alert["kind"] for alert in result["alerts"]}
        self.assertIn("collection", kinds)
        self.assertNotEqual(result["overall_status"], "OK")


class CollectionFailureTests(unittest.TestCase):
    def test_empty_physical_disk_payload_is_an_error(self) -> None:
        with self.assertRaises(DiskCollectionError):
            ensure_disk_rows([])
        with self.assertRaises(DiskCollectionError):
            ensure_disk_rows(None)
        rows = ensure_disk_rows({"DeviceId": "0"})
        self.assertEqual(len(rows), 1)

    def test_volume_payload_distinguishes_empty_from_failure(self) -> None:
        self.assertEqual(parse_volume_payload("[]"), [])
        with self.assertRaises(CapacityCollectionError):
            parse_volume_payload("")
        with self.assertRaises(CapacityCollectionError):
            parse_volume_payload("{not json")
        with self.assertRaises(CapacityCollectionError):
            parse_volume_payload("[]", returncode=1)

    def test_timeouts_have_their_own_messages(self) -> None:
        self.assertIn("タイムアウト", inventory_error_message(subprocess.TimeoutExpired("powershell", 45)))


class ScheduleAndPortTests(unittest.TestCase):
    def test_cancelled_startup_waits_before_the_daily_scan(self) -> None:
        self.assertEqual(
            classify_scan_outcome(
                phase="cancelled",
                health_running=False,
                health_error=False,
                has_result=True,
            ),
            "cancelled",
        )
        self.assertEqual(
            classify_scan_outcome(
                phase="error",
                health_running=False,
                health_error=True,
                has_result=False,
            ),
            "failed",
        )
        self.assertTrue(startup_should_delay_daily("cancelled"))
        self.assertFalse(startup_should_delay_daily("failed"))
        self.assertFalse(startup_should_delay_daily("ok"))

    def test_failed_startup_does_not_cover_the_daily_slot(self) -> None:
        self.assertFalse(startup_covers_daily(startup_succeeded=False, now_past_slot=True))
        self.assertTrue(startup_covers_daily(startup_succeeded=True, now_past_slot=True))
        self.assertFalse(startup_covers_daily(startup_succeeded=True, now_past_slot=False))

    def test_daily_retries_after_failure_instead_of_marking_the_day(self) -> None:
        self.assertTrue(
            daily_is_due(now_past_slot=True, covered_today=False, seconds_since_failure=None)
        )
        self.assertFalse(
            daily_is_due(now_past_slot=True, covered_today=True, seconds_since_failure=None)
        )
        self.assertFalse(
            daily_is_due(now_past_slot=True, covered_today=False, seconds_since_failure=30)
        )
        self.assertTrue(
            daily_is_due(
                now_past_slot=True,
                covered_today=False,
                seconds_since_failure=15 * 60,
            )
        )

    def test_listen_port_parsing_and_busy_port(self) -> None:
        self.assertEqual(parse_listen_port(None), 8787)
        self.assertEqual(parse_listen_port("nope"), 8787)
        self.assertEqual(parse_listen_port("0"), 8787)
        self.assertEqual(parse_listen_port("8791"), 8791)
        held = socket.socket()
        held.bind(("127.0.0.1", 0))
        port = held.getsockname()[1]
        try:
            self.assertFalse(port_is_free("127.0.0.1", port))
        finally:
            held.close()
        self.assertTrue(port_is_free("127.0.0.1", port))

    def test_space_map_interval_and_fixed_drives_only(self) -> None:
        now = datetime(2026, 11, 15, 12, 0, tzinfo=timezone.utc)
        self.assertTrue(space_map_due(None, 1, now=now, tz=timezone.utc))
        self.assertTrue(space_map_due(now.isoformat(), 0, now=now, tz=timezone.utc))
        recent = (now - timedelta(hours=2)).isoformat()
        self.assertFalse(space_map_due(recent, 1, now=now, tz=timezone.utc))
        # 前日の同時刻より少し前。24時間未満でも、日付が変わっていれば実施する。
        yesterday = datetime(2026, 11, 14, 9, 30, tzinfo=timezone.utc)
        morning = datetime(2026, 11, 15, 9, 0, tzinfo=timezone.utc)
        self.assertTrue(space_map_due(yesterday.isoformat(), 1, now=morning, tz=timezone.utc))
        self.assertFalse(
            space_map_due(
                datetime(2026, 11, 15, 8, 0, tzinfo=timezone.utc).isoformat(),
                1,
                now=morning,
                tz=timezone.utc,
            )
        )
        self.assertTrue(drive_type_included(3, fixed_only=True))
        self.assertFalse(drive_type_included(2, fixed_only=True))
        self.assertTrue(drive_type_included(2, fixed_only=False))
        self.assertFalse(drive_type_included(4, fixed_only=False))


class SpaceScanIsolationTests(unittest.TestCase):
    def test_manual_cancel_does_not_cancel_automatic_map(self) -> None:
        from app import space_scan

        space_scan._auto.cancelled = False
        space_scan._manual.cancelled = False
        space_scan.cancel_scan()
        self.assertFalse(space_scan._auto.cancelled)
        self.assertTrue(space_scan._manual.cancelled)
        space_scan.cancel_auto_scan()
        self.assertTrue(space_scan._auto.cancelled)
        space_scan._auto.cancelled = False
        space_scan._manual.cancelled = False

    def test_manual_start_refuses_drive_owned_by_automatic_scan(self) -> None:
        from app import space_scan

        with space_scan._auto.lock:
            space_scan._auto.running = True
            space_scan._auto.root_path = r"C:\\"
        try:
            result = space_scan.start_scan(r"C:\\")
            self.assertFalse(result["ok"])
            self.assertIn("自動", result["message"])
        finally:
            with space_scan._auto.lock:
                space_scan._auto.running = False
                space_scan._auto.root_path = None


if __name__ == "__main__":
    unittest.main()
