"""Shared configuration for the Revenue Intelligence Inbox.

Loads ``backend/.env`` with the same comment-stripping pattern as
``backend/test_connectivity.py`` and exposes a lazily-built Supabase client.
Secrets are read from the environment and never printed by this module.
"""
from __future__ import annotations

from datetime import timedelta, timezone
from pathlib import Path

# backend/ is the parent of this package's directory (backend/app/).
BACKEND_DIR = Path(__file__).resolve().parent.parent
ENV_PATH = BACKEND_DIR / ".env"

# Fixed Asia/Kolkata offset (UTC+05:30, no DST since 1945). A fixed offset is
# correct for 2026 and avoids the missing tzdata / Windows-zoneinfo dependency
# for Asia/Kolkata on this host. Mirrors scripts/inspect_data.py.
KOLKATA = timezone(timedelta(hours=5, minutes=30))


def load_env() -> dict[str, str]:
    """Read backend/.env, stripping inline comments. Mirrors test_connectivity."""
    env: dict[str, str] = {}
    if not ENV_PATH.exists():
        return env
    for raw in ENV_PATH.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        val = val.split("#")[0].strip()
        env[key.strip()] = val
    return env


ENV: dict[str, str] = load_env()


def app_env() -> str:
    """Return APP_ENV (lowercased); defaults to 'development'."""
    return ENV.get("APP_ENV", "development").lower()


def get_supabase_client():
    """Build and return the Supabase client using the service role key.

    Raises if SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY are missing. The key is
    used server-side only and is never returned or logged.
    """
    from supabase import create_client

    url = ENV.get("SUPABASE_URL", "")
    key = ENV.get("SUPABASE_SERVICE_ROLE_KEY", "")
    if not url or not key:
        raise RuntimeError(
            "Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY in backend/.env"
        )
    return create_client(url, key)
