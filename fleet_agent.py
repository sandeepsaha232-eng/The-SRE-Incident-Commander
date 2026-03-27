import psutil
import requests
import time
import socket
import os

# --- CONFIG ---
CLOUD_URL = "https://sandeep8327-sre-incident-commander.hf.space" # REPLACE THIS
MACHINE_ID = socket.gethostname()

def get_stats():
    cpu = psutil.cpu_percent(interval=1)
    ram = psutil.virtual_memory().percent
    procs = []
    for p in psutil.process_iter(['pid', 'name', 'cpu_percent']):
        try: procs.append(p.info)
        except: continue
    top_p = sorted(procs, key=lambda x: x['cpu_percent'] or 0, reverse=True)[0]
    return {
        "machine_id": MACHINE_ID,
        "total_cpu": cpu,
        "total_memory": ram,
        "top_app_name": top_p['name'],
        "top_pid": top_p['pid']
    }

print(f"🎖️ SRE Agent Online: {MACHINE_ID}")

while True:
    try:
        # 1. SEND REPORT
        stats = get_stats()
        requests.post(f"{CLOUD_URL}/report", json=stats, timeout=5)
        
        # 2. POLL FOR COMMANDS (Remote Fix)
        cmd_res = requests.get(f"{CLOUD_URL}/poll/{MACHINE_ID}", timeout=5)
        command = cmd_res.json().get("command")
        
        if command:
            print(f"⚠️ REMOTE ACTION RECEIVED: {command}")
            os.system(command)
            print("✅ Action executed.")

    except Exception as e:
        print(f"Heartbeat failed: {e}")
    
    time.sleep(5)
