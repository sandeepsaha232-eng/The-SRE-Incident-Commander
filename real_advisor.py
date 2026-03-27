import os
import psutil
import time
import sqlite3
from datetime import datetime
from groq import Groq

def send_macos_notification(title, message):
    # We use 'sound name' to make sure you HEAR the alert too
    # We wrap the message in quotes to handle special characters
    clean_message = message.replace('"', "'").replace("\n", " ")[:150] # Limit length for OS
    os.system(f'osascript -e "display notification \\"{clean_message}\\" with title \\"{title}\\" sound name \\"Submarine\\""')

# 1. Setup the "Memory" (Database)
def init_db():
    conn = sqlite3.connect('sre_history.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS incidents 
                 (timestamp TEXT, cpu REAL, ram REAL, pid INTEGER, process TEXT, advice TEXT, disk_io REAL, net_io REAL)''')
    conn.commit()
    conn.close()

# 2. Add this to your loop to save incidents
def log_incident(metrics, top_app, advice):
    conn = sqlite3.connect('sre_history.db')
    c = conn.cursor()
    try:
        c.execute("INSERT INTO incidents (timestamp, cpu, ram, pid, process, advice, disk_io, net_io) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                  (metrics['timestamp'], metrics['total_cpu'], metrics['total_memory'], 
                   top_app['pid'], top_app['name'], advice, metrics['disk_io'], metrics['net_io']))
    except sqlite3.OperationalError:
        c.execute("DROP TABLE IF EXISTS incidents")
        c.execute('''CREATE TABLE incidents 
                     (timestamp TEXT, cpu REAL, ram REAL, pid INTEGER, process TEXT, advice TEXT, disk_io REAL, net_io REAL)''')
        c.execute("INSERT INTO incidents (timestamp, cpu, ram, pid, process, advice, disk_io, net_io) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                  (metrics['timestamp'], metrics['total_cpu'], metrics['total_memory'], 
                   top_app['pid'], top_app['name'], advice, metrics['disk_io'], metrics['net_io']))
    conn.commit()
    conn.close()
    print("💾 Incident saved to SRE History database.")

# 3. New 'Hardcore' Threshold Logic
SENSITIVITY_THRESHOLD = 20.0

# Initialize the Groq Client
client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

def get_sre_advice(metrics, top_app):
    """Sends real MacBook metrics to Groq for lightning-fast SRE diagnosis."""
    
    system_prompt = (
        "You are an expert SRE (Site Reliability Engineer). "
        "Analyze the provided MacBook system metrics and give a high-speed, "
        "technically precise diagnosis. Recommend a specific shell command to fix the issue."
    )
    
    user_content = f"""
    SYSTEM ALERT:
    - CPU Usage: {metrics['total_cpu']}%
    - RAM Usage: {metrics['total_memory']}%
    - Top Process: {top_app['name']} (PID: {top_app['pid']}) @ {top_app['cpu_percent']}% CPU.
    
    Identify the issue and provide the fix.
    """

    try:
        # Use Llama-3.3-70B for maximum 'Hardcore' reasoning
        chat_completion = client.chat.completions.create(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content}
            ],
            model="llama-3.3-70b-versatile", # Or "llama-4-scout-17b-16e-instruct"
            temperature=0.1 # Low temperature for reliable technical advice
        )
        return chat_completion.choices[0].message.content
    except Exception as e:
        return f"Groq API Error: {str(e)}"

def get_real_system_metrics():
    # 1. Fetch Real CPU and Memory percentages
    cpu_usage = psutil.cpu_percent(interval=1)
    memory_info = psutil.virtual_memory()
    
    # 2. Capture overall disk and network I/O (bytes per second approximation)
    disk_io = psutil.disk_io_counters().read_bytes + psutil.disk_io_counters().write_bytes
    net_io = psutil.net_io_counters().bytes_sent + psutil.net_io_counters().bytes_recv
    
    # 3. Get Top 5 Processes by CPU usage
    processes = []
    for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent']):
        try:
            p_info = proc.info
            if p_info['cpu_percent'] is None:
                p_info['cpu_percent'] = 0.0
            if p_info['memory_percent'] is None:
                p_info['memory_percent'] = 0.0
            processes.append(p_info)
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue
    
    top_processes = sorted(processes, key=lambda x: x['cpu_percent'], reverse=True)[:5]
    
    return {
        "timestamp": datetime.now().strftime("%H:%M:%S"),
        "total_cpu": cpu_usage,
        "total_memory": memory_info.percent,
        "disk_io": disk_io,
        "net_io": net_io,
        "top_processes": top_processes
    }

# A list of critical system processes that should NEVER be recommended for termination
SYSTEM_PROTECTION_LIST = [
    'kernel_task', 'launchd', 'WindowServer', 'opendirectoryd', 
    'powerd', 'configd', 'syslogd', 'UserEventAgent'
]

def monitor_and_advise():
    print("🚀 SRE Read-Only Advisor Active (Protected Mode)...")
    init_db() # Ensure DB is ready
    
    try:
        while True:
            metrics = get_real_system_metrics()
            
            # Filter out system-critical processes from the "troublemakers"
            risky_apps = [
                p for p in metrics['top_processes'] 
                if p['name'] not in SYSTEM_PROTECTION_LIST
            ]

            print(f"[{metrics['timestamp']}] CPU: {metrics['total_cpu']}% | RAM: {metrics['total_memory']}%")
            
            if metrics['total_cpu'] > 20.0 and risky_apps:
                top_app = risky_apps[0]
                print(f"\n⚠️  ANOMALY: {top_app['name']} is spiking!")
                print("🧠 CONSULTING THE AI BRAIN...")
                
                # CALL THE AI
                advice = get_sre_advice(metrics, top_app)
                
                # Now send the notification AFTER getting the advice
                # We grab the first sentence of the advice for the popup
                short_advice = advice.split('.')[0] 
                send_macos_notification(f"🚨 {top_app['name']} Alert", short_advice)
                
                print("-" * 40)
                print(f"ADVISOR RECOMMENDATION:\n{advice}")
                print("-" * 40 + "\n")
                
                # Automatically Log the completed diagnostic loop
                log_incident(metrics, top_app, advice)
            
            time.sleep(5)
    except KeyboardInterrupt:
        print("\nStopping Advisor.")

if __name__ == "__main__":
    monitor_and_advise()
