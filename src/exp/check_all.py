# -*- coding: utf-8 -*-
"""Single acceptance gate for the coder track.

Runs, in order:

1. ``modeling/sanity/discrete_contract.py``  (contract reference, must print ALL PASS)
2. ``pytest tests``                           (T1-T13, 17 tests)
3. ``tools/verify_contract.py``               (document/parameter consistency, 67 checks)
4. ``python -m exp.audit``                    (result artefacts, ledger closure, figures)

Exit code 0 iff all four pass.  Usage::

    python -m exp.check_all
"""
from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path
from typing import List, Tuple

REPO_ROOT = Path(__file__).resolve().parents[2]


def _run(name: str, args: List[str]) -> Tuple[str, bool, float, str]:
    t0 = time.time()
    proc = subprocess.run([sys.executable, *args], cwd=REPO_ROOT,
                          capture_output=True, text=True)
    elapsed = time.time() - t0
    tail = "\n".join((proc.stdout or "").strip().splitlines()[-3:])
    return name, proc.returncode == 0, elapsed, tail


def main(argv=None) -> int:
    steps = [
        ("reference prototype", ["modeling/sanity/discrete_contract.py"]),
        ("pytest T1-T13", ["-m", "pytest", "tests", "-q"]),
        ("contract verifier", ["tools/verify_contract.py"]),
        ("result audit", ["-m", "exp.audit"]),
    ]
    results = [_run(*step) for step in steps]
    ok = True
    for name, passed, elapsed, tail in results:
        ok &= passed
        print(f"[{'PASS' if passed else 'FAIL'}] {name:22s} {elapsed:6.1f}s  {tail}")
    print(f"===== check_all: {'ALL PASS' if ok else 'FAILED'} =====")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
