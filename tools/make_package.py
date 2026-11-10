#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""tools/make_package.py — 生成可交付包：源码 zip + git bundle + SHA256（整改 C4）

用法： python tools/make_package.py [--tag r1_20261110]
产物： dist/MCM2027A_<tag>_<commit>.zip / .bundle / SHA256SUMS_<tag>.txt / COMMIT.txt
说明： zip 由 `git archive HEAD` 生成，只含**被跟踪**的文件；
      被 .gitignore 排除的原始 PDF/GIS 不在包内（见 README「克隆后你拿不到什么」）。
"""
import argparse, hashlib, os, subprocess, sys, datetime

root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
dist = os.path.join(root, "dist")
os.makedirs(dist, exist_ok=True)

def git(*a):
    return subprocess.check_output(["git", *a], cwd=root, text=True).strip()

def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()

ap = argparse.ArgumentParser()
ap.add_argument("--tag", default=datetime.date.today().strftime("%Y%m%d"))
args = ap.parse_args()

commit = git("rev-parse", "HEAD")
short = commit[:7]
name = f"MCM2027A_{args.tag}_{short}"
zip_path = os.path.join(dist, name + ".zip")
bundle_path = os.path.join(dist, name + ".bundle")

subprocess.check_call(["git", "archive", "--format=zip",
                       f"--prefix=MCM2027A/", "-o", zip_path, "HEAD"], cwd=root)
subprocess.check_call(["git", "bundle", "create", bundle_path, "--all"], cwd=root)

sums = [f"{sha256(zip_path)}  {os.path.basename(zip_path)}",
        f"{sha256(bundle_path)}  {os.path.basename(bundle_path)}"]
sums_path = os.path.join(dist, f"SHA256SUMS_{args.tag}.txt")
with open(sums_path, "w", encoding="utf-8") as f:
    f.write("\n".join(sums) + "\n")
with open(os.path.join(dist, "COMMIT.txt"), "w", encoding="utf-8") as f:
    f.write(f"COMMIT {commit}\nBRANCH {git('rev-parse','--abbrev-ref','HEAD')}\n")
print("\n".join(sums))
for p in (zip_path, bundle_path, sums_path):
    print(f"{os.path.basename(p):48s} {os.path.getsize(p)/1e6:8.2f} MB")
