#!/usr/bin/env python3
import os
import re
import sys
import json
import zipfile
import tempfile
import argparse
from urllib.parse import urlparse, unquote

import requests
from bs4 import BeautifulSoup

try:
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
except Exception:
    pass

NBS_URL = "https://microdata.nigerianstat.gov.ng/index.php/catalog/157/related-materials"
DEFAULT_SAVE_DIR = os.getenv("SAVE_DIR", "/data/nbs_reports")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

ALLOWED_EXTS = (".pdf", ".zip")


def _safe_name(name: str) -> str:
    name = unquote(name or "")
    name = re.sub(r'[\\/:*?"<>|]', "_", name)
    return name.strip()


def _extract_zip_pdfs(zip_path: str, save_dir: str) -> list:
    extracted = []
    with zipfile.ZipFile(zip_path, "r") as zf:
        for info in zf.infolist():
            if info.is_dir():
                continue
            if not info.filename.lower().endswith(".pdf"):
                continue
            base = os.path.basename(info.filename)
            target = os.path.join(save_dir, base)
            if os.path.exists(target):
                stem, ext = os.path.splitext(base)
                i = 1
                while os.path.exists(target):
                    target = os.path.join(save_dir, f"{stem}_{i}{ext}")
                    i += 1
            with zf.open(info) as src, open(target, "wb") as dst:
                dst.write(src.read())
            extracted.append(target)
    return extracted


def collect_download_links(html: str) -> list:
    soup = BeautifulSoup(html, "html.parser")
    seen, results = set(), []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "/download/" not in href.lower():
            continue
        full = href if href.startswith("http") else \
            "https://microdata.nigerianstat.gov.ng" + href
        path_name = _safe_name(os.path.basename(urlparse(full).path))
        title_name = _safe_name(a.get("title", ""))
        fname = None
        for candidate in (path_name, title_name):
            if candidate and candidate.lower().endswith(ALLOWED_EXTS):
                fname = candidate
                break
        if not fname:
            continue
        m = re.search(r"/download/(\d+)", full)
        key = m.group(1) if m else full
        if key in seen:
            continue
        seen.add(key)
        results.append((full, fname))
    return results


def _fetch(session, url, dest):
    with session.get(url, timeout=180, stream=True, allow_redirects=True) as resp:
        resp.raise_for_status()
        with tempfile.NamedTemporaryFile(dir=os.path.dirname(dest),
                                         suffix=".part", delete=False) as tmp:
            for chunk in resp.iter_content(chunk_size=1 << 16):
                if chunk:
                    tmp.write(chunk)
            tmp_path = tmp.name
    os.replace(tmp_path, dest)


def _resource_pdfs_on_disk(fname: str, save_dir: str) -> list:
    """
    For a ZIP resource named PMS_Report_MAY_2026.zip, we cannot know
    which PDFs it contained. But if *any* file matching the report stem
    is on disk (e.g. PMS_Report_MAY_2026.pdf or similar), treat it as
    already-downloaded so a scheduled run does not re-fetch it.
    A plain .pdf resource is its own on-disk artifact.
    """
    if fname.lower().endswith(".pdf"):
        target = os.path.join(save_dir, fname)
        return [target] if os.path.exists(target) and os.path.getsize(target) > 0 else []

    # ZIP: try the common naming — same stem with .pdf extension
    stem = os.path.splitext(fname)[0]
    for ext in (".pdf", ".PDF"):
        candidate = os.path.join(save_dir, stem + ext)
        if os.path.exists(candidate) and os.path.getsize(candidate) > 0:
            return [candidate]
    return []


def run(save_dir: str, probe: int) -> dict:
    os.makedirs(save_dir, exist_ok=True)

    session = requests.Session()
    session.headers.update(HEADERS)

    print(f"🌐 {NBS_URL}", file=sys.stderr)
    try:
        r = session.get(NBS_URL, timeout=30)
        r.raise_for_status()
    except Exception as e:
        print(f"Downloaded 0 new files to {save_dir}")
        return {"error": f"portal fetch failed: {e}", "count": 0,
                "files": [], "save_dir": save_dir}

    links = collect_download_links(r.text)
    print(f"🔗 {len(links)} downloadable resources", file=sys.stderr)
    if not links:
        print(f"Downloaded 0 new files to {save_dir}")
        return {"count": 0, "files": [], "save_dir": save_dir,
                "note": "no links parsed"}

    probes = links[:probe]
    print(f"🔎 Probing top {len(probes)} resource(s)", file=sys.stderr)

    downloaded, skipped, tried = [], 0, []
    for url, fname in probes:
        tried.append(fname)

        # Case A: resource is already on disk from a previous run.
        existing = _resource_pdfs_on_disk(fname, save_dir)
        if existing:
            skipped += 1
            print(f"⏭️  Already have: {fname}", file=sys.stderr)
            break  # top of page is already covered → done

        # Case B: try to download this resource.
        target = os.path.join(save_dir, fname)
        try:
            print(f"⬇️  {fname}", file=sys.stderr)
            _fetch(session, url, target)

            if fname.lower().endswith(".zip"):
                pdfs = _extract_zip_pdfs(target, save_dir)
                os.remove(target)
            else:
                pdfs = [target]

            if not pdfs:
                print(f"⚠️  {fname} produced 0 PDFs — trying next", file=sys.stderr)
                continue  # broken resource; probe the next one

            downloaded.extend(pdfs)
            print(f"✅ {fname} → {len(pdfs)} PDF(s)", file=sys.stderr)
            break  # we got a valid report → stop
        except Exception as e:
            print(f"❌ {fname}: {e} — trying next", file=sys.stderr)
            continue  # broken download; probe the next one

    # A "success" is: we have ≥1 new PDF, OR the top-of-page resource was
    # already on disk from a prior run.
    if downloaded or skipped:
        print(f"Downloaded {len(downloaded)} new files to {save_dir}")
        return {"count": len(downloaded), "skipped": skipped,
                "tried": tried, "files": downloaded,
                "save_dir": save_dir}
    else:
        print(f"Downloaded 0 new files to {save_dir}")
        return {"count": 0, "skipped": 0, "tried": tried,
                "files": [], "save_dir": save_dir}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--save-dir", default=DEFAULT_SAVE_DIR)
    ap.add_argument("--probe", type=int, default=4,
                    help="How many of the newest resources to try if the top "
                         "one is broken or already present (default: 4)")
    args = ap.parse_args()

    result = run(args.save_dir, probe=args.probe)
    print(json.dumps(result))


if __name__ == "__main__":
    main()