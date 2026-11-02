import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def load_env():
    """Read literal KEY=value entries; never execute shell code or overwrite env."""
    for name in (".env.local", ".env"):
        path = ROOT / name
        if not path.exists():
            continue
        for line in path.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            value = value.strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
                value = value[1:-1]
            # Skip empty assignments so a blank FIREWORKS_API_KEY= cannot clobber
            # a real key provided by the shell / LaunchAgent environment.
            if not value:
                continue
            os.environ.setdefault(key.strip(), value)

