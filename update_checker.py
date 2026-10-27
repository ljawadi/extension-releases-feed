#!/usr/bin/env python3
"""
Update-Checker für Alvaro Installer.
Prüft Release-Feed von Gitea, vergleicht Versionen, lädt Releases und
verifiziert deren Checksum.
"""

import json
import sys
import ssl
import hashlib
import urllib.request
import urllib.error
from pathlib import Path

try:
    from packaging import version as pkg_version
    _HAVE_PACKAGING = True
except Exception:  # packaging ist optional (z.B. im gebündelten .exe)
    _HAVE_PACKAGING = False

# Update-Feed URL (GitHub Raw)
FEED_URL = "https://raw.githubusercontent.com/ljawadi/extension-releases-feed/main/release_feed.json"

# Fallback-Version, falls version.txt fehlt
CURRENT_VERSION = "1.0.3"

# Pfad zur lokalen Versionsdatei (liegt neben diesem Skript / in der .exe)
def _base_dir():
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).parent

VERSION_FILE = _base_dir() / "version.txt"


# ---------------------------------------------------------------------------
# Versionsdatei (lokaler Fallback)
# ---------------------------------------------------------------------------

def read_local_version():
    """Lies die lokale Version aus version.txt, sonst CURRENT_VERSION."""
    try:
        text = VERSION_FILE.read_text(encoding="utf-8").strip()
        return text or CURRENT_VERSION
    except Exception:
        return CURRENT_VERSION


def write_local_version(version_str):
    """Schreibe die aktuelle Version nach version.txt (nach jedem Update)."""
    try:
        VERSION_FILE.write_text(str(version_str).strip() + "\n", encoding="utf-8")
        return True
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Versionsvergleich (mit Fallback ohne 'packaging')
# ---------------------------------------------------------------------------

def _parse_version_tuple(v):
    parts = []
    for chunk in str(v).strip().lstrip("vV").split("."):
        num = ""
        for ch in chunk:
            if ch.isdigit():
                num += ch
            else:
                break
        parts.append(int(num) if num else 0)
    return tuple(parts)


def version_is_newer(candidate, baseline):
    """True, wenn candidate eine höhere Version als baseline ist."""
    try:
        if _HAVE_PACKAGING:
            return pkg_version.parse(str(candidate)) > pkg_version.parse(str(baseline))
    except Exception:
        pass
    return _parse_version_tuple(candidate) > _parse_version_tuple(baseline)


# ---------------------------------------------------------------------------
# SSL-Kontext: immer mit Zertifikats- und Hostname-Pruefung
# ---------------------------------------------------------------------------

def _ssl_context(insecure=False):
    # Kein CERT_NONE-Pfad mehr: wer insecure anfordert, bekommt einen Fehler.
    if insecure:
        raise ValueError("TLS verification cannot be disabled for the update feed")
    return ssl.create_default_context()


def _urlopen(url, timeout=10, insecure=False):
    req = urllib.request.Request(url, headers={"User-Agent": "AlvaroInstaller"})
    return urllib.request.urlopen(req, timeout=timeout, context=_ssl_context(insecure))


# ---------------------------------------------------------------------------
# Feed laden / neueste Release bestimmen
# ---------------------------------------------------------------------------

def get_release_feed():
    """Lade Release-Feed (nur gueltiges HTTPS). None bei Fehler/offline."""
    try:
        with _urlopen(FEED_URL, timeout=8, insecure=False) as response:
            return json.loads(response.read().decode())
    except (urllib.error.URLError, ssl.SSLError) as e:
        print(f"[!] TLS-/Netzwerkfehler beim Feed-Abruf: {e}", file=sys.stderr)
        return None  # kein Fallback ohne Zertifikatspruefung
    except json.JSONDecodeError as e:
        print(f"[!] Release-Feed ist kein gueltiges JSON: {e}", file=sys.stderr)
        return None
    except Exception as e:
        print(f"[!] Feed-Abruf fehlgeschlagen: {e}", file=sys.stderr)
        return None


def get_latest_stable_release(feed):
    """Hole die neueste stabile, nicht-deprecatete Release."""
    if not feed or "releases" not in feed:
        return None

    stable = [
        r for r in feed["releases"]
        if r.get("channel") == "stable" and not r.get("deprecated", False)
    ]
    if not stable:
        return None

    try:
        if _HAVE_PACKAGING:
            stable.sort(key=lambda r: pkg_version.parse(r["version"]), reverse=True)
        else:
            stable.sort(key=lambda r: _parse_version_tuple(r["version"]), reverse=True)
    except Exception:
        pass
    return stable[0]


