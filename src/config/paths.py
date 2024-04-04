from pathlib import Path


SRC_DIR = Path(__file__).parent.parent

CONFIG_DIR = SRC_DIR / "config"
DATA_DIR = SRC_DIR / "data"

CACHE_DIR = DATA_DIR / "cache"
LOG_DIR = DATA_DIR / "logs"
PERMS_DIR = DATA_DIR / "perms"

SECRETS_FILE = CONFIG_DIR / "secrets.toml"
DISCORD_CONFIG = CONFIG_DIR / "discord_config.toml"

for dir in [CONFIG_DIR, DATA_DIR, CACHE_DIR, LOG_DIR, PERMS_DIR]:
    if not dir.exists():
        dir.mkdir(parents=True, exist_ok=True)

for file in [SECRETS_FILE, DISCORD_CONFIG]:
    assert file.exists(), file
