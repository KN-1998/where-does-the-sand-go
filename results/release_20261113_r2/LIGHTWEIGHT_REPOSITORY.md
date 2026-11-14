# Frozen R2 evidence in the repository

Restored from the verified `review_handoff_20261113_r2.zip` Release asset
(SHA-256 `9ab3aea09695abcc03d578e338faf27f56eacc52175d789d0fb06d64ef35252f`).
The original scientific source SHA-256 remains
`5ff6da62fbd11a0d481f990140883a2640cef1b911370f4521598e56ef5dd2be`.
The original archive verification receipt is `original_archive_verification.json`.

This directory retains all CSV, JSON, Markdown and log evidence and all figure
PNG/PDF pairs from that archive. YAML replay configurations are also retained
because `tools/check_release.py` requires them. Field arrays, binary payloads,
and disposable JSONL caches remain in the original Release assets.
Byte-sensitive result evidence and MATLAB plotting source use `-text` Git
attributes so a Windows clean clone preserves the recorded SHA-256 values.

Run `python tools/check_release.py` from the repository root. The checker also
locates its default release and source files when invoked from another directory.

`layout_quantiles.csv` is a supplementary extraction from the same 1,000 paired
S1 seeds per layout, reproduced with `python tools/export_layout_quantiles.py`.
Its P10/P50/P90 values use NumPy's linear quantile method and `E_w` units m*yr.
This extraction changes no frozen R2 simulation outcomes.
