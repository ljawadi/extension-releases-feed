#!/usr/bin/env python3
"""
Auto-Update-Modul für den Alvaro Installer.

Kapselt die gesamte Auto-Update-Logik:
  * check_for_update()      -> prüft den Gitea-Release-Feed gegen die lokale Version
  * download_and_install()  -> lädt die passende Datei, verifiziert sie, startet sie neu
  * show_progress_dialog()  -> modale GUI mit Fortschrittsbalken

Design-Prinzipien:
  * Netzwerk/Checks laufen im Hintergrund-Thread, GUI bleibt responsiv.
  * Jede Operation failed graceful: Gitea offline, Download kaputt, Checksum
    falsch -> der Installer läuft normal weiter (mit Hinweis), nichts crasht.
  * tkinter ist NICHT thread-safe: alle GUI-Aktionen werden über root.after()
    in den Main-Thread marshallt.
"""

import os
import sys
import ssl
import platform
import subprocess
import tempfile
import urllib.request
import urllib.error
from pathlib import Path

import update_checker


# ---------------------------------------------------------------------------
# Plattform-Erkennung
# ---------------------------------------------------------------------------

def current_platform_key():
    """Mappe die laufende Plattform auf den Schlüssel im Release-Feed."""
    system = platform.system()
    if system == "Windows":
        return "windows_exe"
    if system == "Darwin":
        machine = platform.machine().lower()
        if machine in ("arm64", "aarch64"):
            return "mac_arm64"
        return "mac_intel"
    # Linux / Fallback: das plattformunabhängige Python-Skript
    return "python_script"


def _running_as_frozen():
    """True, wenn als PyInstaller-.exe gebündelt (dann gibt es keine .py)."""
    return getattr(sys, "frozen", False)


# ---------------------------------------------------------------------------
# Schritt 1: Prüfen
# ---------------------------------------------------------------------------

def check_for_update():
    """
    Prüft den Feed und vergleicht mit der lokalen Version.

    Returns
    -------
    dict | None
        None  -> kein Update / Feed nicht erreichbar (siehe 'reason').
        dict  -> {
            'available': bool,
            'current':   str,
            'latest':    str,
            'changelog': list[str],
            'release_date': str,
            'download':  dict | None,   # Download-Info für diese Plattform
            'reason':    str,           # 'ok' | 'offline' | 'no_releases' | 'up_to_date'
        }
    """
    current = update_checker.read_local_version()

    feed = update_checker.get_release_feed()
    if not feed:
        return {
            "available": False,
            "current": current,
            "latest": current,
            "changelog": [],
            "release_date": "",
            "download": None,
            "reason": "offline",
        }

    latest = update_checker.get_latest_stable_release(feed)
    if not latest:
        return {
            "available": False,
            "current": current,
            "latest": current,
            "changelog": [],
            "release_date": "",
            "download": None,
            "reason": "no_releases",
        }

    latest_version = latest.get("version", current)
    is_newer = update_checker.version_is_newer(latest_version, current)

    plat_key = current_platform_key()
    download = (latest.get("downloads") or {}).get(plat_key)

    return {
        "available": bool(is_newer and download),
        "current": current,
        "latest": latest_version,
        "changelog": latest.get("changelog", []),
        "release_date": latest.get("releaseDate", ""),
        "download": download,
        "reason": "ok" if is_newer else "up_to_date",
    }


# ---------------------------------------------------------------------------
# Schritt 2+3: Download + Installation
# ---------------------------------------------------------------------------

