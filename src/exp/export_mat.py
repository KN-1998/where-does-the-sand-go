"""Convert saved NumPy field arrays to MATLAB .mat inputs for plotting."""

import argparse
from pathlib import Path

import numpy as np
from scipy.io import savemat


def export(root):
    root = Path(root)
    count = 0
    for npz_path in root.rglob("fields.npz"):
        fields = np.load(npz_path)
        payload = {key: fields[key] for key in fields.files}
        savemat(npz_path.with_name("fields.mat"), payload, do_compression=True)
        count += 1
    print(f"wrote MATLAB field inputs: {count}")


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True)
    args = parser.parse_args(argv)
    export(args.root)


if __name__ == "__main__":
    main()
