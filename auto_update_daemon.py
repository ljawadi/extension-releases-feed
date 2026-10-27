#!/usr/bin/env python3
"""
Alvaro Auto-Update Daemon  --  TRANSPARENTER Hintergrund-Updater.

Design-Prinzip (bewusst NICHT silent):
  1. Ein geplanter Hintergrund-Lauf (Task Scheduler / launchd / cron) prueft
     einmal taeglich den Gitea-Release-Feed.
  2. Gibt es eine neuere Version, erscheint eine sichtbare Benachrichtigung
     ("Update verfuegbar"). Es wird NICHTS installiert, solange der Nutzer
     nicht aktiv "Jetzt updaten" klickt.
  3. Erst nach Klick: Download -> SHA256-Verify -> Backup -> Austausch.
     Schlaegt irgendein Schritt fehl, wird automatisch zurueckgerollt.
  4. Laeuft der Check auf einem Rechner ohne Desktop/Display (headless),
     wird NICHT still installiert -- es wird nur ins Log geschrieben, dass
     ein Update bereitliegt. Installation braucht immer eine Person am Bildschirm.

Logging: %APPDATA%\\Alvaro\\update.log (Windows) bzw. ~/.local/state/Alvaro/update.log.
Es werden bewusst keine Tokens, Header-Werte oder Secrets geloggt.

Aufruf:
  python auto_update_daemon.py              # geplanter Lauf: pruefen + ggf. fragen
  python auto_update_daemon.py --check-only # nur pruefen, nie installieren (Exit 10 = Update da)
  python auto_update_daemon.py --yes        # Update anwenden ohne Dialog (nur fuer bewusste CLI-Nutzung)
  python auto_update_daemon.py --insecure   # self-signed Gitea-Zertifikat akzeptieren
"""

import argparse
import hashlib
import json
import os
import platform
import shutil
import ssl
import sys
import tempfile
import time
import urllib.request
import urllib.error
from datetime import datetime
from pathlib import Path

# --------------------------------------------------------------------------
# Konfiguration
# --------------------------------------------------------------------------
FEED_URL = (
    "https://gitea.thedoomsdayproject.ignorelist.com:3000/"
    "ljawadi/alvaro-releases/raw/branch/main/release_feed.json"
)
CURRENT_VERSION = "1.0.0"
APP_NAME = "Alvaro"
NETWORK_TIMEOUT = 15


# --------------------------------------------------------------------------
# Pfade (plattformabhaengig)
# --------------------------------------------------------------------------
def data_dir() -> Path:
    """Verzeichnis fuer Log, Backups und Downloads -- pro Nutzer, kein Admin noetig."""
    system = platform.system()
    if system == "Windows":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    elif system == "Darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local" / "state"))
    d = base / APP_NAME
    d.mkdir(parents=True, exist_ok=True)
    return d


def log_path() -> Path:
    return data_dir() / "update.log"


def install_target() -> Path:
    """
    Die Datei, die ersetzt wird. Standard: die aktuell laufende Installation.
    Ueberschreibbar per ALVARO_INSTALL_TARGET fuer Tests.
    """
    override = os.environ.get("ALVARO_INSTALL_TARGET")
    if override:
        return Path(override)
    # Als eingefrorene .exe ist sys.executable die Installation selbst.
    if getattr(sys, "frozen", False):
        return Path(sys.executable)
    # Als Skript: die installer.py neben dem Daemon.
    return Path(__file__).resolve().parent / "installer.py"


# --------------------------------------------------------------------------
# Logging (ohne Secrets)
# --------------------------------------------------------------------------
def log(message: str, level: str = "INFO") -> None:
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    line = f"[{stamp}] {level}: {message}"
    try:
        with log_path().open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except OSError:
        pass
    print(line)


# --------------------------------------------------------------------------
# Feed laden & Version vergleichen
# --------------------------------------------------------------------------
def _ssl_context(insecure: bool):
    if not insecure:
        return None
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


