from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Dict

import requests
from rich.progress import track

SAMPLE = {
    "name": "Mao Qianren",
    "institution": "Zhongguancun Laboratory, Beijing, P.R.China.",
    "reviewed": "3",
    "recognized": "1",
    "percentage": "33",
}

DATA_DIR = Path("data/raw")
DATA_DIR.mkdir(parents=True, exist_ok=True)

CONFIG = Path("config/data_sources.toml")


def load_sources() -> Dict[str, str]:
    import tomllib

    with CONFIG.open("rb") as f:
        data = tomllib.load(f)
    return data.get("sources", {})


def fetch(name: str, url: str) -> None:
    # Create a new session for each request to avoid SSL context issues in threads
    with requests.Session() as session:
        resp = session.get(url, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        if not isinstance(data, list):
            raise ValueError(f"Unexpected payload for {name}")
        for entry in data:
            for key in SAMPLE:
                if key not in entry:
                    raise ValueError(f"Missing {key} in {name}")
        out = DATA_DIR / f"{name}.json"
        with out.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)


def download_all() -> None:
    sources = load_sources()
    print(f"Downloading {len(sources)} data files...")
    
    # Try concurrent downloads first, fall back to sequential if SSL issues occur
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:  # Reduced workers
            list(
                track(
                    pool.map(lambda kv: fetch(*kv), sources.items()),
                    total=len(sources),
                    description="Downloading (concurrent)",
                )
            )
    except Exception as e:
        if "SSL" in str(e) or "ssl" in str(e).lower():
            print(f"Concurrent download failed with SSL error, falling back to sequential downloads...")
            # Fall back to sequential downloads
            for name, url in track(sources.items(), description="Downloading (sequential)"):
                try:
                    fetch(name, url)
                except Exception as seq_e:
                    print(f"Failed to download {name}: {seq_e}")
                    raise
        else:
            raise


if __name__ == "__main__":
    download_all()
