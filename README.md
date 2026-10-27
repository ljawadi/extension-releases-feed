# Alvaro CRM Installer – Release Management

Zentrales Release-Repository für **Alvaro ↔ Teamnanagement Installer**.

Enthält:
- 📋 **Release-Feed** (`release_feed.json`) – Versionsverwaltung & Download-Links
- 🔄 **Update-Checker** (`update_checker.py`) – Prüft auf verfügbare Updates
- 📦 **Installer-Skripte** – GUI-Installer & Proxy
- 🎯 **CI/CD-Hooks** – Automatische Builds und Releases

---

## 📁 Repo-Struktur

```
alvaro-releases/
├── README.md                    ← Diese Datei
├── release_feed.json            ← Update-Feed (JSON)
├── update_checker.py            ← Update-Checker-Skript
├── installer.py                 ← GUI-Installer (tkinter)
├── proxy_server.py              ← HTTPS-Proxy
├── build_installer.py           ← Windows .exe-Builder
│
├── releases/                    ← Download-Ordner
│   ├── AlvaroInstaller-1.0.0.exe
│   ├── AlvaroInstaller-1.0.0-arm64.dmg
│   ├── AlvaroInstaller-1.0.0-intel.dmg
│   └── installer-1.0.0.py
│
├── docs/                        ← Dokumentation
│   ├── INSTALLATION.md
│   ├── RELEASES.md
│   └── UPDATE_PROCESS.md
│
└── scripts/                     ← Build & Deployment-Skripte
    ├── build_windows.sh
    ├── build_mac.sh
    └── publish_release.sh
```

---

## 🚀 Workflow: Neue Version veröffentlichen

### **1. Version vorbereiten**

```bash
# Aktualisiere Versionsnummer
# installer.py: CURRENT_VERSION = "1.1.0"
# release_feed.json: neue Entry hinzufügen

# Teste lokal
python3 installer.py
```

### **2. Binaries bauen**

```bash
# Windows .exe
pip install pyinstaller
python3 build_installer.py
# → dist/AlvaroInstaller.exe

# Mac (mit PyInstaller oder native Packaging)
# → releases/AlvaroInstaller-1.1.0-arm64.dmg
# → releases/AlvaroInstaller-1.1.0-intel.dmg
```

### **3. Release-Feed aktualisieren**

```json
{
  "version": "1.1.0",
  "releaseDate": "2026-10-28",
  "downloads": {
    "windows_exe": {
      "url": "https://gitea.../releases/AlvaroInstaller-1.1.0.exe",
      "checksum": "sha256:...",
      "size": "45MB"
    },
    ...
  },
  "changelog": [
    "✨ Neue Feature",
    "🐛 Bug-Fix"
  ]
}
```

### **4. Commit & Push**

```bash
git add .
git commit -m "Release: v1.1.0 - Neue Features und Bug-Fixes"
git tag v1.1.0
git push origin main
git push origin v1.1.0
```

---

## 📡 Update-Checker verwenden

Installer prüft automatisch auf Updates:

```bash
python3 update_checker.py
```

Output:
```
📡 Prüfe auf Updates...
🎉 UPDATE VERFÜGBAR! 1.0.0 → 1.1.0

📅 Veröffentlicht: 2026-10-28
📝 Änderungen:
   • ✨ Neue Feature
   • 🐛 Bug-Fix

🔗 Repository:
   https://gitea.thedoomsdayproject.ignorelist.com:3000/ljawadi/alvaro-releases

📦 Downloads:
   • windows_exe: 45MB
```

---

## 🔐 Update-Feed Struktur

```json
{
  "releases": [
    {
      "version": "1.1.0",
      "releaseDate": "2026-10-28",
      "channel": "stable",
      "downloads": {
        "windows_exe": { "url": "...", "checksum": "...", "size": "..." },
        "mac_arm64": { ... },
        "mac_intel": { ... },
        "python_script": { ... }
      },
      "changelog": ["✨ New feature", "🐛 Bug fix"],
      "deprecated": false
    }
  ],
  "metadata": {
    "lastUpdated": "2026-10-28T10:00:00Z",
    "repository": "https://gitea.../alvaro-releases",
    "feedUrl": "https://gitea.../raw/branch/main/release_feed.json"
  }
}
```

---

## 🔗 Integration in Installer

`installer.py` ruft automatisch `release_feed.json` von Gitea ab:

1. **Beim Start** → Prüft auf Updates
2. **Falls Update verfügbar** → Warnt Nutzer mit Dialog
3. **Nutzer klickt "Update"** → Download & Installation

---

## 📦 Versioning

- **Major.Minor.Patch** (z.B. 1.2.3)
- **Stable Channel** für produktive Releases
- **Beta Channel** für Test-Releases (optional)

---

## 🔄 CI/CD (optional)

Automatische Builds auf Tag-Push:

```yaml
# .gitea/workflows/release.yml
on:
  push:
    tags: ["v*"]

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Build Windows
        run: python build_installer.py
      - name: Upload Release
        run: ./scripts/publish_release.sh
```

---

## 🆘 Notizen

- **Checksums** werden lokal berechnet: `sha256sum installer-1.0.0.py`
- **Update-Feed URL**: `https://gitea.../raw/branch/main/release_feed.json`
- **Downloads direkt von Gitea**: Raw-Links in `release_feed.json`
- **Keine externen CDNs** – alles läuft über Gitea

---

## 📞 Support

Fehler bei Updates? Schreibe einen Issue ins Repo oder kontaktiere den Maintainer.

---

**Repository**: https://gitea.thedoomsdayproject.ignorelist.com:3000/ljawadi/alvaro-releases  
**Maintainer**: ljawadi  
**Zuletzt aktualisiert**: 2026-10-27
