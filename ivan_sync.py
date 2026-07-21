import requests
import json
import base64
import os
import datetime
import binascii
from collections import OrderedDict

# 🔐 Load Source URL from GitHub Secrets
TARGET_URL = os.getenv("LIVXOW_URL")

def get_token():
    """Generates a security token based on current UTC time."""
    current_time = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    try:
        encoded_bytes = base64.b64encode(current_time.encode('utf-8'))
        encoded_str = encoded_bytes.decode('utf-8')
        reversed_b64 = encoded_str[::-1]
        hex_str = binascii.hexlify(reversed_b64.encode('utf-8')).decode('utf-8')
        return hex_str[::-1]
    except: return None

def process_links(links_input):
    """Processes branding rules, domain fixes, and standardizes link keys."""
    final_list = []
    if isinstance(links_input, str):
        try: links_input = json.loads(links_input)
        except: return []
    if not isinstance(links_input, list): return []

    for link_obj in links_input:
        name = link_obj.get("name", "").strip()
        link_val = link_obj.get("link", "") or link_obj.get("url", "")
        
        # Clean tokenApi from stringified JSON to proper Object
        token_api_raw = link_obj.get("tokenApi", "")
        if isinstance(token_api_raw, str) and (token_api_raw.startswith("{") or token_api_raw.startswith("[")):
            try: token_api_raw = json.loads(token_api_raw)
            except: pass

        # Branding: Replace CricZ with SPORTIFy
        if "CricZ" in name or "cricz" in name:
            name = name.replace("CricZ", "SPORTIFy").replace("cricz", "SPORTIFy")
        elif name.upper() in ["AQ", "LQ", "SD", "HD", "FHD", "4K"]:
            name = f"SPORTIFy {name}"
        
        # Domain fix: .fly. to .cf.
        if "otte.live.fly.ww.aiv-cdn.net" in link_val:
            link_val = link_val.replace(".fly.", ".cf.")

        final_list.append(OrderedDict([
            ("title", name),
            ("link", link_val),
            ("logo", ""),
            ("type", link_obj.get("scheme", 0)),
            ("api", link_obj.get("api", "")),
            ("tokenApi", token_api_raw)
        ]))
    return final_list

def run():
    if not TARGET_URL:
        print("Error: LIVXOW_URL missing in GitHub Secrets!")
        exit(1)

    token = get_token()
    payload = json.dumps({"requestData": token, "from": "highlights"}, separators=(',', ':'))
    headers = {"User-Agent": "okhttp/4.9.0", "Content-Type": "application/json"}

    try:
        r = requests.post(TARGET_URL, data=payload, headers=headers, timeout=30)
        r.raise_for_status()
        raw_data = r.json()
        
        highlights_list = []
        for item in raw_data:
            # Decoding nested JSON strings
            h_info = json.loads(item.get("highlight", "{}"))
            processed_channels = process_links(item.get("links", "[]"))
            title = h_info.get("eventName") or h_info.get("title") or "Unknown Highlight"

            # Building standardized structure
            h_obj = OrderedDict([
                ("id", int(item.get("id", 0))),
                ("title", title),
                ("image", h_info.get("eventLogo", "")),
                ("cat", h_info.get("category", "Highlights")),
                ("eventInfo", OrderedDict([
                    ("teamA", h_info.get("teamAName", "Team A")),
                    ("teamB", h_info.get("teamBName", "Team B")),
                    ("teamAFlag", h_info.get("teamAFlag", "")),
                    ("teamBFlag", h_info.get("teamBFlag", "")),
                    ("eventName", title),
                    ("date", h_info.get("date", "")),
                    ("time", h_info.get("time", ""))
                ])),
                ("channels_data", processed_channels)
            ])
            highlights_list.append(h_obj)

        # IST Time for header
        now_ist = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=5, minutes=30)
        update_time_str = now_ist.strftime("%I:%M:%S %p %d-%m-%Y")
        
        final_res = OrderedDict([
            ("NAME", "FluX-oW Highlights (Auto Updated)"),
            ("AUTHOR", "iVan_FluX"),
            ("TELEGRAM CHANNEL", "https://t.me/api_hub_by_ivan"),
            ("Last update time", update_time_str),
            ("events", highlights_list)
        ])

        # Saving as plain JSON (No Encryption)
        with open("ivan.json", "w", encoding="utf-8") as f:
            json.dump(final_res, f, indent=4, ensure_ascii=False)
        
        print("Success: ivan.json has been generated.")

    except Exception as e:
        print(f"Error: {e}")
        exit(1)

if __name__ == "__main__":
    run()
