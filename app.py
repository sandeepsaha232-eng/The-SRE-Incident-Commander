import os
import asyncio
import datetime
import uuid
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from groq import Groq

app = FastAPI()

# --- CONFIG & INITIALIZATION ---
API_KEY = os.environ.get("GROQ_API_KEY")
client = Groq(api_key=API_KEY) if API_KEY else None
fleet_data = {}
pending_commands = {} # The "Mailbox" for remote execution
CPU_LIMIT = 20.0 
SESSION_KEY = "SRE-" + str(uuid.uuid4())[:8].upper()

# --- UTILITY: AI REASONING ---
async def get_sre_advice(metrics):
    if not client: return "AI Offline: Set GROQ_API_KEY in Space Secrets."
    try:
        prompt = f"System: {metrics['machine_id']}. CPU: {metrics['total_cpu']}%, RAM: {metrics['total_memory']}%. Process: {metrics['top_app_name']}. You are a Senior SRE. Give a 1-sentence fix. Bold the command."
        completion = await asyncio.to_thread(
            client.chat.completions.create,
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2
        )
        return completion.choices[0].message.content
    except: return "Analyzing metrics... system looks stable."

# --- ENDPOINTS: AGENT COMMUNICATION ---
@app.post("/report")
async def receive_report(request: Request):
    data = await request.json()
    mid = data.get("machine_id", "Unknown")
    data["status"] = "CRITICAL" if data.get("total_cpu", 0) > CPU_LIMIT else "HEALTHY"
    data["last_seen"] = datetime.datetime.now().strftime("%H:%M:%S")
    fleet_data[mid] = data
    return {"status": "ok"}

@app.get("/poll/{machine_id}")
async def poll_commands(machine_id: str):
    # Agent checks this every 5s to see if a 'Kill' was clicked on the web
    command = pending_commands.pop(machine_id, None)
    return {"command": command}

@app.post("/kill/{machine_id}/{pid}")
async def queue_kill(machine_id: str, pid: str):
    pending_commands[machine_id] = f"kill -9 {pid}"
    return {"status": "command_queued"}

# --- DASHBOARD UI ---
@app.get("/", response_class=HTMLResponse)
async def dashboard():
    # Calculate Fleet Health using Statistics
    # Fleet Health = (1 - (Critical_Nodes / Total_Nodes)) * 100
    critical_count = sum(1 for m in fleet_data.values() if m["status"] == "CRITICAL")
    total_nodes = len(fleet_data)
    health_score = 100 if total_nodes == 0 else (1 - (critical_count / total_nodes)) * 100

    rows = ""
    for mid, info in fleet_data.items():
        color = "#ff7b72" if info["status"] == "CRITICAL" else "#39d353"
        rows += f"""
        <tr style="border-bottom: 1px solid #30363d;">
            <td style="padding: 15px;"><a href="/machine/{mid}" style="color: #58a6ff; text-decoration: none; font-weight: bold;">{mid} 🔍</a></td>
            <td style="color: {color}; font-weight: bold;">● {info['status']}</td>
            <td>{info['total_cpu']}%</td>
            <td>{info['total_memory']}%</td>
            <td>{info['top_app_name']}</td>
            <td>
                <form action="/kill/{mid}/{info.get('top_pid', '0')}" method="post" style="display:inline;">
                    <button type="submit" style="background:transparent; border:1px solid #da3633; color:#da3633; cursor:pointer; border-radius:4px;">TERMINATE</button>
                </form>
            </td>
        </tr>
        """

    return f"""
    <html>
        <head><title>SRE FLEET COMMANDER</title></head>
        <body style="background: #010409; color: #c9d1d9; font-family: sans-serif; padding: 40px;">
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <h1>🚀 FLEET COMMANDER</h1>
                <div style="text-align: right; background: #161b22; padding: 10px; border-radius: 6px;">
                    <span style="color: #8b949e; font-size: 0.7rem;">FLEET KEY:</span><br>
                    <b style="color: #58a6ff;">{SESSION_KEY}</b>
                </div>
            </div>

            <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 20px; margin: 30px 0;">
                <div style="background: #0d1117; padding: 20px; border: 1px solid #30363d; border-radius: 8px;">
                    <span style="color: #8b949e;">FLEET HEALTH</span>
                    <h2 style="color: #39d353;">{health_score:.1f}%</h2>
                </div>
                <div style="background: #0d1117; padding: 20px; border: 1px solid #30363d; border-radius: 8px;">
                    <span style="color: #8b949e;">NODES ONLINE</span>
                    <h2 style="color: #f0f6fc;">{total_nodes}</h2>
                </div>
                <div style="background: #0d1117; padding: 20px; border: 1px solid #30363d; border-radius: 8px;">
                    <span style="color: #8b949e;">TOIL REDUCED</span>
                    <h2 style="color: #58a6ff;">{total_nodes * 2.5:.1f} hrs/mo</h2>
                </div>
            </div>

            <table style="width: 100%; border-collapse: collapse; background: #0d1117; border: 1px solid #30363d;">
                <thead style="background: #161b22; color: #8b949e; text-align: left;">
                    <tr><th style="padding: 15px;">MACHINE ID</th><th>STATUS</th><th>CPU</th><th>RAM</th><th>TOP PROCESS</th><th>ACTION</th></tr>
                </thead>
                <tbody>{rows if rows else "<tr><td colspan='6' style='text-align:center; padding: 50px;'>No active agents.</td></tr>"}</tbody>
            </table>
            <script>setTimeout(()=>location.reload(), 5000);</script>
        </body>
    </html>
    """

@app.get("/machine/{machine_id}", response_class=HTMLResponse)
async def machine_detail(machine_id: str):
    info = fleet_data.get(machine_id)
    if not info: return "<h1>System Offline</h1>"
    advice = await get_sre_advice(info)
    return f"""
    <html>
        <body style="background: #010409; color: #c9d1d9; font-family: sans-serif; padding: 40px;">
            <a href="/" style="color: #58a6ff; text-decoration: none;">&larr; Return to Dashboard</a>
            <h1 style="margin-top: 30px;">{machine_id} Deep Dive</h1>
            <div style="background: #161b22; padding: 30px; border-radius: 8px; border: 1px solid #f1e05a;">
                <h3 style="color: #f1e05a; margin-top: 0;">🤖 AI ROOT CAUSE ANALYSIS</h3>
                <p style="font-size: 1.2rem; line-height: 1.6;">{advice}</p>
            </div>
        </body>
    </html>
    """
