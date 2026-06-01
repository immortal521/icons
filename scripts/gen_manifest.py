#!/usr/bin/env python3

import hashlib
import json
import re
import sys
from pathlib import Path

PACKAGES_DIR = Path(sys.argv[1] if len(sys.argv) > 1 else "packages")

VARIANT_BY_FILE = {
    "monochrome.png": "monet",
    "recbg.png": "light",
    "recfg.png": "light",
    "rec_night.png": "dark",
    "mat.png": "mat",
}

VARIANT_ORDER = ("monet", "light", "dark", "mat")
SIZE_SUFFIX_RE = re.compile(r"^\d+x\d+$")


def normalize_name(name: str) -> str:
    stem = Path(name).stem
    parts = stem.split("_")
    if len(parts) >= 2 and SIZE_SUFFIX_RE.match(parts[-1]):
        stem = "_".join(parts[:-1])
    return f"{stem}.png"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(8192):
            digest.update(chunk)
    return digest.hexdigest()


def detect_variant(name: str):
    return VARIANT_BY_FILE.get(normalize_name(name))


def calc_version(pkg_dir: Path) -> str:
    parts = []
    for file_path in sorted(pkg_dir.iterdir(), key=lambda item: item.name):
        if file_path.is_file() and file_path.suffix == ".png" and file_path.name != "manifest.json":
            parts.append((file_path.name, sha256_file(file_path)))

    digest = hashlib.sha256()
    for name, sha in parts:
        digest.update(name.encode())
        digest.update(sha.encode())
    return digest.hexdigest()[:12] if parts else "0"


def build_entry(file_path: Path) -> dict:
    return {
        "file": file_path.name,
        "sha256": sha256_file(file_path),
        "size": file_path.stat().st_size,
    }


def sort_entries(entries: list[dict]) -> list[dict]:
    return sorted(entries, key=lambda item: item["file"])


def build_manifest(pkg_dir: Path):
    required = []
    variants = {name: [] for name in VARIANT_ORDER}
    count = 0

    for file_path in sorted(pkg_dir.iterdir(), key=lambda item: item.name):
        if not file_path.is_file():
            continue
        if file_path.name == "manifest.json" or file_path.suffix != ".png":
            continue

        count += 1
        entry = build_entry(file_path)
        variant = detect_variant(file_path.name)
        if variant:
            variants[variant].append(entry)
        else:
            required.append(entry)

    return {
        "version": calc_version(pkg_dir),
        "count": count,
        "required": sort_entries(required),
        "variants": {
            name: sort_entries(items) for name, items in variants.items() if items
        },
    }


def main():
    if not PACKAGES_DIR.exists():
        print("packages directory not found")
        return

    for pkg_dir in PACKAGES_DIR.iterdir():
        if not pkg_dir.is_dir():
            continue

        print(f"Generating manifest for {pkg_dir.name}")
        manifest = build_manifest(pkg_dir)

        out_file = pkg_dir / "manifest.json"
        with open(out_file, "w") as f:
            json.dump(manifest, f, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    main()