def fetch_feed(insecure: bool):
    try:
        ctx = _ssl_context(insecure)
        with urllib.request.urlopen(FEED_URL, timeout=NETWORK_TIMEOUT, context=ctx) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, json.JSONDecodeError, ssl.SSLError, OSError) as exc:
        log(f"Feed nicht erreichbar -- naechster Versuch morgen ({type(exc).__name__})", "WARN")
        return None


def _version_tuple(v: str):
    parts = []
    for chunk in str(v).split("."):
        num = "".join(ch for ch in chunk if ch.isdigit())
        parts.append(int(num) if num else 0)
    return tuple(parts)


def latest_stable(feed):
    if not feed or "releases" not in feed:
        return None
    stable = [
        r for r in feed["releases"]
        if r.get("channel") == "stable" and not r.get("deprecated", False)
    ]
    if not stable:
        return None
    stable.sort(key=lambda r: _version_tuple(r.get("version", "0")), reverse=True)
    return stable[0]


def find_update(insecure: bool):
    """Gibt das Release-Dict zurueck, wenn eine neuere Version existiert, sonst None."""
    feed = fetch_feed(insecure)
    if not feed:
        return None
    latest = latest_stable(feed)
    if not latest:
        log("Keine stabilen Releases im Feed.")
        return None
    newest = latest.get("version", "0")
    if _version_tuple(newest) > _version_tuple(CURRENT_VERSION):
        log(f"Update gefunden: {CURRENT_VERSION} -> {newest} -- warte auf Nutzer-Bestaetigung")
        return latest
    log(f"Aktuell -- {CURRENT_VERSION} ist die neueste Version")
    return None


# --------------------------------------------------------------------------
# Sichtbare Nachfrage (transparent)
# --------------------------------------------------------------------------
def platform_for_feed() -> str:
    system = platform.system()
    if system == "Windows":
        return "windows_exe"
    if system == "Darwin":
        return "mac_arm64" if platform.machine().lower() in ("arm64", "aarch64") else "mac_intel"
    return "python_script"


def ask_user(release) -> bool:
    """
    Zeigt einen sichtbaren Dialog. True nur, wenn der Nutzer "Jetzt updaten" klickt.
    Ohne Display (headless) -> False, es wird nur geloggt. Niemals stilles Ja.
    """
    version = release.get("version", "?")
    changes = release.get("changelog", [])
    changelist = "\n".join(f"  - {c}" for c in changes) if changes else "  (keine Details)"
    message = (
        f"Eine neue Version von {APP_NAME} ist verfuegbar.\n\n"
        f"Aktuell: {CURRENT_VERSION}\nNeu: {version}\n\n"
        f"Aenderungen:\n{changelist}\n\n"
        f"Jetzt herunterladen und installieren?"
    )
    try:
        import tkinter as tk
        from tkinter import messagebox
        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        answer = messagebox.askyesno(f"{APP_NAME} Update verfuegbar", message)
        root.destroy()
        log(f"Nutzer-Entscheidung zum Update {version}: {'JA' if answer else 'NEIN'}")
        return bool(answer)
    except Exception as exc:
        log(f"Kein Dialog moeglich (headless?) -- Update {version} liegt bereit, "
            f"nicht installiert ({type(exc).__name__})", "WARN")
        return False


# --------------------------------------------------------------------------
# Download / Verify / Backup / Install / Rollback
# --------------------------------------------------------------------------
def download(url: str, dest: Path, insecure: bool) -> bool:
    try:
        log(f"Lade herunter: {url.rsplit('/', 1)[-1]}")
        ctx = _ssl_context(insecure)
        with urllib.request.urlopen(url, timeout=NETWORK_TIMEOUT, context=ctx) as resp, \
                dest.open("wb") as out:
            shutil.copyfileobj(resp, out)
        log(f"Download fertig ({dest.stat().st_size} Bytes)")
        return True
    except (urllib.error.URLError, ssl.SSLError, OSError) as exc:
        log(f"Download fehlgeschlagen -- morgen erneut ({type(exc).__name__})", "ERROR")
        return False


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(65536), b""):
            h.update(block)
    return h.hexdigest()


