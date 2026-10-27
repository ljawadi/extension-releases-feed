#!/usr/bin/env python3
"""
One-Click Installer für Alvaro ↔ Teamnanagement Proxy
Grafische Browser-Auswahl, alles automatisch
"""

import os
import sys
import platform
import subprocess
import threading
import webbrowser
import ctypes
import shutil
import stat
from pathlib import Path

APP_NAME = "Alvaro"
AUTO_UPDATE_TASK = "AlvaroAutoUpdate"


def appdata_dir():
    """Pro-Nutzer-Verzeichnis fuer Daemon, Log und Backups (kein Admin noetig)."""
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

try:
    import tkinter as tk
    from tkinter import ttk, messagebox
except ImportError:
    print("❌ tkinter nicht verfügbar. Installation fehlgeschlagen.")
    sys.exit(1)

# Eigenes Verzeichnis auf den Importpfad legen (Skript- und .exe-Modus),
# damit die Update-Module gefunden werden.
_BASE_DIR = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
if str(_BASE_DIR) not in sys.path:
    sys.path.insert(0, str(_BASE_DIR))

# Auto-Update ist optional: fehlt das Modul (z.B. Alt-Build), läuft der
# Installer trotzdem normal weiter.
try:
    import auto_update
    import update_checker
    _AUTO_UPDATE_AVAILABLE = True
except Exception as _e:  # noqa: BLE001
    auto_update = None
    update_checker = None
    _AUTO_UPDATE_AVAILABLE = False

def is_admin():
    """Prüfe ob Admin-Rechte vorhanden sind (Windows)."""
    if platform.system() != "Windows":
        return True
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False

def request_admin():
    """Starte Skript mit Admin-Rechten neu (Windows)."""
    if platform.system() == "Windows" and not is_admin():
        try:
            ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, " ".join(sys.argv), None, 1)
            sys.exit()
        except:
            pass

