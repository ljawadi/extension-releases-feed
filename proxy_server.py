#!/usr/bin/env python3
"""
Lokaler HTTPS-Proxy: Serviert Alvaro unter https://teamnanagement.horbach-center-stuttgart.de/crm/dashboard
(doppeltes n – damit die echte teammanagement-Seite noch erreichbar bleibt)
- Port 443 (HTTPS)
- Self-signed Zertifikat: certs/cert-typo.pem + certs/key-typo.pem
- Adressleiste zeigt: https://teamnanagement.horbach-center-stuttgart.de
- Geladen: https://crm.alvarofinanz.de (via loopback mit Alvaro-Skin)

Nutzer:
  1. hosts-Datei: 127.0.0.1 teamnanagement.horbach-center-stuttgart.de
  2. Zertifikat in Brave vertrauen (ca. 1x per Sitzung):
     - brave://settings/security
     - "Zertifikate verwalten" → "Zertifizierungsstellen"
     - PEM importieren: certs/cert-typo.pem
  3. Diesen Server starten: py proxy_server.py (Administrator-Rechte nötig für Port 443)
  4. In Brave: https://teamnanagement.horbach-center-stuttgart.de/crm/dashboard
"""

import http.server
import ssl
import json
from pathlib import Path
from urllib.parse import urlparse, urljoin

ALVARO_BASE = "https://crm.alvarofinanz.de"
CERT_DIR = Path(__file__).parent / "certs"
CERT_FILE = CERT_DIR / "cert-typo.pem"
KEY_FILE = CERT_DIR / "key-typo.pem"

class ProxyHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        """Alle GET-Anfragen nach Alvaro umleiten."""
        # Parse die angeforderte URL
        path = self.path
        # Rewrite: /crm/dashboard → /buyer/dashboard (optional, wenn nötig)
        if path.startswith("/crm/"):
            path = path.replace("/crm/", "/buyer/", 1)

        target_url = urljoin(ALVARO_BASE, path)

        self.send_response(307)  # Temporary Redirect
        self.send_header("Location", target_url)
        self.send_header("Content-Length", "0")
        self.end_headers()

        print(f"[PROXY] GET {self.path} → {target_url}")

    def do_POST(self):
        """POST-Anfragen auch weiterleiten."""
        self.do_GET()

    def log_message(self, format, *args):
        """Logging."""
        print(f"[{self.client_address[0]}] {format % args}")

def run_server(port=443):
    """HTTPS-Server starten."""
    if not CERT_FILE.exists() or not KEY_FILE.exists():
        print(f"❌ Zertifikat nicht gefunden!")
        print(f"   Erstelle es mit:")
        print(f"   openssl req -x509 -newkey rsa:2048 -keyout {KEY_FILE} -out {CERT_FILE} -days 365 -nodes \\")
        print(f"     -subj '/CN=teammanagement.horbach-center-stuttgart.de'")
        return

    server = http.server.HTTPServer(("0.0.0.0", port), ProxyHandler)

    # HTTPS-Kontext setzen
    context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
    context.load_cert_chain(str(CERT_FILE), str(KEY_FILE))
    server.socket = context.wrap_socket(server.socket, server_side=True)

    print(f"🔒 HTTPS-Proxy läuft auf https://teamnanagement.horbach-center-stuttgart.de:{port}")
    print(f"   (doppeltes n – echte teammanagement-Seite bleibt erreichbar)")
    print(f"   → Alvaro-Backend: {ALVARO_BASE}")
    print(f"   Stoppen mit Strg+C")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n⏹ Server gestoppt")
        server.shutdown()

if __name__ == "__main__":
    run_server(443)
