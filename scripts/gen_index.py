#!/usr/bin/env python3
import hashlib
import json
import re
import sys
import time
from pathlib import Path

ROOT = Path(sys.argv[1] if len(sys.argv) > 1 else ".")
PACKAGES_DIR = ROOT / "packages"
REQUIRED_DIR = ROOT / "required"
OUTPUT = ROOT / "index.json"

VARIANT_BY_FILE = {
    "monochrome.png": "monet",
    "recbg.png": "light",
    "recfg.png": "light",
    "rec_night.png": "dark",
    "mat.png": "mat",
}

VARIANT_ORDER = ("monet", "light", "dark", "mat")
SIZE_SUFFIX_RE = re.compile(r"^\d+x\d+$")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(8192):
            digest.update(chunk)
    return digest.hexdigest()


def normalize_name(name: str) -> str:
    stem = Path(name).stem
    parts = stem.split("_")
    if len(parts) >= 2 and SIZE_SUFFIX_RE.match(parts[-1]):
        stem = "_".join(parts[:-1])
    return f"{stem}.png"


def detect_variant(name: str):
    return VARIANT_BY_FILE.get(normalize_name(name))


def build_file_entry(file_path: Path, relative_path: str) -> dict:
    return {
        "file": file_path.name,
        "path": relative_path,
        "sha256": sha256_file(file_path),
        "size": file_path.stat().st_size,
    }


def calc_version(entries: list[tuple[str, str]]) -> str:
    digest = hashlib.sha256()
    for key, value in sorted(entries):
        digest.update(key.encode())
        digest.update(value.encode())
    return digest.hexdigest()[:12]


def sort_entries(entries: list[dict]) -> list[dict]:
    return sorted(entries, key=lambda item: item["file"])


def build_package(pkg_dir: Path) -> dict:
    required = []
    variants = {name: [] for name in VARIANT_ORDER}
    version_parts = []
    total_files = 0

    for file_path in sorted(pkg_dir.iterdir(), key=lambda item: item.name):
        if not file_path.is_file() or file_path.suffix != ".png":
            continue

        total_files += 1
        entry = build_file_entry(file_path, f"packages/{pkg_dir.name}/{file_path.name}")
        version_parts.append((file_path.name, entry["sha256"]))

        variant = detect_variant(file_path.name)
        if variant:
            variants[variant].append(entry)
        else:
            required.append(entry)

    return {
        "path": f"packages/{pkg_dir.name}",
        "version": calc_version(version_parts) if version_parts else "0",
        "count": total_files,
        "required": sort_entries(required),
        "variants": {
            name: sort_entries(items) for name, items in variants.items() if items
        },
    }


def build_packages() -> dict:
    packages = {}
    if not PACKAGES_DIR.exists():
        return packages

    for pkg_dir in sorted(PACKAGES_DIR.iterdir(), key=lambda item: item.name):
        if pkg_dir.is_dir():
            packages[pkg_dir.name] = build_package(pkg_dir)

    return packages


def build_required_files() -> list[dict]:
    if not REQUIRED_DIR.exists():
        return []

    entries = []
    for file_path in sorted(REQUIRED_DIR.iterdir(), key=lambda item: item.name):
        if file_path.is_file():
            entries.append(build_file_entry(file_path, f"required/{file_path.name}"))
    return entries


def build_repo_version(packages: dict, required_files: list[dict]) -> str:
    parts = []
    for pkg_name, pkg_info in sorted(packages.items()):
        parts.append((f"pkg:{pkg_name}", pkg_info["version"]))
    for entry in required_files:
        parts.append((f"file:{entry['file']}", entry["sha256"]))
    return calc_version(parts) if parts else "0"


def main():
    packages = build_packages()
    required_files = build_required_files()

    index = {
        "repo_version": 2,
        "generated_at": int(time.time()),
        "version": build_repo_version(packages, required_files),
        "variant_definitions": {
            "monet": ["monochrome*.png"],
            "light": ["recbg*.png", "recfg*.png"],
            "dark": ["rec_night*.png"],
            "mat": ["mat*.png"],
        },
        "required_files": required_files,
        "packages": packages,
    }

    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(index, f, separators=(",", ":"), ensure_ascii=False)

    print(f"index.json generated at {OUTPUT}")


if __name__ == "__main__":
    main()
