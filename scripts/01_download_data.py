#!/usr/bin/env python3
"""
01_download_data.py — Download raster datasets for the heat-risk analysis.

Downloads:
  1. GloUTCI-M August 2022 (1 km monthly UTCI) from Zenodo  (~270 MB ZIP)
  2. WorldPop 2024 China 100 m population — window extract via GDAL vsicurl
  3. PCNL 2021 harmonized nighttime light from Zenodo        (~94 MB)
  4. Gridded GDP 5-arcmin from Zenodo                        (~166 MB)
"""

import os
import sys
import time
import zipfile
from pathlib import Path

import requests

# Ensure config is importable
sys.path.insert(0, str(Path(__file__).resolve().parent))
from config import (
    UTCI_URL, POP_URL, NL_URL, GDP_URL,
    UTCI_DIR, POP_DIR, NL_DIR, GDP_DIR,
    SHANGHAI_BBOX,
)


# ── Helpers ────────────────────────────────────────────────────────────────

def download_file(url: str, dest: Path, desc: str = "",
                  max_retries: int = 3) -> Path:
    """Stream-download a file with progress and retry logic."""
    if dest.exists() and dest.stat().st_size > 1_000:
        print(f"  [skip] {dest.name} already exists ({dest.stat().st_size / 1e6:.1f} MB)")
        return dest

    for attempt in range(1, max_retries + 1):
        try:
            print(f"  [{attempt}/{max_retries}] Downloading {desc or dest.name} ...")
            resp = requests.get(url, stream=True, timeout=60)
            resp.raise_for_status()

            total = int(resp.headers.get("content-length", 0))
            downloaded = 0
            t0 = time.time()

            with open(dest, "wb") as f:
                for chunk in resp.iter_content(chunk_size=1 << 20):  # 1 MB
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total > 0:
                        pct = downloaded / total * 100
                        elapsed = time.time() - t0
                        speed = downloaded / elapsed / 1e6 if elapsed > 0 else 0
                        print(
                            f"\r    {downloaded / 1e6:8.1f} / {total / 1e6:.1f} MB "
                            f"({pct:5.1f}%)  {speed:.1f} MB/s",
                            end="", flush=True,
                        )
            print()  # newline after progress
            print(f"  ✓ Saved → {dest}  ({dest.stat().st_size / 1e6:.1f} MB)")
            return dest

        except Exception as e:
            print(f"\n  ✗ Attempt {attempt} failed: {e}")
            if dest.exists():
                dest.unlink()
            if attempt < max_retries:
                wait = 2 ** attempt
                print(f"    Retrying in {wait}s ...")
                time.sleep(wait)
            else:
                raise RuntimeError(f"Failed to download {url} after {max_retries} attempts") from e
    return dest  # unreachable but keeps linter happy


# ── 1. UTCI ────────────────────────────────────────────────────────────────

def download_utci() -> Path:
    """Download GloUTCI-M August 2022 ZIP and extract the GeoTIFF."""
    print("\n── UTCI (GloUTCI-M August 2022) ──")
    zip_path = UTCI_DIR / "GloUTCI-M_YEAR_2022_MONTH_08.zip"

    # Check if already extracted
    tif_candidates = list(UTCI_DIR.glob("*.tif"))
    if tif_candidates:
        print(f"  [skip] UTCI TIF already exists: {tif_candidates[0].name}")
        return tif_candidates[0]

    download_file(UTCI_URL, zip_path, desc="GloUTCI-M Aug 2022 ZIP")

    # Extract
    print("  Extracting ZIP ...")
    with zipfile.ZipFile(zip_path, "r") as zf:
        tif_names = [n for n in zf.namelist() if n.lower().endswith(".tif")]
        if not tif_names:
            raise RuntimeError("No .tif found inside UTCI ZIP")
        for name in tif_names:
            zf.extract(name, UTCI_DIR)
            print(f"  ✓ Extracted {name}")

    # Clean up ZIP to save disk
    zip_path.unlink()
    print("  ✓ Removed ZIP to save space")

    return UTCI_DIR / tif_names[0]


# ── 2. Population ─────────────────────────────────────────────────────────

def download_population() -> Path:
    """
    Extract Shanghai window from WorldPop 2024 CHN 100 m via GDAL vsicurl.
    Falls back to full download if vsicurl is unavailable.
    """
    print("\n── Population (WorldPop 2024 CHN 100 m) ──")
    out_path = POP_DIR / "shanghai_pop_2024_100m.tif"

    if out_path.exists() and out_path.stat().st_size > 1_000:
        print(f"  [skip] {out_path.name} already exists ({out_path.stat().st_size / 1e6:.1f} MB)")
        return out_path

    xmin, ymin, xmax, ymax = SHANGHAI_BBOX
    # Add a small buffer for reprojection edge effects
    buf = 0.1
    projwin = f"{xmin - buf} {ymax + buf} {xmax + buf} {ymin - buf}"

    # Try GDAL vsicurl (transfers only needed bytes)
    print("  Attempting GDAL vsicurl window extract ...")
    vsicurl_url = f"/vsicurl/{POP_URL}"
    cmd = (
        f'gdal_translate -projwin {projwin} '
        f'-co COMPRESS=LZW -co TILED=YES '
        f'"{vsicurl_url}" "{out_path}"'
    )
    print(f"  → {cmd}")
    rc = os.system(cmd)

    if rc == 0 and out_path.exists() and out_path.stat().st_size > 1_000:
        print(f"  ✓ vsicurl extract succeeded ({out_path.stat().st_size / 1e6:.1f} MB)")
        return out_path

    # Fallback: full download
    print("  vsicurl failed — falling back to full download ...")
    full_path = POP_DIR / "chn_pop_2024_UC_100m_R2024A_v1.tif"
    download_file(POP_URL, full_path, desc="WorldPop CHN 100m (5.4 GB)")

    # Clip with gdal_translate
    cmd = (
        f'gdal_translate -projwin {projwin} '
        f'-co COMPRESS=LZW -co TILED=YES '
        f'"{full_path}" "{out_path}"'
    )
    os.system(cmd)
    print(f"  ✓ Clipped to Shanghai ({out_path.stat().st_size / 1e6:.1f} MB)")
    return out_path


# ── 3. Nightlight ─────────────────────────────────────────────────────────

def download_nightlight() -> Path:
    """Download PCNL 2021 harmonized nighttime light."""
    print("\n── Nightlight (PCNL 2021) ──")
    dest = NL_DIR / "PCNL2021.tif"
    download_file(NL_URL, dest, desc="PCNL 2021 nightlight")
    return dest


# ── 4. GDP ────────────────────────────────────────────────────────────────

def download_gdp() -> Path:
    """Download gridded GDP total at 5-arcmin resolution."""
    print("\n── GDP (5-arcmin gridded, 1990-2022) ──")
    dest = GDP_DIR / "rast_gdpTot_1990_2022_5arcmin.tif"
    download_file(GDP_URL, dest, desc="GDP 5-arcmin")
    return dest


# ── Main ──────────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("STEP 1: Data Download")
    print("=" * 60)

    paths = {}
    paths["utci"] = download_utci()
    paths["population"] = download_population()
    paths["nightlight"] = download_nightlight()
    paths["gdp"] = download_gdp()

    print("\n" + "=" * 60)
    print("Download summary:")
    for name, p in paths.items():
        sz = p.stat().st_size / 1e6 if p.exists() else 0
        print(f"  {name:15s} → {p}  ({sz:.1f} MB)")
    print("=" * 60)

    return paths


if __name__ == "__main__":
    main()
