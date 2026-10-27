#!/usr/bin/env python3
"""
Baut den Windows .exe-Installer mit PyInstaller.
Verwendet: pip install pyinstaller
"""

import os
import subprocess
import sys
from pathlib import Path

def build_windows_exe():
    """Baue Windows .exe mit PyInstaller."""
    installer_py = Path(__file__).parent / "installer.py"
    output_dir = Path(__file__).parent / "dist"

    if not installer_py.exists():
        print(f"❌ {installer_py} nicht gefunden")
        sys.exit(1)

    print("🔨 Baue Windows .exe mit PyInstaller...")

    cmd = [
        "pyinstaller",
        "--onefile",  # Eine einzelne .exe
        "--windowed",  # Kein Console-Fenster
        "--icon=extension/icons/icon128.png",  # Optional: Icon
        "--name=AlvaroInstaller",
        "--distpath=dist",
        "--buildpath=build",
        "--specpath=.",
        str(installer_py)
    ]

    try:
        result = subprocess.run(cmd, check=True)
        exe_path = output_dir / "AlvaroInstaller.exe"

        if exe_path.exists():
            print(f"\n✅ .exe erstellt: {exe_path}")
            print(f"📦 Größe: {exe_path.stat().st_size / (1024*1024):.1f} MB")
            print(f"\n💡 Nutzer können jetzt einfach doppelklicken!")
        else:
            print("❌ .exe wurde nicht gefunden nach Build")
    except subprocess.CalledProcessError as e:
        print(f"❌ Build fehlgeschlagen: {e}")
        print("\n💡 PyInstaller installieren: pip install pyinstaller")
        sys.exit(1)

if __name__ == "__main__":
    build_windows_exe()
