"""Auto-configure Donut Browser API integration.

Reads (or generates) the API token directly from Donut Browser's
encrypted settings, so the user never has to copy-paste tokens manually.

Donut Browser stores its API token in:
  {data_dir}/settings/api_token.dat  (AES-256-GCM, key derived via Argon2id)
  {data_dir}/settings/app_settings.json  (plaintext, api_enabled flag)

The vault password is the compile-time default from Donut Browser's build.rs.
"""

import base64
import json
import logging
import os
import secrets
import sys

logger = logging.getLogger(__name__)

_VAULT_PASSWORD = "donutbrowser-api-vault-password"


def _donut_data_dir() -> str:
    """Find Donut Browser data directory (matches app_dirs.rs logic)."""
    env_override = os.environ.get("DONUTBROWSER_DATA_DIR")
    if env_override:
        return env_override

    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA", os.path.expanduser("~"))
        return os.path.join(base, "DonutBrowser")

    # Linux / macOS
    xdg = os.environ.get("XDG_DATA_HOME", os.path.expanduser("~/.local/share"))
    return os.path.join(xdg, "DonutBrowser")


def _settings_dir() -> str:
    return os.path.join(_donut_data_dir(), "settings")


def _decrypt_token(file_path: str) -> str | None:
    """Decrypt API token from api_token.dat using Argon2id + AES-256-GCM."""
    try:
        from argon2.low_level import hash_secret_raw, Type
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    except ImportError:
        logger.warning("argon2-cffi or cryptography not installed — cannot auto-read token")
        return None

    try:
        with open(file_path, "rb") as f:
            data = f.read()
    except FileNotFoundError:
        return None

    # Validate header: b"DBAPI" + version byte (2)
    if len(data) < 6 or data[:5] != b"DBAPI" or data[5] != 2:
        return None

    offset = 6

    # Read salt (length-prefixed string)
    salt_len = data[offset]
    offset += 1
    salt_b64 = data[offset:offset + salt_len].decode("utf-8")
    offset += salt_len

    # Decode PHC-format base64 salt (standard base64, no padding)
    padding = (4 - len(salt_b64) % 4) % 4
    salt_raw = base64.b64decode(salt_b64 + "=" * padding)

    # Read nonce (12 bytes for AES-GCM)
    nonce = data[offset:offset + 12]
    offset += 12

    # Read ciphertext (u32 LE length + data)
    ct_len = int.from_bytes(data[offset:offset + 4], "little")
    offset += 4
    ciphertext = data[offset:offset + ct_len]

    # Derive key using Argon2id (matching Rust's Argon2::default())
    key = hash_secret_raw(
        secret=_VAULT_PASSWORD.encode("utf-8"),
        salt=salt_raw,
        time_cost=2,
        memory_cost=19456,
        parallelism=1,
        hash_len=32,
        type=Type.ID,
    )

    # Decrypt with AES-256-GCM
    aesgcm = AESGCM(key)
    plaintext = aesgcm.decrypt(nonce, ciphertext, None)
    return plaintext.decode("utf-8")


def _encrypt_token(token: str) -> bytes:
    """Encrypt API token in Donut Browser's api_token.dat format."""
    from argon2.low_level import hash_secret_raw, Type
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    # Generate random salt (16 bytes, standard for Argon2)
    salt_raw = secrets.token_bytes(16)
    salt_b64 = base64.b64encode(salt_raw).rstrip(b"=").decode("utf-8")

    # Derive key
    key = hash_secret_raw(
        secret=_VAULT_PASSWORD.encode("utf-8"),
        salt=salt_raw,
        time_cost=2,
        memory_cost=19456,
        parallelism=1,
        hash_len=32,
        type=Type.ID,
    )

    # Encrypt
    nonce = secrets.token_bytes(12)
    aesgcm = AESGCM(key)
    ciphertext = aesgcm.encrypt(nonce, token.encode("utf-8"), None)

    # Build file data
    file_data = bytearray()
    file_data.extend(b"DBAPI")  # 5-byte header
    file_data.append(2)  # Version 2
    file_data.append(len(salt_b64))
    file_data.extend(salt_b64.encode("utf-8"))
    file_data.extend(nonce)
    file_data.extend(len(ciphertext).to_bytes(4, "little"))
    file_data.extend(ciphertext)
    return bytes(file_data)


def auto_configure() -> str | None:
    """Auto-configure Donut Browser API token.

    1. If API enabled + token exists → decrypt and return it
    2. If API disabled → enable it, generate token, save encrypted
    3. Returns the API token string, or None on failure.
    """
    settings_dir = _settings_dir()
    settings_file = os.path.join(settings_dir, "app_settings.json")
    token_file = os.path.join(settings_dir, "api_token.dat")

    if not os.path.isdir(settings_dir):
        logger.info("Donut Browser settings dir not found: %s", settings_dir)
        logger.info("Start Donut Browser at least once before running SOSM")
        return None

    # Read current settings
    settings = {}
    if os.path.isfile(settings_file):
        try:
            with open(settings_file) as f:
                settings = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("Cannot read Donut Browser settings: %s", e)

    api_enabled = settings.get("api_enabled", False)

    # Case 1: API enabled, try to read existing token
    if api_enabled and os.path.isfile(token_file):
        token = _decrypt_token(token_file)
        if token:
            logger.info("Donut Browser API token auto-detected")
            return token
        logger.warning("Failed to decrypt Donut Browser API token")

    # Case 2: Enable API and generate new token
    try:
        from argon2.low_level import hash_secret_raw  # noqa: F401
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM  # noqa: F401
    except ImportError:
        logger.warning("argon2-cffi or cryptography not installed — cannot auto-configure Donut Browser")
        return None

    token = secrets.token_urlsafe(32)
    logger.info("Generating new Donut Browser API token and enabling API")

    # Write encrypted token
    os.makedirs(settings_dir, exist_ok=True)
    encrypted = _encrypt_token(token)
    with open(token_file, "wb") as f:
        f.write(encrypted)

    # Enable API in settings (preserve existing settings)
    settings["api_enabled"] = True
    settings.setdefault("api_port", 10108)
    # Note: api_token is NOT stored in JSON (only in encrypted .dat file)
    with open(settings_file, "w") as f:
        json.dump(settings, f, indent=2)

    logger.info("Donut Browser API enabled at port %s", settings.get("api_port", 10108))
    return token
