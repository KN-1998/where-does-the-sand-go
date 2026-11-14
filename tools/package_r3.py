"""Build the R3 supplement, retaining the exact frozen R2 source bytes.

Inclusion is deliberately explicit: source/input/documentation directories,
root Markdown/version metadata, lightweight R2 results, and caliber_R2 outputs.
Only the two deterministic diagnostic field matrices are retained. Other result
trees, Git internals, caches and large reference/GIS collections are excluded.
"""

import argparse
import hashlib
import json
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile


ROOT = Path(__file__).resolve().parents[1]
RELEASE = Path("results/release_20261113_r2")
CALIBER = Path("results/caliber_R2")
SOURCE_DIRS = (
    "src", "tests", "configs", "modeling", "tools", "matlab", "handoff",
    "data/raw", "problem", "meta", "ledger",
)
TEXT_SUFFIXES = {".py", ".md", ".yaml", ".yml", ".json", ".csv", ".txt", ".log", ".m", ".toml"}
RESULT_SUFFIXES = {".csv", ".json", ".md", ".log", ".yaml", ".yml"}


def source_sha256():
    digest = hashlib.sha256()
    for path in sorted((ROOT / "src").rglob("*.py")):
        digest.update(path.relative_to(ROOT / "src").as_posix().encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def safe_file(path):
    """Reject symlinks and runtime/private paths before applying inclusion rules."""
    relative = path.relative_to(ROOT)
    return (path.is_file() and not path.is_symlink() and
            not {".git", "__pycache__", ".pytest_cache", ".venv"}.intersection(relative.parts) and
            path.resolve().is_relative_to(ROOT))


def included_paths():
    paths = set()
    for directory in SOURCE_DIRS:
        for path in (ROOT / directory).rglob("*"):
            if safe_file(path) and path.suffix.lower() in TEXT_SUFFIXES:
                paths.add(path)
    paths.update(path for path in ROOT.glob("*.md") if safe_file(path))
    for name in ("requirements.txt", "CODE_VERSION.json", "CODE_VERSION_R3.json",
                 "HANDOFF_VERIFICATION_R3.json", ".gitattributes", ".gitignore"):
        path = ROOT / name
        if safe_file(path):
            paths.add(path)
    # These two small, existing inputs support the historical diagnostic and
    # problem statement. Do not recursively include arbitrary raw binaries.
    for name in ("data/raw/Hatteras_Transects.dbf",
                 "problem/2027_MCM_A_Where_Does_the_Sand_Go_Template_Style.pdf"):
        path = ROOT / name
        if safe_file(path) and path.stat().st_size <= 2 * 1024 * 1024:
            paths.add(path)
    for path in (ROOT / "资料").rglob("*.md"):
        if safe_file(path):
            paths.add(path)
    for path in (ROOT / RELEASE).rglob("*"):
        if not safe_file(path):
            continue
        relative = path.relative_to(ROOT / RELEASE)
        if path.suffix.lower() in RESULT_SUFFIXES:
            paths.add(path)
        elif (relative.parent == Path("figures") and path.suffix.lower() in {".png", ".pdf"}
              and path.stat().st_size <= 2 * 1024 * 1024):
            paths.add(path)
    for path in (ROOT / CALIBER).rglob("*"):
        if not safe_file(path):
            continue
        relative = path.relative_to(ROOT / CALIBER)
        if path.suffix.lower() in RESULT_SUFFIXES:
            paths.add(path)
        elif relative in {Path("A_det/fields.npz"), Path("B_det/fields.npz")}:
            paths.add(path)
    return sorted(paths)


def validate(paths):
    code = json.loads((ROOT / "CODE_VERSION.json").read_text(encoding="utf-8"))
    fingerprint = source_sha256()
    if fingerprint != code["src_sha256"]:
        raise RuntimeError("Frozen R2 source differs from CODE_VERSION.json")
    for name in ("audit.json", "completeness.json"):
        result = json.loads((ROOT / RELEASE / name).read_text(encoding="utf-8"))
        if result["status"] != "PASS":
            raise RuntimeError(f"R2 {name} is not PASS")
    complete = json.loads((ROOT / RELEASE / "completeness.json").read_text(encoding="utf-8"))
    if complete["code_sha256"] != fingerprint:
        raise RuntimeError("R2 result/source identity mismatch")
    summary = json.loads((ROOT / CALIBER / "summary.json").read_text(encoding="utf-8"))
    if summary["source_sha256"] != fingerprint:
        raise RuntimeError("Diagnostic result/source identity mismatch")
    if any(summary[group]["n"] < 200 for group in ("A_nostorm", "B_storm")):
        raise RuntimeError("Diagnostic requires at least 200 paired realizations")
    if not 0 <= summary["residual_rel_max"] < 1e-6:
        raise RuntimeError("Diagnostic mass balance failed")
    if summary["A_nostorm"]["retreat_mean"] >= summary["B_storm"]["retreat_mean"]:
        raise RuntimeError("Diagnostic storm/no-storm ordering failed")
    if sum(path.name == "completeness.json" for path in paths) != 1:
        raise RuntimeError("Package must contain exactly one frozen release completeness report")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default="dist/supplement_handoff_20261114_r3.zip")
    args = parser.parse_args()
    paths = included_paths()
    validate(paths)
    out = Path(args.out)
    if not out.is_absolute():
        out = ROOT / out
    out = out.resolve()
    if not out.is_relative_to(ROOT / "dist") or out.suffix.lower() != ".zip":
        parser.error("--out must name a .zip within this repository's dist directory")
    out.parent.mkdir(parents=True, exist_ok=True)
    manifest = {}
    with ZipFile(out, "w", ZIP_DEFLATED, compresslevel=6) as archive:
        for path in paths:
            name = path.relative_to(ROOT).as_posix()
            payload = path.read_bytes()
            manifest[name] = hashlib.sha256(payload).hexdigest()
            archive.writestr(name, payload)
        archive.writestr("PACKAGE_MANIFEST.json", json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
        archive.writestr("LIGHTWEIGHT_README.md", (
            "# R3 supplemental handoff\n\n"
            "Includes the frozen R2 scientific source, inputs, tools, tests and documentation; "
            "R2 CSV/JSON/Markdown/log/YAML results and figure PNG/PDF pairs up to 2 MiB; "
            "and the paired caliber_R2 diagnostics, including A_det/B_det fields.npz. "
            "The two small existing transect DBF/problem PDF inputs are included; "
            "other result trees, full R2 field matrices, large raw collections and caches are omitted. "
            "PACKAGE_MANIFEST.json records SHA-256 of every payload file.\n\n"
            "Verify transport, payloads and frozen source:\n\n"
            "```powershell\n"
            f"python tools/verify_handoff.py dist/{out.name} --out dist/HANDOFF_VERIFICATION_R3.json\n"
            "```\n"
        ))
    digest = hashlib.sha256(out.read_bytes()).hexdigest()
    out.with_suffix(".sha256").write_text(f"{digest}  {out.name}\n", encoding="utf-8")
    print(json.dumps({"archive": str(out), "bytes": out.stat().st_size,
                      "payload_files": len(manifest), "sha256": digest,
                      "src_sha256": source_sha256()}, indent=2))


if __name__ == "__main__":
    main()
