#!/usr/bin/env python3
"""
vlc_maverick_builder.py

A helper script that:
  1. Clones or updates the official VLC repo.
  2. Applies local patches from ./patches.
  3. Optionally runs bootstrap / configure / make.

Usage examples:

  # Clone/update VLC and apply patches only
  python vlc_maverick_builder.py --apply-only

  # Clone/update, apply patches, configure and build
  python vlc_maverick_builder.py --configure --build

  # Specify a custom work directory
  python vlc_maverick_builder.py --work-dir /path/to/work \
      --configure --build
"""

import argparse
import subprocess
import sys
import shutil
import textwrap
from pathlib import Path
from typing import List, Optional


DEFAULT_REMOTE = "https://code.videolan.org/videolan/vlc.git"
DEFAULT_BRANCH = "master"


def run(
    cmd: List[str],
    cwd: Optional[Path] = None,
    env: Optional[dict] = None,
) -> None:
    """
    Run a command, streaming stdout/stderr, raising on failure.
    """
    print(f"\n[RUN] {' '.join(cmd)}")
    try:
        subprocess.run(
            cmd,
            cwd=str(cwd) if cwd else None,
            env=env,
            check=True,
        )
    except subprocess.CalledProcessError as exc:
        print(f"[ERROR] Command failed: {exc}", file=sys.stderr)
        sys.exit(exc.returncode)


def check_tool(name: str) -> None:
    """
    Ensure an external tool is available on PATH.
    """
    if shutil.which(name) is None:
        print(f"[ERROR] Required tool not found on PATH: {name}",
              file=sys.stderr)
        sys.exit(1)


def ensure_repo(
    work_dir: Path,
    remote: str,
    branch: str,
) -> Path:
    """
    Clone VLC repo into work_dir/vlc if missing, otherwise update it.

    Returns the path to the VLC repo directory.
    """
    repo_dir = work_dir / "vlc"

    if not repo_dir.exists():
        print(f"[INFO] Cloning VLC into {repo_dir}")
        work_dir.mkdir(parents=True, exist_ok=True)
        run(["git", "clone", remote, str(repo_dir)])
    else:
        print(f"[INFO] VLC repo exists at {repo_dir}, fetching updates")
        run(["git", "fetch", "origin"], cwd=repo_dir)

    print(f"[INFO] Checking out branch {branch}")
    run(["git", "checkout", branch], cwd=repo_dir)
    run(["git", "pull", "origin", branch], cwd=repo_dir)

    return repo_dir


def apply_patches(
    repo_dir: Path,
    patches_dir: Path,
    reverse: bool = False,
) -> None:
    """
    Apply all .patch files in patches_dir (sorted by name) using git apply.

    If reverse=True, patches are reversed (for cleanup).
    """
    if not patches_dir.exists():
        print(f"[INFO] No patches directory found: {patches_dir}")
        return

    patch_files = sorted(patches_dir.glob("*.patch"))
    if not patch_files:
        print(f"[INFO] No .patch files found in {patches_dir}")
        return

    print(f"[INFO] Applying patches from {patches_dir}")
    for patch in patch_files:
        print(f"[INFO] Applying patch: {patch.name}")
        cmd = ["git", "apply"]
        if reverse:
            cmd.append("--reverse")
        cmd.append(str(patch))
        run(cmd, cwd=repo_dir)


def configure_vlc(
    repo_dir: Path,
    build_dir: Path,
    extra_flags: List[str],
    run_bootstrap: bool,
) -> None:
    """
    Run bootstrap (optionally) and configure VLC in an out-of-tree build dir.

    This assumes a Unix-like environment with autotools available.
    """
    build_dir.mkdir(parents=True, exist_ok=True)

    if run_bootstrap:
        print("[INFO] Running ./bootstrap in VLC repo")
        run(["./bootstrap"], cwd=repo_dir)

    configure_script = repo_dir / "configure"
    if not configure_script.exists():
        print(
            "[ERROR] configure script not found. "
            "Try running with --bootstrap.",
            file=sys.stderr,
        )
        sys.exit(1)

    # Typical minimal configure command. You can tweak this for
    # your fork (e.g. enable/disable modules).
    cmd = [str(configure_script), f"--prefix={build_dir / 'install'}"]
    cmd.extend(extra_flags)

    print("[INFO] Configuring VLC (out-of-tree)")
    run(cmd, cwd=build_dir)


