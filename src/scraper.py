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

# The related-materials page returns ALL resources (including .xlsx),
# with the filename in the `title=` attribute.
# The catalog page returns only ZIP/PDF, with the filename in the URL.
# Use the related-materials page so we get everything, and filter in code.
NBS_URL = "https://microdata.nigerianstat.gov.ng/index.php/catalog/157/related-materials"
DEFAULT_SAVE_DIR = os.getenv("SAVE_DIR", "/data/nbs_reports")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

# Download these file types. Add ".xlsx" here if you also want the tables.
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
    """
    Collect (absolute_url, filename) pairs from BOTH page layouts:

      * catalog page:   href=".../download/1424/PMS_Report_MAY_2026.zip"
                        -> filename from URL path

      * related-materials page:
                        href=".../download/1424"
                        title="PMS_Report_MAY_2026.zip"
                        -> filename from the title attribute
    """
    soup = BeautifulSoup(html, "html.parser")
    seen, results = set(), []

    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "/download/" not in href.lower():
            continue

        full = href if href.startswith("http") else \
            "https://microdata.nigerianstat.gov.ng" + href

        # Try the URL path first, then the title attribute.
        path_name = _safe_name(os.path.basename(urlparse(full).path))
        title_name = _safe_name(a.get("title", ""))

        fname = None
        for candidate in (path_name, title_name):
            if candidate and candidate.lower().endswith(ALLOWED_EXTS):
                fname = candidate
                break

        if not fname:
            # Could be an xlsx on the related-materials page, or a bare
            # /download/1424 with no title= — skip.
            continue

        # De-dupe by download ID (the number in the URL), not by full URL,
        # so the same resource appearing twice on the page is only fetched once.
        m = re.search(r"/download/(\d+)", full)
        key = m.group(1) if m else full
        if key in seen:
            continue
        seen.add(key)
        results.append((full, fname))

    return results


def download_reports(save_dir: str = DEFAULT_SAVE_DIR) -> dict:
    os.makedirs(save_dir, exist_ok=True)

    print(f"🌐 Listing URL: {NBS_URL}", file=sys.stderr)
    try:
        r = requests.get(NBS_URL, headers=HEADERS, timeout=30)
        r.raise_for_status()
    except Exception as e:
        print(f"Downloaded 0 new files to {save_dir}")
        return {"error": f"portal fetch failed: {e}", "count": 0,
                "files": [], "save_dir": save_dir}

    html = r.text
    print(f"📄 Received {len(html)} bytes of HTML", file=sys.stderr)

    links = collect_download_links(html)
    print(f"🔗 {len(links)} unique downloadable links", file=sys.stderr)

    downloaded = []
    for url, fname in links:
        target = os.path.join(save_dir, fname)
        try:
            print(f"⬇️  {fname}", file=sys.stderr)
            with requests.get(url, headers=HEADERS, timeout=120,
                              stream=True, allow_redirects=True) as resp:
                resp.raise_for_status()
                with tempfile.NamedTemporaryFile(
                    dir=save_dir, suffix=".part", delete=False
                ) as tmp:
                    for chunk in resp.iter_content(chunk_size=1 << 15):
                        if chunk:
                            tmp.write(chunk)
                    tmp_path = tmp.name
            os.replace(tmp_path, target)

            if fname.lower().endswith(".zip"):
                print(f"📦 Extracting {fname}", file=sys.stderr)
                pdfs = _extract_zip_pdfs(target, save_dir)
                downloaded.extend(pdfs)
                os.remove(target)
            else:
                downloaded.append(target)
        except Exception as e:
            print(f"❌ {fname}: {e}", file=sys.stderr)

    print(f"Downloaded {len(downloaded)} new files to {save_dir}")
    return {"count": len(downloaded), "files": downloaded, "save_dir": save_dir}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--save-dir", default=DEFAULT_SAVE_DIR)
    args = ap.parse_args()

    result = download_reports(args.save_dir)
    print(json.dumps(result))


if __name__ == "__main__":
    main()