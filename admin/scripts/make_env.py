"""Dev helper: generate repo-root .env from .env.example with fresh secrets."""
import secrets
from pathlib import Path

from cryptography.fernet import Fernet

root = Path(__file__).resolve().parents[2]
src = root / ".env.example"
dst = root / ".env"

lines = []
for line in src.read_text(encoding="utf-8").splitlines():
    if line.startswith("LINK_ENCRYPTION_KEY="):
        line = f"LINK_ENCRYPTION_KEY={Fernet.generate_key().decode()}"
    elif line.startswith("ADMIN_PASSWORD="):
        line = "ADMIN_PASSWORD=admin123"
    elif line.startswith("JWT_SECRET="):
        line = f"JWT_SECRET={secrets.token_hex(32)}"
    lines.append(line)

dst.write_text("\n".join(lines) + "\n", encoding="utf-8")
print(f"written {dst}")