def verify_checksum(path: Path, expected: str) -> bool:
    expected = (expected or "").split(":", 1)[-1].strip().lower()
    if not expected or expected == "placeholder":
        log("Kein gueltiger SHA256 im Feed -- Update abgebrochen (Sicherheit)", "ERROR")
        return False
    actual = sha256(path).lower()
    if actual == expected:
        log("SHA256 verifiziert")
        return True
    log(f"SHA256-MISMATCH -- erwartet {expected[:12]}..., war {actual[:12]}... Abbruch", "ERROR")
    return False


def backup(target: Path) -> Path | None:
    if not target.exists():
        log(f"Kein Installationsziel zum Sichern: {target}", "WARN")
        return None
    bdir = data_dir() / "backups"
    bdir.mkdir(exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    dest = bdir / f"{target.name}.{CURRENT_VERSION}.{stamp}.bak"
    shutil.copy2(target, dest)
    log(f"Backup angelegt: {dest.name}")
    return dest


def install(new_file: Path, target: Path, backup_file: Path | None) -> bool:
    """Atomarer Austausch mit automatischem Rollback bei Fehler."""
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp = target.with_suffix(target.suffix + ".new")
        shutil.copy2(new_file, tmp)
        os.replace(tmp, target)  # atomar auf gleichem Volume
        log(f"Installiert -> {target}")
        return True
    except OSError as exc:
        log(f"Installation fehlgeschlagen: {type(exc).__name__} -- starte Rollback", "ERROR")
        return rollback(target, backup_file)


def rollback(target: Path, backup_file: Path | None) -> bool:
    if not backup_file or not backup_file.exists():
        log("Kein Backup fuer Rollback vorhanden", "ERROR")
        return False
    try:
        shutil.copy2(backup_file, target)
        log(f"Rollback erfolgreich aus {backup_file.name}")
    except OSError as exc:
        log(f"Rollback FEHLGESCHLAGEN: {type(exc).__name__}", "ERROR")
        return False
    return False  # Rollback heisst: Update nicht angewendet


def apply_update(release, insecure: bool) -> bool:
    key = platform_for_feed()
    dl = release.get("downloads", {}).get(key)
    if not dl or not dl.get("url"):
        log(f"Kein Download fuer Plattform '{key}' im Feed", "ERROR")
        return False

    workdir = Path(tempfile.mkdtemp(prefix="alvaro_update_"))
    try:
        local = workdir / Path(dl["url"]).name
        if not download(dl["url"], local, insecure):
            return False
        if not verify_checksum(local, dl.get("checksum", "")):
            return False
        target = install_target()
        bak = backup(target)
        ok = install(local, target, bak)
        if ok:
            log(f"Update auf {release.get('version')} abgeschlossen. "
                f"Neue Version wird beim naechsten Start aktiv.")
        return ok
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


# --------------------------------------------------------------------------
# Ablauf
# --------------------------------------------------------------------------
def run(check_only: bool, assume_yes: bool, insecure: bool) -> int:
    log("--- Update-Lauf gestartet ---")
    release = find_update(insecure)
    if not release:
        return 0
    if check_only:
        log("--check-only: Update vorhanden, nichts installiert")
        return 10
    proceed = True if assume_yes else ask_user(release)
    if not proceed:
        log("Update verschoben (Nutzer oder headless). Erneuter Hinweis beim naechsten Lauf.")
        return 0
    ok = apply_update(release, insecure)
    return 0 if ok else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Alvaro transparenter Auto-Updater")
    parser.add_argument("--check-only", action="store_true",
                        help="nur pruefen, nie installieren (Exit 10 = Update verfuegbar)")
    parser.add_argument("--yes", action="store_true",
                        help="ohne Dialog anwenden (bewusste CLI-Nutzung)")
    parser.add_argument("--insecure", action="store_true",
                        help="self-signed Gitea-Zertifikat akzeptieren")
    args = parser.parse_args()
    try:
        return run(args.check_only, args.yes, args.insecure)
    except Exception as exc:  # nie crashen -- morgen laeuft es wieder
        log(f"Unerwarteter Fehler: {type(exc).__name__}: {exc}", "ERROR")
        return 1


if __name__ == "__main__":
    sys.exit(main())
