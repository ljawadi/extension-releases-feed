# Changelog – Alvaro CRM Installer

Alle Änderungen an diesem Projekt werden hier dokumentiert.

---

## [1.0.2] – 2026-10-27

### 🐛 Bugfixes
- FIX: Zertifikat-Dateien ins Bundle (`datas=[('certs','certs')]`) – One-File-Build
  fand `certs/cert-typo.pem` zuvor nicht und brach mit „Zertifikat nicht gefunden" ab
- FIX: `proxy_server.py` ins Bundle aufgenommen (wird als Subprozess gestartet)
- FIX: Zertifikat- und Proxy-Lookup nutzen jetzt `_BASE_DIR` (`sys._MEIPASS`),
  statt `__file__` – deterministisch im eingefrorenen One-File-Modus

---

## [1.0.0] – 2026-10-27

### ✨ Features
- Grafischer One-Click-Installer (tkinter)
- Browser-Erkennung für Windows, macOS, Linux
- Automatische hosts-Datei-Konfiguration
- HTTPS-Zertifikat-Import in OS/Browser
- Proxy-Server für URL-Weiterleitung
- Update-Checker mit Gitea-Integration
- Release-Feed-System (JSON)

### 🐛 Bugfixes
- Keine bekannten Bugs in v1.0.0

### 📦 Unterstützte Plattformen
- Windows 10+ (PowerShell Admin)
- macOS 10.13+ (Intel & Apple Silicon)
- Linux (Ubuntu, Debian, Fedora)

### 🌐 Unterstützte Browser
- Chrome/Chromium
- Edge
- Firefox
- Safari (macOS)
- Opera
- Brave

### 🔧 Technische Details
- Python 3.8+
- tkinter (Standard-Library)
- PyInstaller für Windows .exe
- Self-signed HTTPS-Zertifikat (365 Tage)

---

## [Geplant: 1.1.0]

- [ ] Mac .dmg-Installer (native)
- [ ] Linux .AppImage-Installer
- [ ] Auto-Update-Funktion im Installer
- [ ] Dark Mode für GUI
- [ ] Proxy-Port-Konfiguration
- [ ] Erweiterte Fehlerdiagnose

---

## Format-Hinweise

### Für neue Releases:

```markdown
## [X.Y.Z] – YYYY-MM-DD

### ✨ Features
- Feature 1
- Feature 2

### 🐛 Bugfixes
- Bug 1 behoben
- Bug 2 behoben

### 📚 Dokumentation
- Neue Seite: XYZ
- Updated: ABC

### ⚠️ Breaking Changes
- Alte Funktion X entfernt

### 📦 Abhängigkeiten
- Aktualisiert: Package A → 2.0
```

---

## Release-Prozess

1. **Version in `installer.py` aktualisieren**
   ```python
   CURRENT_VERSION = "1.1.0"
   ```

2. **Changelog schreiben** (diese Datei)

3. **Commit & Tag**
   ```bash
   git commit -am "Release v1.1.0"
   git tag -a v1.1.0 -m "Version 1.1.0"
   ```

4. **Push**
   ```bash
   git push origin main
   git push origin v1.1.0
   ```

5. **Gitea Release erstellen**
   ```powershell
   .\publish_release.ps1 -Version "1.1.0"
   ```

6. **Binaries hochladen** zu `releases/`

7. **Update-Feed aktualisieren** (`release_feed.json`)

---

## Versionierung

Wir folgen [Semantic Versioning](https://semver.org/):

- **MAJOR** (1.0.0): Breaking Changes
- **MINOR** (1.1.0): Neue Features (backwards-compatible)
- **PATCH** (1.0.1): Bugfixes

---

## Support

Bugs oder Feature-Requests? Schreib einen Issue auf Gitea!

---

**Repository**: https://gitea.thedoomsdayproject.ignorelist.com:3000/ljawadi/alvaro-releases  
**Maintainer**: ljawadi
