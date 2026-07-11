from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent.parent
VERSION_PATH = BASE_DIR / "VERSION"


def get_version() -> str:
    if not VERSION_PATH.exists():
        return "0.0.0"
    return VERSION_PATH.read_text(encoding="utf-8").strip()
