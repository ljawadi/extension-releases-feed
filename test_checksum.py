#!/usr/bin/env python3
"""
Checksum-Prüfung: GUI-Pfad (update_checker) und Daemon (auto_update_daemon)
müssen sich gleich verhalten -- beide fail-closed.

Aufruf:  python test_checksum.py
"""

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

import auto_update
import auto_update_daemon
import update_checker

REPO = Path(__file__).resolve().parent

# Daemon-Log nicht ins echte %APPDATA%\Alvaro\update.log schreiben
auto_update_daemon.log = lambda *a, **k: None


def _gui_ok(path, expected):
    try:
        return update_checker.verify_checksum(path, expected)
    except ValueError:
        return False


class ChecksumParity(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.file = Path(self.tmp.name) / "payload.bin"
        self.file.write_bytes(b"alvaro-update-payload")
        self.good = hashlib.sha256(b"alvaro-update-payload").hexdigest()

    def tearDown(self):
        self.tmp.cleanup()

    def test_placeholder_sets_identical(self):
        self.assertEqual(update_checker.PLACEHOLDER_CHECKSUMS,
                         auto_update_daemon.PLACEHOLDER_CHECKSUMS)

    def test_placeholders_rejected_in_both_paths(self):
        for value in ("", None, "placeholder", "PLACEHOLDER", "tbd", "none",
                      "sha256:", "sha256:placeholder", "  "):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    update_checker.verify_checksum(self.file, value)
                self.assertFalse(auto_update_daemon.verify_checksum(self.file, value))

    def test_placeholder_rejected_before_file_is_read(self):
        missing = Path(self.tmp.name) / "does-not-exist"
        with self.assertRaises(ValueError):
            update_checker.verify_checksum(missing, "placeholder")

    def test_mismatch_rejected_in_both_paths(self):
        wrong = "0" * 64
        with self.assertRaises(ValueError):
            update_checker.verify_checksum(self.file, wrong)
        self.assertFalse(auto_update_daemon.verify_checksum(self.file, wrong))

    def test_match_accepted_in_both_paths(self):
        for value in (self.good, "sha256:" + self.good, self.good.upper()):
            with self.subTest(value=value):
                self.assertTrue(update_checker.verify_checksum(self.file, value))
                self.assertTrue(auto_update_daemon.verify_checksum(self.file, value))

    def test_real_release_artifacts_against_real_feed(self):
        """Echte Daten: Feed-Checksums gegen die lokal gebauten Release-Dateien."""
        feed = json.loads((REPO / "release_feed.json").read_text(encoding="utf-8"))
        local = {"windows_exe": REPO / "dist" / "AlvaroInstaller.exe",
                 "python_script": REPO / "releases" / "installer-1.0.0.py"}
        downloads = feed["releases"][0]["downloads"]
        checked = 0
        for key, path in local.items():
            if not path.exists():
                continue
            expected = downloads[key]["checksum"]
            with self.subTest(key=key):
                self.assertEqual(_gui_ok(path, expected),
                                 auto_update_daemon.verify_checksum(path, expected))
            checked += 1
        if not checked:
            self.skipTest("keine lokalen Release-Dateien")


class CallerAbortsInstall(unittest.TestCase):
    """download_and_install muss bei Placeholder abbrechen und (False, msg) liefern."""

    def test_placeholder_aborts_without_relaunch(self):
        relaunched = []
        orig_dl = update_checker.download_file
        orig_relaunch = auto_update._relaunch_with_new_version
        orig_write = update_checker.write_local_version

        def fake_download(url, dest, **kw):
            Path(dest).write_bytes(b"evil")
            return dest

        update_checker.download_file = fake_download
        auto_update._relaunch_with_new_version = lambda p: relaunched.append(p) or (True, "ok")
        update_checker.write_local_version = lambda v: True
        try:
            result = auto_update.download_and_install(
                {"url": "https://example.invalid/AlvaroInstaller.exe",
                 "checksum": "placeholder"},
                "9.9.9")
        finally:
            update_checker.download_file = orig_dl
            auto_update._relaunch_with_new_version = orig_relaunch
            update_checker.write_local_version = orig_write

        ok, message = result  # Tupel-Vertrag des GUI-Workers
        self.assertFalse(ok)
        self.assertIn("placeholder", message)
        self.assertEqual(relaunched, [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
