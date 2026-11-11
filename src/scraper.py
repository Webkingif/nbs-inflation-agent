import os
import requests
from bs4 import BeautifulSoup

NBS_URL = "https://microdata.nigerianstat.gov.ng/index.php/catalog/157/related-materials"

def check_and_download_nbs_reports(save_dir="samples"):
    os.makedirs(save_dir, exist_ok=True)
    headers = {"User-Agent": "Mozilla/5.0"}
    response = requests.get(NBS_URL, headers=headers)
    
    if response.status_code != 200:
        print(f"Failed to reach portal, status: {response.status_code}")
        return []

    soup = BeautifulSoup(response.text, 'html.parser')
    downloaded_files = []

    for link in soup.find_all('a', href=True):
        href = link['href']
        text = link.get_text(strip=True).lower()
        if "download" in href and any(k in text for k in ["pms", "diesel", "transport"]):
            full_url = href if href.startswith("http") else f"https://microdata.nigerianstat.gov.ng{href}"
            file_name = os.path.basename(full_url) + ".pdf"
            target_path = os.path.join(save_dir, file_name)
            
            if not os.path.exists(target_path):
                print(f"Downloading new report: {file_name}")
                res = requests.get(full_url)
                with open(target_path, 'wb') as f:
                    f.write(res.content)
                downloaded_files.append(target_path)
                
    return downloaded_files

if __name__ == "__main__":
    files = check_and_download_nbs_reports()
    print(f"Downloaded {len(files)} new files.")