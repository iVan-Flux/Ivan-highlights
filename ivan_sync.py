import requests
import json
import base64
import os
from datetime import datetime, timedelta
from Crypto.Cipher import AES

# 🔐 Load Credentials from GitHub Secrets
IVAN_TOKEN = os.getenv("IVAN_TOKEN") 
APP_PASSWORD = os.getenv("APP_PASSWORD")
REPO_OWNER = "iVan-Flux"
TARGET_REPO = "iVan-Xtra" # Your private storage repository

# Firebase Credentials
FIREBASE_API_KEY = os.getenv("FIREBASE_API_KEY")
PROJECT_NUMBER = os.getenv("PROJECT_NUMBER")
FIREBASE_FID = os.getenv("FIREBASE_FID")
FIREBASE_APP_ID = os.getenv("FIREBASE_APP_ID")
PACKAGE_NAME = os.getenv("PACKAGE_NAME")

class iVanHighlightsProcessor:
    def _generate_aes_key_iv(self, s: str):
        # Algorithm to generate the AES Key and IV from the APP_PASSWORD
        CHARSET = b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+!@#$%&="
        u32 = lambda x: x & 0xFFFFFFFF
        data = s.encode("utf-8"); n = len(data); u = 0x811c9dc5
        for b in data: u = u32((u ^ b) * 0x1000193)
        key = bytearray(16)
        for i in range(16):
            b = data[i % n]; u = u32(u * 0x1f + (i ^ b)); key[i] = CHARSET[u % len(CHARSET)]
        u = 0x811c832a
        for b in data: u = u32((u ^ b) * 0x1000193)
        iv = bytearray(16); idx = acc = 0
        while idx != 0x30:
            b = data[idx % n]; u = u32(u * 0x1d + (acc ^ b)); iv[idx // 3] = CHARSET[u % len(CHARSET)]; idx += 3; acc = u32(acc + 7)
        return bytes(key), bytes(iv)

    def _decrypt_data(self, b64_data: str):
        # Decrypt AES-CBC encrypted Base64 data from the server
        try:
            if not b64_data: return ""
            ct = base64.b64decode(b64_data)
            key, iv = self._generate_aes_key_iv(APP_PASSWORD)
            cipher = AES.new(key, AES.MODE_CBC, iv)
            pt = cipher.decrypt(ct); pad = pt[-1]
            if 1 <= pad <= 16: pt = pt[:-pad]
            return pt.decode("utf-8", errors="replace")
        except: return ""

    def apply_corrections(self, channels):
        # 🛠️ Applying the 7 solid rules for DRM Key correction (J, $, l, Q, W, ), Z)
        correction_map = {'J': 'a', '$': '5', 'l': '2', 'Q': 'b', 'W': 'f', ')': '2', 'Z': 'a'}
        if not isinstance(channels, list): return []
        for ch in channels:
            api_val = ch.get("api", "")
            if api_val:
                # Attempt to decode Base64 API keys if they exist
                try:
                    if len(api_val) > 20:
                        decoded = base64.b64decode(api_val).decode('utf-8')
                        if ":" in decoded: api_val = decoded
                except: pass
                # Replace incorrect characters with correct Hex values
                for wrong, right in correction_map.items():
                    api_val = api_val.replace(wrong, right)
                ch["api"] = api_val
            # Ensure the stream link remains 100% Raw
            ch["link"] = ch.get("link", "") 
        return channels

    def get_api_url(self):
        # Dynamically fetch the current API URL from Firebase Remote Config
        try:
            r = requests.post(f"https://firebaseinstallations.googleapis.com/v1/projects/sportzx-7cc3f/installations", json={"fid": FIREBASE_FID, "appId": FIREBASE_APP_ID, "authVersion": "FIS_v2", "sdkVersion": "a:18.0.0"}, headers={"x-goog-api-key": FIREBASE_API_KEY}, timeout=10)
            auth_token = r.json()["authToken"]["token"]
            r2 = requests.post(f"https://firebaseremoteconfig.googleapis.com/v1/projects/{PROJECT_NUMBER}/namespaces/firebase:fetch", json={"appVersion": "2.1", "appInstanceId": FIREBASE_FID, "appId": FIREBASE_APP_ID, "packageName": PACKAGE_NAME}, headers={"X-Goog-Api-Key": FIREBASE_API_KEY, "X-Goog-Firebase-Installations-Auth": auth_token}, timeout=10)
            return r2.json().get("entries", {}).get("api_url")
        except: return None

    def push_to_private_repo(self, filename, data):
        # Push processed JSON files directly to the private repository 'iVan-Xtra'
        url = f"https://api.github.com/repos/{REPO_OWNER}/{TARGET_REPO}/contents/{filename}"
        headers = {"Authorization": f"token {IVAN_TOKEN}", "Accept": "application/vnd.github.v3+json"}
        
        # Fetch current file's SHA to perform an update
        r_get = requests.get(url, headers=headers)
        sha = r_get.json().get('sha') if r_get.status_code == 200 else None
        
        # Encode content to Base64 for GitHub API
        content = base64.b64encode(json.dumps(data, indent=4, ensure_ascii=False).encode('utf-8')).decode('utf-8')
        payload = {"message": f"Auto-Update Highlights {filename}", "content": content}
        if sha: payload["sha"] = sha
        
        res = requests.put(url, headers=headers, json=payload)
        if res.ok: print(f"✅ {filename} updated in iVan-Xtra!")
        else: print(f"❌ Failed to push {filename}: {res.text}")

    def start_sync(self):
        # Main execution flow: Get API -> Fetch Highlights -> Decrypt Streams -> Push to GitHub
        api_url = self.get_api_url()
        if not api_url: 
            print("❌ Firebase connection failed."); return
        
        base_api = api_url.rstrip('/')
        headers = {"User-Agent": "Dalvik/2.1.0"}
        
        # 1. Fetch and decrypt the main highlights list
        print(f"📡 Fetching Highlights list from: {base_api}/highlights.json")
        r_list = requests.get(f"{base_api}/highlights.json", headers=headers)
        list_dec = self._decrypt_data(r_list.json().get("data", ""))
        
        if not list_dec:
            print("❌ Failed to decrypt Highlights list."); return
            
        highlights_data = json.loads(list_dec)
        print(f"✅ Found {len(highlights_data)} Highlight items. Fetching stream details...")
        
        # 2. Loop through each highlight to fetch and fix channel data
        for item in highlights_data:
            m_id = item.get("id")
            # Fetch individual stream files for each highlight ID
            r_ch = requests.get(f"{base_api}/channels/{m_id}.json", headers=headers)
            if r_ch.status_code == 200:
                ch_dec = self._decrypt_data(r_ch.json().get("data", ""))
                if ch_dec:
                    # Apply 7 rules and inject into the main object
                    item["stream_links"] = self.apply_corrections(json.loads(ch_dec))
                else:
                    item["stream_links"] = []
            else:
                item["stream_links"] = []
        
        # 3. Save files to the private repository iVan-Xtra
        self.push_to_private_repo("highlights.json", highlights_data)
        self.push_to_private_repo("Playz-Highlights.json", highlights_data)
        print("✅ Highlights Sync to iVan-Xtra Successful!")

if __name__ == "__main__":
    iVanHighlightsProcessor().start_sync()
