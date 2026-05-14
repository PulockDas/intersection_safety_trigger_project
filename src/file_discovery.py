"""
file_discovery.py — Utilities for locating zip files and managing output dirs.
"""

from __future__ import annotations

from pathlib import Path


def find_training_zips(directory: Path) -> list[Path]:
    """
    Return a sorted list of .zip files found at the top level of *directory*.

    Prints informative messages; never raises.

    Parameters
    ----------
    directory : Path
        Folder to search (must exist).

    Returns
    -------
    list[Path]
        Sorted list of zip paths (empty list on error or if none found).
    """
    if not directory.exists():
        print(f"[ERROR] Directory does not exist: {directory}")
        print("        Check TRAINING_ZIP_DIR in the configuration cell.")
        return []

    if not directory.is_dir():
        print(f"[ERROR] Path is not a directory: {directory}")
        return []

    zips = sorted(directory.glob("*.zip"))

    if not zips:
        print(f"[WARN]  No .zip files found in: {directory}")
        print("        Make sure your Google Drive is mounted and the path is correct.")
    else:
        print(f"[INFO]  Found {len(zips)} zip file(s) in: {directory}")

    return zips


def make_output_dirs(*dirs: Path) -> None:
    """
    Create one or more output directories, including any missing parents.
    Safe to call when directories already exist.
    """
    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)
        print(f"[INFO]  Output directory ready: {d}")


def resolve_project_root(notebook_path: str | None = None) -> Path:
    """
    Try to infer the project root.

    Checks common Colab Drive locations first, then falls back to the
    current working directory tree.  Returns the first valid candidate,
    or CWD if nothing is found.

    Parameters
    ----------
    notebook_path : str | None
        Optional explicit path to the notebook file; the function will
        walk up two levels (notebooks/ -> project root).
    """
    if notebook_path:
        candidate = Path(notebook_path).resolve().parents[1]
        if (candidate / "src").exists():
            return candidate

    candidates = [
        Path("/content/drive/MyDrive/intersection_safety_trigger_project"),
        Path("/content/intersection_safety_trigger_project"),
        Path.cwd().parent,
        Path.cwd(),
    ]
    for c in candidates:
        if (c / "src").exists():
            print(f"[INFO]  Project root detected: {c}")
            return c

    cwd = Path.cwd()
    print(f"[WARN]  Could not detect project root; using CWD: {cwd}")
    return cwd
