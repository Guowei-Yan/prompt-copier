"""
SSH key management — filesystem-based storage for uploaded private keys.

Keys are stored in a configurable directory (default: data/ssh_keys/).
Each key gets a user-assigned label and is saved as <label>.pem with mode 0o600.
"""

import json
import os
import time
from typing import Dict, List, Optional


_SSH_KEYS_DIR = os.environ.get("SSH_KEYS_DIR", os.path.join("data", "ssh_keys"))
_META_FILE = os.path.join(_SSH_KEYS_DIR, "_meta.json")


def _ensure_dir() -> None:
    os.makedirs(_SSH_KEYS_DIR, exist_ok=True)


def _load_meta() -> Dict[str, Dict]:
    _ensure_dir()
    if not os.path.exists(_META_FILE):
        return {}
    try:
        with open(_META_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return {}


def _save_meta(meta: Dict[str, Dict]) -> None:
    _ensure_dir()
    with open(_META_FILE, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)


def _key_file_path(label: str) -> str:
    safe = label.replace("/", "_").replace("\\", "_").replace(" ", "_")
    return os.path.join(_SSH_KEYS_DIR, f"{safe}.pem")


def save_key(label: str, key_bytes: bytes) -> str:
    """Save an SSH private key and return the file path.

    Args:
        label: Human-readable name, e.g. "work-laptop"
        key_bytes: Raw bytes of the private key file

    Returns:
        Absolute path of the saved key file.
    """
    _ensure_dir()
    path = _key_file_path(label)
    with open(path, "wb") as f:
        f.write(key_bytes)
    os.chmod(path, 0o600)

    meta = _load_meta()
    meta[label] = {
        "filename": os.path.basename(path),
        "uploaded_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    _save_meta(meta)

    return os.path.abspath(path)


def list_keys() -> List[Dict]:
    """Return list of ``{label, filename, uploaded_at}``."""
    meta = _load_meta()
    result = []
    for label, info in meta.items():
        path = _key_file_path(label)
        if os.path.exists(path):
            result.append({
                "label": label,
                "filename": info.get("filename", ""),
                "uploaded_at": info.get("uploaded_at", ""),
            })
    return result


def delete_key(label: str) -> bool:
    """Delete a key by label.  Returns True if it existed."""
    path = _key_file_path(label)
    existed = False
    if os.path.exists(path):
        os.remove(path)
        existed = True

    meta = _load_meta()
    if label in meta:
        del meta[label]
        _save_meta(meta)
        existed = True

    return existed


def get_key_path(label: str) -> Optional[str]:
    """Return the absolute path of a key file, or None if it doesn't exist."""
    path = _key_file_path(label)
    if os.path.exists(path):
        return os.path.abspath(path)
    return None
