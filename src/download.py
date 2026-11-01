"""Download the DataCo Smart Supply Chain CSV (Mendeley Data, CC BY 4.0) to data/raw/.

The file is about 96 MB, so it is not stored in git. The checksum below is the
file downloaded on 1 Nov 2026 (version 5 of the dataset). A different checksum
means the source changed; the script stops so numbers are not silently different.
"""
import hashlib
import pathlib
import sys

import requests

ROOT = pathlib.Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "DataCoSupplyChainDataset.csv"
URL = ("https://data.mendeley.com/public-files/datasets/8gx2fvg2k6/files/"
       "72784be5-36d3-44fe-b75d-0edbf1999f65/file_downloaded")
SHA256 = "fa6d022ed437155e1a2f0378710602848703c8a7f203f7ff5d77805bf8480aa6"
EXPECTED_ROWS = 180_519


def sha256(path: pathlib.Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> None:
    RAW.parent.mkdir(parents=True, exist_ok=True)
    if RAW.exists() and sha256(RAW) == SHA256:
        print(f"already downloaded: {RAW.relative_to(ROOT)}")
    else:
        print(f"downloading {URL}")
        tmp = RAW.with_suffix(".part")
        with requests.get(URL, stream=True, timeout=120) as r:
            r.raise_for_status()
            with tmp.open("wb") as f:
                for chunk in r.iter_content(1 << 20):
                    f.write(chunk)
        tmp.replace(RAW)
    digest = sha256(RAW)
    if digest != SHA256:
        sys.exit(f"checksum mismatch: got {digest}, expected {SHA256}")
    with RAW.open("rb") as f:
        rows = sum(1 for _ in f) - 1
    if rows != EXPECTED_ROWS:
        sys.exit(f"expected {EXPECTED_ROWS} data rows, got {rows}")
    print(f"ok: {rows:,} rows, {RAW.stat().st_size / 1e6:.1f} MB, sha256 {digest[:12]}...")


if __name__ == "__main__":
    main()