class AlvaroInstaller:
    def __init__(self, root):
        self.root = root
        self.root.title("Alvaro ↔ Teamnanagement Installer")
        self.root.geometry("500x400")
        self.root.resizable(False, False)
        self.system = platform.system()
        self.proxy_process = None
        self._update_in_progress = False

        # Farben
        self.root.configure(bg="#f5f5f5")

        # Header
        header = tk.Label(root, text="Alvaro Setup Wizard", font=("Arial", 16, "bold"), bg="#f5f5f5")
        header.pack(pady=20)

        # Browser-Auswahl
        frame = tk.Frame(root, bg="#f5f5f5")
        frame.pack(padx=20, pady=10)

        tk.Label(frame, text="Wähle deinen Browser:", font=("Arial", 11), bg="#f5f5f5").pack(anchor="w")

        self.browser_var = tk.StringVar(value="Chrome")
        browsers = self._detect_browsers()

        for browser in browsers:
            tk.Radiobutton(frame, text=browser, variable=self.browser_var, value=browser,
                          font=("Arial", 10), bg="#f5f5f5").pack(anchor="w", pady=5)

        # Status-Text
        self.status_label = tk.Label(root, text="Bereit zum Installieren", font=("Arial", 10), bg="#f5f5f5", fg="#666")
        self.status_label.pack(pady=20)

        # Progress-Bar
        self.progress = ttk.Progressbar(root, mode='indeterminate', length=400)
        self.progress.pack(padx=20, pady=10)

        # Buttons
        button_frame = tk.Frame(root, bg="#f5f5f5")
        button_frame.pack(pady=20)

        tk.Button(button_frame, text="Installieren", command=self.install,
                 font=("Arial", 11, "bold"), bg="#2563eb", fg="white", padx=20, pady=10).pack(side="left", padx=5)
        tk.Button(button_frame, text="Abbrechen", command=root.quit,
                 font=("Arial", 11), bg="#ccc", padx=20, pady=10).pack(side="left", padx=5)

        # Versions-Fußzeile
        self._local_version = (
            update_checker.read_local_version() if _AUTO_UPDATE_AVAILABLE else "?"
        )
        self.version_label = tk.Label(
            root, text=f"Version {self._local_version}",
            font=("Arial", 8), bg="#f5f5f5", fg="#999")
        self.version_label.pack(side="bottom", pady=4)

        # Auto-Update-Check im Hintergrund starten (blockiert die GUI nicht).
        if _AUTO_UPDATE_AVAILABLE:
            self.root.after(300, self.check_and_install_update)

    # ------------------------------------------------------------------
    # Auto-Update
    # ------------------------------------------------------------------

    def check_and_install_update(self):
        """Startet den Update-Check in einem Hintergrund-Thread."""
        if not _AUTO_UPDATE_AVAILABLE or self._update_in_progress:
            return
        threading.Thread(target=self._update_check_worker, daemon=True).start()

    def _update_check_worker(self):
        """Netzwerk-Check (Hintergrund). Ergebnis geht via after() zur GUI."""
        try:
            result = auto_update.check_for_update()
        except Exception as e:  # noqa: BLE001 - nie crashen
            result = {"available": False, "reason": "offline", "error": str(e)}
        self.root.after(0, lambda: self._on_update_check_done(result))

    def _on_update_check_done(self, result):
        """Läuft im Main-Thread: entscheidet, ob der Dialog erscheint."""
        if not result:
            return

        reason = result.get("reason")
        if reason == "offline":
            # Gitea offline -> trotzdem starten, nur dezent warnen.
            self.update_status("⚠️  Update-Server nicht erreichbar – fahre offline fort.")
            return
        if not result.get("available"):
            # Aktuell oder keine passende Datei -> still weiter.
            return

        self._prompt_update(result)

    def _prompt_update(self, result):
        """Modaler Dialog: 'Update verfügbar – jetzt installieren?'"""
        current = result["current"]
        latest = result["latest"]
        changelog = result.get("changelog", []) or []

        changes = "\n".join(f"  • {c}" for c in changelog[:8]) or "  (keine Details)"
        msg = (
            f"Ein Update ist verfügbar:\n\n"
            f"    {current}  →  {latest}\n\n"
            f"Änderungen:\n{changes}\n\n"
            f"Jetzt herunterladen und installieren?"
        )
        do_update = messagebox.askyesno("Update verfügbar", msg, icon="info")
        if not do_update:
            # 'Später': Installer läuft normal weiter, warnt beim nächsten Start wieder.
            self.update_status(f"Update {latest} verfügbar – später über Neustart.")
            return

        self._start_update_download(result)

    def _start_update_download(self, result):
        """Öffnet den Progress-Dialog und lädt im Hintergrund herunter."""
        self._update_in_progress = True
        download_info = result["download"]
        latest = result["latest"]

        dialog = auto_update.show_progress_dialog(
            self.root, title=f"Update {latest} wird installiert")

        def worker():
            ok, message = auto_update.download_and_install(
                download_info, latest,
                progress_cb=dialog.set_progress,
                status_cb=dialog.set_status,
            )
            self.root.after(0, lambda: self._on_update_finished(dialog, ok, message, latest))

        threading.Thread(target=worker, daemon=True).start()

    def _on_update_finished(self, dialog, ok, message, latest):
        """Main-Thread: Ergebnis des Downloads/Installs auswerten."""
        dialog.close()
        self._update_in_progress = False

        if ok:
            # Neue Version läuft bereits -> alte Instanz beenden.
            messagebox.showinfo(
                "Update gestartet",
                f"Version {latest} wurde gestartet.\n"
                f"Dieser Installer wird jetzt beendet.")
            self.root.quit()
            self.root.destroy()
        else:
            # Alles graceful: Fehler zeigen, dann normal weiterlaufen.
            messagebox.showerror(
                "Update fehlgeschlagen",
                f"{message}\n\nDer Installer läuft mit der aktuellen Version weiter.")
            self.update_status(f"❌ Update fehlgeschlagen – fahre mit {self._local_version} fort.")

    def _detect_browsers(self):
        """Erkenne verfügbare Browser."""
        available = []

        if self.system == "Windows":
            paths = {
                "Chrome": r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                "Edge": r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
                "Opera": r"C:\Program Files\Opera\opera.exe",
                "Firefox": r"C:\Program Files\Mozilla Firefox\firefox.exe",
            }
        elif self.system == "Darwin":  # Mac
            paths = {
                "Chrome": "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
                "Edge": "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
                "Firefox": "/Applications/Firefox.app/Contents/MacOS/firefox",
                "Safari": "/Applications/Safari.app/Contents/MacOS/Safari",
                "Opera": "/Applications/Opera.app/Contents/MacOS/Opera",
            }
        else:  # Linux
            paths = {
                "Chrome": "/usr/bin/google-chrome",
                "Chromium": "/usr/bin/chromium-browser",
                "Firefox": "/usr/bin/firefox",
                "Opera": "/usr/bin/opera",
                "Edge": "/usr/bin/microsoft-edge",
            }

        for name, path in paths.items():
            if Path(path).exists():
                available.append(name)

        return available if available else ["Chrome", "Firefox"]

    def update_status(self, text):
        """Aktualisiere Status-Text."""
        self.status_label.config(text=text)
        self.root.update()

    def install(self):
        """Starte Installation im Hintergrund."""
        self.progress.start()
        self.root.update_idletasks()

        thread = threading.Thread(target=self._run_installation, daemon=True)
        thread.start()

    def _run_installation(self):
        """Installationslogik."""
        try:
            self.update_status("Konfiguriere hosts-Datei...")
            self._setup_hosts()

            self.update_status("Importiere Zertifikat...")
            self._import_certificate()

            self.update_status("Starte Proxy-Server...")
            self._start_proxy()

            self.update_status("Richte automatische Updates ein...")
            try:
                register_auto_update_service()
                self.update_status("✓ Auto-Updates aktiviert (transparent, mit Nachfrage)")
            except Exception as e:
                # Updater ist optional -- Installation soll daran nicht scheitern
                self.update_status(f"⚠ Auto-Update-Setup uebersprungen: {e}")

            self.update_status("Öffne Browser...")
            self._open_browser()

            self.progress.stop()
            self.update_status("✓ Installation abgeschlossen!")
            messagebox.showinfo(
                "Erfolg",
                "Alvaro ist jetzt unter\n"
                "https://teamnanagement.horbach-center-stuttgart.de\nerreichbar!\n\n"
                "Automatische Updates sind aktiv: Alvaro prueft taeglich auf neue\n"
                "Versionen und FRAGT dich, bevor etwas installiert wird."
            )

        except Exception as e:
            self.progress.stop()
            self.update_status(f"❌ Fehler: {str(e)}")
            messagebox.showerror("Fehler", f"Installation fehlgeschlagen:\n{str(e)}")

    def _setup_hosts(self):
        """Bearbeite hosts-Datei."""
        if self.system == "Windows":
            hosts_file = Path("C:\\Windows\\System32\\drivers\\etc\\hosts")
        else:
            hosts_file = Path("/etc/hosts")

        entry = "127.0.0.1\tteamnanagement.horbach-center-stuttgart.de"

        try:
            content = hosts_file.read_text()
            if "teamnanagement" in content:
                return  # Bereits vorhanden
        except:
            pass

        if self.system == "Windows":
            cmd = f'powershell -Command "Add-Content \'{hosts_file}\' \'{entry}\'"'
            subprocess.run(cmd, shell=True, check=True)
        else:
            cmd = f'echo "{entry}" | sudo tee -a {hosts_file}'
            subprocess.run(cmd, shell=True, check=True)

    def _import_certificate(self):
        """Importiere Zertifikat in den Browser."""
        cert_file = Path(__file__).parent / "certs" / "cert-typo.pem"

        if not cert_file.exists():
            raise Exception(f"Zertifikat nicht gefunden: {cert_file}")

        browser = self.browser_var.get()

        if self.system == "Windows":
            # Zertifikat in Windows-Store importieren (betrifft alle Browser)
            cmd = f'certutil -addstore "Root" "{cert_file}"'
            subprocess.run(cmd, shell=True, check=True)
        elif self.system == "Darwin" and browser == "Safari":
            # Mac Safari
            cmd = f'security add-trusted-cert -d -r trustRoot -k /Library/Keychains/System.keychain "{cert_file}"'
            subprocess.run(cmd, shell=True, check=True)
        elif self.system == "Darwin":
            # Mac andere Browser
            cmd = f'security add-trusted-cert -d -r trustRoot -k ~/Library/Keychains/login.keychain "{cert_file}"'
            subprocess.run(cmd, shell=True, check=True)
        # Linux: Zertifikat ist selbstsigniert, Browser werden es trotzdem akzeptieren

    def _start_proxy(self):
        """Starte Proxy-Server."""
        proxy_file = Path(__file__).parent / "proxy_server.py"

        if not proxy_file.exists():
            raise Exception(f"Proxy nicht gefunden: {proxy_file}")

        if self.system == "Windows":
            self.proxy_process = subprocess.Popen(
                ["python", str(proxy_file)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
        else:
            self.proxy_process = subprocess.Popen(
                ["python3", str(proxy_file)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )

        # Warte kurz, bis Proxy läuft
        import time
        time.sleep(2)

    def _open_browser(self):
        """Öffne den Browser mit der Alvaro-Seite."""
        browser = self.browser_var.get()
        url = "https://teamnanagement.horbach-center-stuttgart.de/crm/dashboard"

        if self.system == "Windows":
            if browser == "Chrome":
                subprocess.Popen([r"C:\Program Files\Google\Chrome\Application\chrome.exe", url])
            elif browser == "Edge":
                subprocess.Popen([r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe", url])
            elif browser == "Firefox":
                subprocess.Popen([r"C:\Program Files\Mozilla Firefox\firefox.exe", url])
            elif browser == "Opera":
                subprocess.Popen([r"C:\Program Files\Opera\opera.exe", url])
        elif self.system == "Darwin":
            subprocess.Popen(["open", "-a", browser, url])
        else:  # Linux
            webbrowser.open(url)

# ==========================================================================
# Transparenter Auto-Update-Service
# ==========================================================================
# Der geplante Task fuehrt einmal taeglich (3 Uhr) auto_update_daemon.py aus.
# Der Daemon PRUEFT nur und zeigt bei einem Update eine sichtbare Nachfrage --
# installiert wird erst nach Klick des Nutzers. Kein Silent-Modus.

def _deploy_daemon():
    """Kopiere auto_update_daemon.py neben den Installer ins Nutzer-Datenverzeichnis."""
    src = Path(__file__).resolve().parent / "auto_update_daemon.py"
    if not src.exists():
        raise FileNotFoundError("auto_update_daemon.py nicht gefunden")
    dst = appdata_dir() / "auto_update_daemon.py"
    shutil.copy2(src, dst)
    return dst


def register_auto_update_service():
    """Registriere den taeglichen Update-Check je nach Betriebssystem."""
    system = platform.system()
    daemon = _deploy_daemon()
    py = sys.executable or "python"

    if system == "Windows":
        _register_windows_task(py, daemon)
    elif system == "Darwin":
        _register_launchd(py, daemon)
    else:
        _register_cron(py, daemon)


def _register_windows_task(py, daemon):
    # pythonw.exe statt python.exe: kein Konsolenfenster beim Check;
    # der Dialog bei vorhandenem Update bleibt sichtbar.
    pyw = str(Path(py).with_name("pythonw.exe"))
    runner = pyw if Path(pyw).exists() else py
    cmd = [
        "schtasks", "/Create", "/TN", AUTO_UPDATE_TASK,
        "/TR", f'"{runner}" "{daemon}"',
        "/SC", "DAILY", "/ST", "03:00",
        "/F",  # vorhandenen Task ueberschreiben
    ]
    subprocess.run(cmd, check=True, capture_output=True)


def _register_launchd(py, daemon):
    label = "com.alvaro.autoupdate"
    plist_dir = Path.home() / "Library" / "LaunchAgents"
    plist_dir.mkdir(parents=True, exist_ok=True)
    plist = plist_dir / f"{label}.plist"
    log_file = appdata_dir() / "update.log"
    plist.write_text(f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key><string>{label}</string>
    <key>ProgramArguments</key>
    <array>
        <string>{py}</string>
        <string>{daemon}</string>
    </array>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key><integer>3</integer>
        <key>Minute</key><integer>0</integer>
    </dict>
    <key>StandardOutPath</key><string>{log_file}</string>
    <key>StandardErrorPath</key><string>{log_file}</string>
</dict>
</plist>
""", encoding="utf-8")
    subprocess.run(["launchctl", "unload", str(plist)], capture_output=True)
    subprocess.run(["launchctl", "load", str(plist)], check=True, capture_output=True)


def _register_cron(py, daemon):
    marker = "# ALVARO_AUTO_UPDATE"
    line = f"0 3 * * * {py} {daemon}  {marker}"
    existing = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
    lines = [l for l in existing.stdout.splitlines() if marker not in l] if existing.returncode == 0 else []
    lines.append(line)
    proc = subprocess.run(["crontab", "-"], input="\n".join(lines) + "\n", text=True, capture_output=True)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or "crontab-Eintrag fehlgeschlagen")


def unregister_auto_update_service():
    """Entferne den Update-Task (fuer Deinstallation)."""
    system = platform.system()
    if system == "Windows":
        subprocess.run(["schtasks", "/Delete", "/TN", AUTO_UPDATE_TASK, "/F"], capture_output=True)
    elif system == "Darwin":
        plist = Path.home() / "Library" / "LaunchAgents" / "com.alvaro.autoupdate.plist"
        subprocess.run(["launchctl", "unload", str(plist)], capture_output=True)
        plist.unlink(missing_ok=True)
    else:
        marker = "# ALVARO_AUTO_UPDATE"
        existing = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
        if existing.returncode == 0:
            lines = [l for l in existing.stdout.splitlines() if marker not in l]
            subprocess.run(["crontab", "-"], input="\n".join(lines) + "\n", text=True, capture_output=True)


if __name__ == "__main__":
    # Deinstallations-Modus: Task entfernen
    if "--uninstall" in sys.argv:
        unregister_auto_update_service()
        print("Auto-Update-Service entfernt.")
        sys.exit(0)

    # Admin-Rechte anfordern (Windows)
    request_admin()

    root = tk.Tk()
    app = AlvaroInstaller(root)
    root.mainloop()
