import sqlite3
import json
from pathlib import Path
import subprocess
import socket
import time
from dotenv import load_dotenv
from advisory_engine import generate_advisories
from notification_gateway import NotificationGateway, pick_highest_priority_advisory
import urllib.request

WA_BRIDGE_DIR = Path('wa-bridge')

def is_port_open(host="127.0.0.1", port=3000):
    # Checks if the WhatsApp Node.js bridge is already running.
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(1)
        return s.connect_ex((host, port)) == 0

def is_wa_ready():
    # Queries the bridge /health endpoint to check if WhatsApp client is fully authenticated.
    try:
        req = urllib.request.urlopen("http://localhost:3000/health", timeout=2)
        if req.status == 200:
            data = json.loads(req.read().decode('utf-8'))
            return data.get('ready', False)
    except Exception:
        return False
    return False

def ensure_wa_bridge():
    # Spawns Konsole if port 3000 is inactive and waits until WhatsApp client reaches ready state.
    if is_wa_ready():
        print("WhatsApp bridge client is active and ready.")
        return

    # Check if server is running but not ready yet
    try:
        urllib.request.urlopen("http://localhost:3000/health", timeout=1)
    except Exception:
        print("Launching WhatsApp bridge in Konsole...")
        cmd = [
            "konsole",
            "--hold",
            "-e",
            "bash",
            "-c",
            f'cd "{WA_BRIDGE_DIR}" || exit 1; node server.js'
        ]
        subprocess.Popen(cmd)

    print("Waiting for WhatsApp Web client to authenticate and finish loading...")
    retries = 30  # Max wait 30 seconds
    while retries > 0:
        if is_wa_ready():
            print("WhatsApp client is ready! Proceeding to send messages.")
            return
        time.sleep(1)
        retries -= 1

    print("Warning: WhatsApp bridge did not reach ready state in time.")
    
def send_daily_messages(data_dir: Path):
    try:
        conn = sqlite3.connect('subscribers.db')
        conn.row_factory = sqlite3.Row
        subscribers = conn.execute("SELECT * FROM subscribers").fetchall()
        conn.close()
    except sqlite3.OperationalError:
        print("No subscriber database found.")
        return

    outlook_index_path = data_dir / 'outlooks_index.json'
    if not outlook_index_path.exists():
        print("Outlooks index missing.")
        return

    outlooks_idx = json.loads(outlook_index_path.read_text(encoding='utf-8'))
    outlook_files = {item['key']: data_dir / item['file'] for item in outlooks_idx.get('locations', [])}

    # Ensure WhatsApp server bridge is running before initializing gateway calls
    has_wa_subscribers = any(sub['platform'] in (2, 3) for sub in subscribers)
    if has_wa_subscribers:
        ensure_wa_bridge()

    try:
        gw = NotificationGateway() 
    except Exception as e:
        print(f"Gateway init warning: {e}. Running in dry-run mode.")
        gw = None

    for sub in subscribers:
        grid_key = sub['grid_key']
        if grid_key not in outlook_files:
            continue

        outlook_data = json.loads(outlook_files[grid_key].read_text(encoding='utf-8'))
        crops = json.loads(sub['crops'])
        
        # 1. Generate multi-crop, multi-bucket advisories for this grid
        advisories = generate_advisories(outlook_data['outlook'], crops)
        
        # 2. Pick highest priority based on their specific crops
        chosen = pick_highest_priority_advisory(advisories, crops)
        if not chosen:
            continue
            
        # 3. Extract text in their preferred language
        lang = sub['language']
        text = chosen['text'].get(lang, chosen['text']['en'])

        # 4. Route to preferred platforms (1: SMS, 2: WA, 3: Both)
        if gw is None:
            print(f"[DRY RUN] -> {sub['phone']} (Platform {sub['platform']}): {text}")
            continue

        try:
            if sub['platform'] in (2, 3):  # WhatsApp
                gw.send_whatsapp(sub['phone'], text)
                print(f"[WA SENT] -> {sub['phone']}")

            if sub['platform'] in (1, 3):  # SMS
                gw.send_sms(sub['phone'], text)
                print(f"[SMS SENT] -> {sub['phone']}")

        except Exception as exc:
            print(f"Failed sending to {sub['phone']}: {exc}")

if __name__ == '__main__':
    load_dotenv()
    send_daily_messages(Path('data'))