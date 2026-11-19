"""Read/write the local .env. Values here are secrets: never log or return them."""
from pathlib import Path

from dotenv import dotenv_values

COOKIE_KEYS = (
    "ltuid_v2", "ltoken_v2", "ltmid_v2", "account_id_v2", "account_mid_v2", "cookie_token_v2",
)


def read_env(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    return {k: v for k, v in dotenv_values(path).items() if v}


def update_env(path: Path, values: dict[str, str]) -> None:
    """Set the given keys, keep every other line (comments, PORT, ...) untouched."""
    lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    remaining = dict(values)
    out: list[str] = []
    for line in lines:
        stripped = line.strip()
        key = stripped.split("=", 1)[0].strip() if "=" in stripped and not stripped.startswith("#") else None
        if key is not None and key in remaining:
            out.append(f"{key}={remaining.pop(key)}")
        else:
            out.append(line)
    out.extend(f"{k}={v}" for k, v in remaining.items())
    path.write_text("\n".join(out) + "\n", encoding="utf-8")


def cookies_from_env(env: dict[str, str]) -> dict[str, str]:
    return {k: env[k.upper()] for k in COOKIE_KEYS if env.get(k.upper())}


def connection_status(env: dict[str, str], stored_status: object) -> dict:
    if not (env.get("LTUID_V2") and env.get("LTOKEN_V2")):
        return {"status": "missing", "uid": None}
    uid = int(env["GENSHIN_UID"]) if env.get("GENSHIN_UID") else None
    return {"status": "expired" if stored_status == "expired" else "connected", "uid": uid}