def download_and_install(download_info, latest_version, progress_cb=None,
                         status_cb=None, allow_insecure_ssl=True):
    """
    Lädt die neue Version, verifiziert die Checksum und startet sie neu.

    progress_cb(fraction: float)  -> 0.0 .. 1.0 (oder None bei unbekannter Größe)
    status_cb(text: str)          -> Text-Status für die GUI

    Returns (ok: bool, message: str). Bei ok=True wurde der Neustart angestoßen;
    der Aufrufer soll die alte Instanz danach beenden.
    """
    def _status(msg):
        if status_cb:
            status_cb(msg)

    url = download_info.get("url")
    expected_checksum = download_info.get("checksum", "")
    if not url:
        return False, "Keine Download-URL im Feed."

    # Zielpfad im Temp-Verzeichnis, Dateiname aus der URL ableiten
    suffix = Path(url.split("?")[0]).suffix
    tmp_dir = Path(tempfile.gettempdir()) / "alvaro_update"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    dest = tmp_dir / f"AlvaroInstaller-{latest_version}{suffix or '.exe'}"

    # --- Download mit Retry (3x) ---
    last_error = ""
    for attempt in range(1, 4):
        try:
            _status(f"Lade Update {latest_version} ... (Versuch {attempt}/3)")
            update_checker.download_file(
                url, dest,
                progress_cb=progress_cb,
                allow_insecure_ssl=allow_insecure_ssl,
            )
            last_error = ""
            break
        except Exception as e:  # noqa: BLE001 - alles graceful abfangen
            last_error = str(e)
            _status(f"Download fehlgeschlagen (Versuch {attempt}/3): {e}")
    if last_error:
        _safe_unlink(dest)
        return False, f"Download nach 3 Versuchen fehlgeschlagen: {last_error}"

    # --- Checksum verifizieren ---
    _status("Verifiziere Checksum ...")
    ok, detail = update_checker.verify_checksum(dest, expected_checksum)
    if not ok:
        _safe_unlink(dest)
        return False, f"Checksum-Prüfung fehlgeschlagen: {detail}"
    _status(f"Checksum ok ({detail}).")

    # --- Neustart mit neuer Version ---
    _status("Starte neue Version ...")
    started, msg = _relaunch_with_new_version(dest)
    if not started:
        return False, msg

    # version.txt lokal aktualisieren, damit der Nächste-Check konsistent ist
    update_checker.write_local_version(latest_version)

    return True, f"Update {latest_version} gestartet."


def _relaunch_with_new_version(new_path):
    """Startet die heruntergeladene Datei (ggf. mit Admin-Rechten) neu."""
    new_path = str(new_path)
    system = platform.system()
    try:
        if system == "Windows":
            if new_path.lower().endswith(".exe"):
                # Mit Admin-Rechten starten (UAC-Prompt), damit die neue
                # Version Zertifikat/hosts schreiben darf und die alte ersetzt.
                import ctypes
                ctypes.windll.shell32.ShellExecuteW(
                    None, "runas", new_path, "", None, 1
                )
            else:
                # Python-Skript: mit aktuellem Interpreter starten
                subprocess.Popen([sys.executable, new_path])
        elif system == "Darwin":
            if new_path.endswith(".dmg"):
                subprocess.Popen(["open", new_path])
            else:
                subprocess.Popen([sys.executable, new_path])
        else:
            subprocess.Popen([sys.executable, new_path])
        return True, "ok"
    except Exception as e:  # noqa: BLE001
        return False, f"Neustart fehlgeschlagen: {e}"


def _safe_unlink(path):
    try:
        Path(path).unlink(missing_ok=True)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Schritt: GUI-Fortschrittsdialog
# ---------------------------------------------------------------------------

def show_progress_dialog(parent, title="Update wird installiert"):
    """
    Erzeugt einen modalen Fortschrittsdialog.

    Returns ein Objekt mit:
      .set_progress(fraction|None)   float 0..1, None = unbestimmt (marquee)
      .set_status(text)
      .close()
    Alle Methoden sind über root.after() thread-safe aufrufbar.
    """
    import tkinter as tk
    from tkinter import ttk

    win = tk.Toplevel(parent)
    win.title(title)
    win.geometry("420x160")
    win.resizable(False, False)
    win.configure(bg="#f5f5f5")
    win.transient(parent)
    win.grab_set()  # modal: kein User-Input im Hauptfenster während Update

    tk.Label(win, text=title, font=("Arial", 13, "bold"),
             bg="#f5f5f5").pack(pady=(18, 6))

    status_var = tk.StringVar(value="Starte ...")
    tk.Label(win, textvariable=status_var, font=("Arial", 10),
             bg="#f5f5f5", fg="#555", wraplength=380).pack(pady=4)

    bar = ttk.Progressbar(win, mode="indeterminate", length=360)
    bar.pack(pady=12)
    bar.start(12)

    # Schließen über das Fensterkreuz während des Downloads unterbinden
    win.protocol("WM_DELETE_WINDOW", lambda: None)

    state = {"mode": "indeterminate"}

    class _Handle:
        def set_progress(self, fraction):
            def _apply():
                if fraction is None:
                    if state["mode"] != "indeterminate":
                        bar.config(mode="indeterminate")
                        bar.start(12)
                        state["mode"] = "indeterminate"
                else:
                    if state["mode"] != "determinate":
                        bar.stop()
                        bar.config(mode="determinate", maximum=100)
                        state["mode"] = "determinate"
                    bar["value"] = max(0, min(100, fraction * 100))
            parent.after(0, _apply)

        def set_status(self, text):
            parent.after(0, lambda: status_var.set(text))

        def close(self):
            def _close():
                try:
                    bar.stop()
                    win.grab_release()
                    win.destroy()
                except Exception:
                    pass
            parent.after(0, _close)

    return _Handle()