def build_vlc(build_dir: Path, jobs: int) -> None:
    """
    Build VLC using make.
    """
    print(f"[INFO] Building VLC in {build_dir}")
    cmd = ["make"]
    if jobs > 0:
        cmd.extend(["-j", str(jobs)])
    run(cmd, cwd=build_dir)


def parse_args() -> argparse.Namespace:
    """
    Parse command-line arguments.
    """
    parser = argparse.ArgumentParser(
        description="Patch and build VLC from upstream.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent(
            """
            Recommended workflow:

              1) Place your patch files in ./patches
                 (use git format-patch or git diff > file.patch).

              2) Run:
                   python vlc_maverick_builder.py --apply-only

              3) Once patches apply cleanly, configure + build:
                   python vlc_maverick_builder.py \\
                       --configure --build --jobs 8
            """
        ),
    )

    parser.add_argument(
        "--work-dir",
        type=Path,
        default=Path("work"),
        help="Working directory for repo and build (default: ./work)",
    )
    parser.add_argument(
        "--patches-dir",
        type=Path,
        default=Path("patches"),
        help="Directory containing .patch files (default: ./patches)",
    )
    parser.add_argument(
        "--remote",
        default=DEFAULT_REMOTE,
        help=("VLC git remote URL "
              f"(default: {DEFAULT_REMOTE})"),
    )
    parser.add_argument(
        "--branch",
        default=DEFAULT_BRANCH,
        help=f"VLC git branch to checkout (default: {DEFAULT_BRANCH})",
    )
    parser.add_argument(
        "--apply-only",
        action="store_true",
        help="Only clone/update repo and apply patches (no configure/build).",
    )
    parser.add_argument(
        "--bootstrap",
        action="store_true",
        help="Run ./bootstrap before configure.",
    )
    parser.add_argument(
        "--configure",
        action="store_true",
        help="Run configure in an out-of-tree build directory.",
    )
    parser.add_argument(
        "--build",
        action="store_true",
        help="Build VLC using make.",
    )
    parser.add_argument(
        "--jobs",
        type=int,
        default=0,
        help="Number of parallel build jobs for make (default: 0 = auto).",
    )
    parser.add_argument(
        "--configure-flags",
        nargs="*",
        default=[],
        help="Extra flags to pass to ./configure.",
    )
    parser.add_argument(
        "--reverse-patches",
        action="store_true",
        help="Reverse patches instead of applying them (cleanup).",
    )

    return parser.parse_args()


def main() -> None:
    """
    Entry point.
    """
    args = parse_args()

    # Ensure critical external tools are available.
    check_tool("git")
    if args.configure or args.build or args.bootstrap:
        check_tool("make")

    work_dir = args.work_dir.resolve()
    patches_dir = args.patches_dir.resolve()
    build_dir = work_dir / "build"

    print(f"[INFO] Work directory: {work_dir}")
    print(f"[INFO] Patches directory: {patches_dir}")

    repo_dir = ensure_repo(
        work_dir=work_dir,
        remote=args.remote,
        branch=args.branch,
    )

    apply_patches(
        repo_dir=repo_dir,
        patches_dir=patches_dir,
        reverse=args.reverse_patches,
    )

    if args.apply_only:
        print("[INFO] Apply-only mode requested, done.")
        return

    if args.configure:
        configure_vlc(
            repo_dir=repo_dir,
            build_dir=build_dir,
            extra_flags=args.configure_flags,
            run_bootstrap=args.bootstrap,
        )

    if args.build:
        build_vlc(build_dir=build_dir, jobs=args.jobs)

    print("[INFO] All done.")


if __name__ == "__main__":
    main()
