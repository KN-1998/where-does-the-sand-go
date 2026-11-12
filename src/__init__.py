# -*- coding: utf-8 -*-
"""Where-Does-the-Sand-Go: model, experiments and figures (coder track).

Package layout (see handoff/CODER_SPEC.md §3)::

    src/sim/    numerical core (grid, model, storms, placements, accounting)
    src/exp/    experiment drivers (run_one, mc, sweep, E0-E7)
    src/viz/    figures F1-F8

The code is installed as an editable package (``pip install -e .``) so the
documented command ``python -m exp.run_one`` works from the repository root.
"""

__version__ = "0.1.0"
