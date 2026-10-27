# Push zum Gitea: Schritt-für-Schritt

## 🔐 Schritt 1: Gitea Token erstellen

1. Gehe zu: `https://gitea.thedoomsdayproject.ignorelist.com:3000/user/settings/applications`
2. Klicke: **"Generate New Token"**
3. Name: `alvaro-releases-push`
4. Berechtigungen: ✓ api ✓ write:repository
5. Token kopieren und speichern!

---

## 🔗 Schritt 2: Remote-Repo in Git hinzufügen

```powershell
cd D:\AI\alvaro-releases

# Remote mit HTTPS + Token
git remote add origin https://ljawadi:YOUR_TOKEN@gitea.thedoomsdayproject.ignorelist.com:3000/ljawadi/alvaro-releases.git

# Oder mit SSH (falls SSH-Key eingerichtet)
git remote add origin git@gitea.thedoomsdayproject.ignorelist.com:ljawadi/alvaro-releases.git
```

**Wichtig**: `YOUR_TOKEN` durch echten Token ersetzen!

---

## 📤 Schritt 3: Erster Push

```powershell
cd D:\AI\alvaro-releases

# Alle Dateien hinzufügen
git add .

# Commit
git commit -m "Initial: Alvaro Release Management System

- GUI-Installer (tkinter)
- Update-Checker
- Release-Feed (JSON)
- Build-Skripte

Co-Authored-By: Claude Haiku 4.5 <noreply@anthropic.com>"

# Push zum Gitea
git push -u origin main
```

---

## ✅ Schritt 4: Verifizieren

```powershell
# Prüfe Remote-URL
git remote -v

# Prüfe, dass alles gepusht wurde
git log --oneline -5

# Browser: https://gitea.thedoomsdayproject.ignorelist.com:3000/ljawadi/alvaro-releases
```

---

## 🔄 Für zukünftige Pushes

```powershell
cd D:\AI\alvaro-releases

# Änderungen machen
git add .
git commit -m "Release: v1.1.0 - [Beschreibung]"

# Push
git push

# Tag erstellen (für Release-Markierung)
git tag v1.1.0
git push origin v1.1.0
```

---

## 🔐 Token sicher speichern (alternativ)

Statt Token in Remote-URL (unsicher):

### **Credential Manager (Windows)**
```powershell
# Einmalig: Token speichern
cmdkey /add:gitea.thedoomsdayproject.ignorelist.com /user:ljawadi /pass:YOUR_TOKEN

# Remote ohne Token
git remote add origin https://gitea.thedoomsdayproject.ignorelist.com:3000/ljawadi/alvaro-releases.git
```

### **SSH (sicherer)**
```powershell
# SSH-Key generieren (falls noch nicht vorhanden)
ssh-keygen -t ed25519 -C "ljawadi@stud.hs-offenburg.de"

# Public-Key zu Gitea hinzufügen:
# 1. Datei öffnen: C:\Users\jluka\.ssh\id_ed25519.pub
# 2. Inhalt kopieren
# 3. Gitea: Settings → SSH Keys → Add Key

# Remote mit SSH
git remote add origin git@gitea.thedoomsdayproject.ignorelist.com:ljawadi/alvaro-releases.git
```

---

## 🆘 Fehlersuche

### **„fatal: repository not found"**
- Token ist falsch oder abgelaufen
- Repo existiert noch nicht auf Gitea
- → Erstelle Repo manuell auf Gitea zuerst

### **„permission denied"**
- SSH-Key nicht hinzugefügt oder falsch
- Token hat nicht die nötige Berechtigung
- → Prüfe Token-Berechtigungen

### **„SSL certificate problem"**
- Gitea-Zertifikat ist selbstsigniert
- **Workaround (nur für Testing!):**
  ```powershell
  git config --global http.sslVerify false
  ```
- **Besser:** Zertifikat importieren (siehe Setup-Docs)

---

## 📋 Checkliste

- [ ] Gitea Token erstellt
- [ ] Remote hinzugefügt: `git remote -v` zeigt Origin
- [ ] Lokale Commits vorhanden: `git log` zeigt Commits
- [ ] Push erfolgreich: `git push` ohne Fehler
- [ ] Gitea-Repo sichtbar: Website zeigt Dateien

---

## 🎯 Nächste Schritte

Nach erfolgreichem Push:

1. **Release-Feed testen:**
   ```powershell
   python3 update_checker.py
   ```

2. **Download-Links in release_feed.json aktualisieren:**
   ```json
   "url": "https://gitea.thedoomsdayproject.ignorelist.com:3000/ljawadi/alvaro-releases/raw/branch/main/..."
   ```

3. **Binaries hochladen:**
   - Windows .exe in `releases/`
   - Mac .dmg in `releases/`
   - Linux .AppImage in `releases/`

---

**Gitea Server**: https://gitea.thedoomsdayproject.ignorelist.com:3000  
**Repo-URL**: https://gitea.thedoomsdayproject.ignorelist.com:3000/ljawadi/alvaro-releases
