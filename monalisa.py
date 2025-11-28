#!/usr/bin/env python3
"""
Configure VLC on Windows to use a specific SoundFont for MIDI playback.

By default this script will point VLC at:
    D:\Monalisa.sf2

You can override that with:
    python configure_vlc_soundfont.py "E:\SoundFonts\SomeFont.sf2"
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import List


def get_vlc_config_file() -> Path:
    """
    Return the path to the VLC config file (vlcrc) for the current user.

    On Windows this is normally:
        %APPDATA%\vlc\vlcrc
    """
    appdata = os.environ.get("APPDATA")
    if not appdata:
        raise RuntimeError("APPDATA environment variable is not set.")
    config_dir = Path(appdata) / "vlc"
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir / "vlcrc"


def backup_file(path: Path) -> None:
    """
    Make a simple .bak backup if the file exists and no backup exists yet.
    """
    if path.exists():
        backup = path.with_suffix(path.suffix + ".bak")
        if not backup.exists():
            backup.write_bytes(path.read_bytes())


def update_soundfont_in_lines(lines: List[str], sf_path: Path) -> List[str]:
    """
    Update or append the soundfont= line in an existing vlcrc content.
    """
    target_line = f'soundfont="{sf_path}"\n'
    updated: List[str] = []
    found = False

    for line in lines:
        stripped = line.lstrip()
        if stripped.startswith("soundfont=") or stripped.startswith("#soundfont="):
            # Replace any existing soundfont setting (commented or not)
            updated.append(target_line)
            found = True
        else:
            updated.append(line)

    if not found:
        # Append at the end if nothing was found
        if updated and not updated[-1].endswith("\n"):
            updated[-1] = updated[-1] + "\n"
        updated.append("\n# Set by configure_vlc_soundfont.py\n")
        updated.append(target_line)

    return updated


def configure_vlc_soundfont(sf_path: Path) -> Path:
    """
    Ensure vlcrc exists and points VLC at the given SoundFont path.
    Returns the path to vlcrc.
    """
    if not sf_path.is_file():
        raise FileNotFoundError(f"SoundFont not found: {sf_path}")

    vlcrc = get_vlc_config_file()
    backup_file(vlcrc)

    if vlcrc.exists():
        text = vlcrc.read_text(encoding="utf-8", errors="ignore")
        lines = text.splitlines(keepends=True)
    else:
        lines = []

    new_lines = update_soundfont_in_lines(lines, sf_path.resolve())
    vlcrc.write_text("".join(new_lines), encoding="utf-8")
    return vlcrc


def parse_args() -> argparse.Namespace:
    """
    Parse CLI arguments.
    """
    parser = argparse.ArgumentParser(
        description="Configure VLC to use a specific SoundFont for MIDI playback."
    )
    parser.add_argument(
        "soundfont",
        nargs="?",
        default=r"D:\Monalisa.sf2",
        help="Path to .sf2 SoundFont file (default: D:\\Monalisa.sf2)",
    )
    return parser.parse_args()


def main() -> None:
    """
    Entrypoint: parse args, configure VLC, and report what was changed.
    """
    args = parse_args()
    sf_path = Path(args.soundfont)

    vlcrc_path = configure_vlc_soundfont(sf_path)
    print(f"Configured VLC SoundFont to: {sf_path.resolve()}")
    print(f"Config file updated at: {vlcrc_path}")


if __name__ == "__main__":
    main()