# ---------------------------------------------------------------------------
# Download + Checksum
# ---------------------------------------------------------------------------

def download_file(url, dest_path, progress_cb=None, allow_insecure_ssl=False,
                  chunk_size=65536, timeout=30):
    """
    Lädt url nach dest_path. progress_cb(fraction|None) für Fortschritt.
    Wirft eine Exception bei Fehler (der Aufrufer macht das Retry).

    Nur HTTPS mit gueltigem Zertifikat. allow_insecure_ssl bleibt nur fuer
    Signatur-Kompatibilitaet; True fuehrt zu ValueError statt CERT_NONE.
    """
    dest_path = Path(dest_path)
    dest_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        with _urlopen(url, timeout=timeout, insecure=allow_insecure_ssl) as resp:
            total = resp.headers.get("Content-Length")
            total = int(total) if total and total.isdigit() else None
            read = 0
            tmp = dest_path.with_suffix(dest_path.suffix + ".part")
            with open(tmp, "wb") as fh:
                while True:
                    chunk = resp.read(chunk_size)
                    if not chunk:
                        break
                    fh.write(chunk)
                    read += len(chunk)
                    if progress_cb:
                        progress_cb((read / total) if total else None)
            tmp.replace(dest_path)
        return dest_path
    except (ssl.SSLError, urllib.error.URLError) as e:
        print(f"[!] TLS-/Netzwerkfehler beim Download: {e}", file=sys.stderr)
        raise  # kein Fallback: nur HTTPS mit gueltigem Zertifikat


def _sha256_of_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


# Werte, die im Feed als "keine echte Prüfsumme" gelten. Muss mit
# auto_update_daemon.PLACEHOLDER_CHECKSUMS übereinstimmen (Daemon läuft
# eigenständig im Nutzer-Datenverzeichnis und kann dieses Modul nicht
# importieren); test_checksum.py prüft die Gleichheit.
PLACEHOLDER_CHECKSUMS = ("", "placeholder", "tbd", "none")


def verify_checksum(file_path, expected_checksum):
    """
    Prüft die SHA256-Checksum der Datei -- fail-closed (wie der Daemon).

    expected_checksum kann 'sha256:<hex>' oder '<hex>' sein.
    Returns True, wenn die Prüfsumme stimmt.

    Raises ValueError, wenn die Checksum fehlt, ein Platzhalter ist oder
    nicht übereinstimmt. Ohne gültige Prüfsumme wird NIE installiert.
    """
    raw = (expected_checksum or "").strip()
    if raw.lower().startswith("sha256:"):
        raw = raw.split(":", 1)[1].strip()

    if raw.lower() in PLACEHOLDER_CHECKSUMS:
        raise ValueError(f"Checksum missing or placeholder. File: {file_path}")

    actual = _sha256_of_file(file_path)
    if actual.lower() != raw.lower():
        raise ValueError(
            f"Checksum mismatch: expected {raw[:12]}..., got {actual[:12]}...")
    return True


# ---------------------------------------------------------------------------
# Standalone-Nutzung: nur anzeigen
# ---------------------------------------------------------------------------

def check_for_updates():
    """Hauptfunktion für CLI: prüfe auf Updates und zeige sie an."""
    feed = get_release_feed()
    if not feed:
        print("[!] Konnte Release-Feed nicht abrufen. Bitte manuell pruefen.")
        return False

    latest = get_latest_stable_release(feed)
    if not latest:
        print("[i] Keine Releases verfuegbar.")
        return False

    current = read_local_version()
    latest_version = latest["version"]

    if version_is_newer(latest_version, current):
        print(f"\nUPDATE VERFUEGBAR: {current} -> {latest_version}\n")
        print(f"Veroeffentlicht: {latest.get('releaseDate', 'unbekannt')}")
        print("Aenderungen:")
        for change in latest.get("changelog", []):
            print(f"   - {change}")
        return True

    print(f"[ok] Neueste Version ist installiert: {current}")
    return False


if __name__ == "__main__":
    has_update = check_for_updates()
    sys.exit(1 if has_update else 0)
