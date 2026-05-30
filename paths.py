"""Canonical runtime paths for the active Friday checkout."""
from __future__ import annotations

import os
from pathlib import Path


def _env_path(name: str) -> Path | None:
    raw = os.environ.get(name, "").strip()
    return Path(raw).expanduser().resolve() if raw else None


def _repo_root() -> Path:
    return Path(__file__).resolve().parent


FRIDAY_ROOT = _env_path("FRIDAY_ROOT") or _repo_root()
FRIDAY_PARENT = FRIDAY_ROOT.parent

NEXUS_ROOT = _env_path("NEXUS_OMEGA_ROOT") or Path("/Users/bhargav/AI Projects/nexus-omega")
AGENCY_ROOT = _env_path("AGENCY_ROOT") or Path("~/agency").expanduser()

LEGACY_FRIDAY_ROOT = Path("~/AI/friday").expanduser()
LEGACY_NEXUS_ROOT = Path("~/nexus-omega").expanduser()


def friday_path(*parts: str) -> Path:
    return FRIDAY_ROOT.joinpath(*parts)


def nexus_path(*parts: str) -> Path:
    return NEXUS_ROOT.joinpath(*parts)

