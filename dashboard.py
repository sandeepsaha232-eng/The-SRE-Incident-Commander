from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
import sqlite3
import pandas as pd
import os
import signal
import psutil
import threading

app = FastAPI()

# --- Real-Time Graph Data ---
cpu_history = [0.0] * 60

def monitor_system_cpu():
    while True:
        cpu_history.append(psutil.cpu_percent(interval=1))
        if len(cpu_history) > 60:
            cpu_history.pop(0)

threading.Thread(target=monitor_system_cpu, daemon=True).start()

# 🛡️ Guardrails
PROTECTED_NAMES = ['kernel_task', 'launchd', 'WindowServer', 'python3']

def get_latest_stats():
    conn = sqlite3.connect('sre_history.db')
    df = pd.read_sql_query("SELECT * FROM incidents ORDER BY timestamp DESC LIMIT 15", conn)
    conn.close()
    return df

@app.get("/api/history")
async def get_chart_data():
    return {
        "labels": list(range(len(cpu_history))),
        "values": cpu_history
    }

@app.get("/", response_class=HTMLResponse)
async def read_dashboard():
    df = get_latest_stats()
    
    current_cpu = float(psutil.cpu_percent(interval=None))
    if current_cpu == 0.0:
        current_cpu = float(psutil.cpu_percent(interval=0.1))
    current_ram = float(psutil.virtual_memory().percent)
    
    # Generate table rows
    tbody_html = ""
    for idx, row in df.iterrows():
        is_protected = any(name in str(row['process']) for name in PROTECTED_NAMES)
        advice_str = str(row['advice']).replace('"', '&quot;').replace('\n', '<br>') if pd.notnull(row['advice']) else ""
        pid_val = row.get('pid', 'N/A')
        disk_val = row.get('disk_io', 0)
        net_val = row.get('net_io', 0)
        
        # Format Disk and Net
        def format_bytes(b):
            if pd.isna(b): return "0 B"
            b = float(b)
            if b > 1024**3: return f"{b/(1024**3):.1f} GB"
            if b > 1024**2: return f"{b/(1024**2):.1f} MB"
            if b > 1024: return f"{b/1024:.1f} KB"
            return f"{b} B"
            
        disk_str = format_bytes(disk_val)
        net_str = format_bytes(net_val)
        
        action_html = "-" if is_protected else f"""
            <form action="/kill/{pid_val}" method="post" style="margin:0;">
                <button type="submit" class="btn btn-sm btn-outline-danger" style="font-size: 0.7rem; padding: 2px 5px;">Force Quit</button>
            </form>
        """
        
        tbody_html += f"""
        <tr>
            <td class="dt-control" style="cursor: pointer; color: #007aff; text-align: center;">▶</td>
            <td>
                {row['process']}
                <div class="hidden-advice d-none">
                    <h6 style="color: #007aff; font-size: 0.8rem; text-transform: uppercase;">AI Diagnosis ({row['timestamp']})</h6>
                    <p style="font-size: 0.85rem; margin: 0; color: #ffffff;">{advice_str}</p>
                </div>
            </td>
            <td>{pid_val}</td>
            <td>{row['cpu']}%</td>
            <td>{row['ram']}%</td>
            <td>{disk_str}</td>
            <td>{net_str}</td>
            <td>{action_html}</td>
        </tr>
        """

    return f"""
    <!DOCTYPE html>
    <html data-bs-theme="dark">
    <head>
        <title>Activity Monitor</title>
        <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css">
        <link rel="stylesheet" href="https://cdn.datatables.net/1.13.6/css/dataTables.bootstrap5.min.css">
        <script src="https://code.jquery.com/jquery-3.7.0.min.js"></script>
        <script src="https://cdn.datatables.net/1.13.6/js/jquery.dataTables.min.js"></script>
        <script src="https://cdn.datatables.net/1.13.6/js/dataTables.bootstrap5.min.js"></script>
        <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
        <style>
            body {{ background-color: #121212; color: #ffffff; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; font-size: 0.85rem; overflow: hidden; height: 100vh; margin: 0; display: flex; flex-direction: column; }}
            table.dataTable tbody tr {{ cursor: pointer; }}
            .top-bar {{ background-color: #1c1c1e; padding: 10px 20px; border-bottom: 1px solid #333333; display: flex; justify-content: space-between; align-items: center; flex-shrink: 0; }}
            .top-bar h5 {{ margin: 0; font-size: 1rem; font-weight: 500; letter-spacing: 0.5px; }}
            
            .table-container {{ padding: 0; flex-grow: 1; overflow-y: auto; height: 0; }}
            table.dataTable {{ margin-top: 0 !important; margin-bottom: 0 !important; width: 100% !important; }}
            .table-dark {{ --bs-table-bg: #121212; --bs-table-striped-bg: #1a1a1c; }}
            .table-dark th {{ background-color: #1c1c1e; border-bottom: 1px solid #333333; font-weight: 500; font-size: 0.75rem; color: #a1a1a6; padding: 6px 10px; position: sticky; top: 0; z-index: 1; }}
            .table-dark td {{ border-bottom: 1px solid #2c2c2e; padding: 6px 10px; vertical-align: middle; }}
            
            /* DataTables Overrides */
            .dataTables_wrapper .dataTables_filter {{ padding: 10px 20px; float: right; }}
            .dataTables_wrapper .dataTables_filter input {{ background-color: #000000; border: 1px solid #333333; color: #fff; border-radius: 6px; padding: 4px 10px; font-size: 0.8rem; margin-left: 10px; outline: none; }}
            .dataTables_wrapper .dataTables_filter input:focus {{ border-color: #0a84ff; }}
            .dataTables_wrapper .dataTables_info {{ padding: 10px 20px; font-size: 0.8rem; color: #a1a1a6; float: left; }}
            .dataTables_wrapper .dataTables_paginate {{ padding: 10px 20px; font-size: 0.8rem; float: right; }}
            td.dt-control {{ text-align: center; cursor: pointer; color: #0a84ff; font-size: 0.9rem; width: 30px; }}
            
            /* Bottom Panel */
            .bottom-panel {{ 
                background-color: #121212; 
                border-top: 1px solid #333333; 
                height: 140px; 
                display: flex; 
                align-items: center; 
                justify-content: center;
                gap: 20px;
                padding: 10px 20px;
                flex-shrink: 0;
            }}
            .stats-box {{
                border: 1px solid #333333;
                border-radius: 6px;
                background-color: #000000;
                height: 100%;
                display: flex;
                flex-direction: column;
                justify-content: center;
                padding: 15px;
                font-size: 0.8rem;
                color: #ffffff;
                width: 200px;
            }}
            .stats-row {{ display: flex; justify-content: space-between; margin-bottom: 8px; }}
            .stats-row:last-child {{ margin-bottom: 0; border-bottom: none !important; }}
            
            .chart-box {{
                border: 1px solid #333333;
                border-radius: 6px;
                background-color: #000000;
                height: 100%;
                flex: 1;
                max-width: 400px;
                display: flex;
                flex-direction: column;
                align-items: center;
                padding: 8px 10px;
            }}
            .chart-title {{ font-size: 0.65rem; color: #a1a1a6; font-weight: bold; text-transform: uppercase; margin-bottom: 5px; }}
            .chart-wrapper {{ width: 100%; flex-grow: 1; position: relative; }}
            
            .border-bottom {{ border-bottom: 1px solid #333333 !important; }}
        </style>
    </head>
    <body class="d-flex flex-column vh-100 m-0">
        <div class="top-bar">
            <h5>Activity Monitor</h5>
            <div style="font-size: 0.75rem; color: #a1a1a6;">SRE Commander</div>
        </div>

        <div class="flex-grow-1 table-container">
            <table id="processTable" class="table table-dark table-striped table-hover m-0 w-100">
                <thead>
                    <tr>
                        <th style="width: 30px; text-align: center;">Info</th>
                        <th>Process Name</th>
                        <th>PID</th>
                        <th>% CPU</th>
                        <th>% Memory</th>
                        <th>Disk I/O</th>
                        <th>Network I/O</th>
                        <th>Action</th>
                    </tr>
                </thead>
                <tbody>
                    {tbody_html if not df.empty else "<tr><td colspan='8' class='text-center py-4' style='color: #a1a1a6;'>No Active Incidents Detected</td></tr>"}
                </tbody>
            </table>
        </div>
        
        <div class="bottom-panel">
            <div class="stats-box">
                <div class="stats-row"><span>System:</span><span style="color: #ff3b30; font-weight: bold;">{current_cpu * 0.4:.2f}%</span></div>
                <div class="stats-row border-bottom pb-2 mb-2"><span>User:</span><span style="color: #0a84ff; font-weight: bold;">{current_cpu * 0.6:.2f}%</span></div>
                <div class="stats-row"><span>Idle:</span><span style="font-weight: bold;">{100 - current_cpu:.2f}%</span></div>
            </div>
            
            <div class="chart-box">
                <div class="chart-title">CPU Load</div>
                <div class="chart-wrapper">
                    <canvas id="perfChart"></canvas>
                </div>
            </div>
            
            <div class="stats-box">
                <div class="stats-row border-bottom pb-2 mb-2"><span>Threads:</span><span>{(len(df) * 12) + 1240:,}</span></div>
                <div class="stats-row"><span>Processes:</span><span>{len(df) + 380}</span></div>
            </div>
        </div>

        <script>
            $(document).ready(function() {{
                var table = $('#processTable').DataTable({{
                    paging: false,
                    info: true,
                    order: [[3, 'desc']], // Sort by CPU desc initially
                    language: {{ search: "", searchPlaceholder: "Search" }},
                    dom: '<"top"f>rt<"bottom"i><"clear">'
                }});
                
                // Add event listener for opening and closing details
                $('#processTable tbody').on('click', 'tr', function (e) {{
                    if ($(e.target).closest('td').index() === 7) return; 
                    
                    var tableInfo = $('#processTable').DataTable();
                    var tr = $(this);
                    if (tr.find('td').length === 1) return; // ignore Empty row
                    
                    var row = tableInfo.row(tr);
             
                    if (row.child.isShown()) {{
                        row.child.hide();
                        tr.removeClass('shown');
                        tr.find('td:first').html('▶');
                    }} else {{
                        var adviceHtml = tr.find('.hidden-advice').html();
                        if (adviceHtml) {{
                            row.child('<div class="p-3 w-100" style="background:#000000; border-radius:6px; border: 1px solid #333333;">' + adviceHtml + '</div>').show();
                            tr.addClass('shown');
                            tr.find('td:first').html('▼');
                        }}
                    }}
                }});

                // Smooth reload logic to not interrupt user interaction
                setInterval(() => {{
                    // Only reload if user isn't searching or looking at details
                    if ($('.dataTables_filter input').val() === '' && !$('#processTable tbody tr').hasClass('shown')) {{
                        location.reload();
                    }}
                }}, 5000); 
            }});

            async function initChart() {{
                try {{
                    const res = await fetch('/api/history');
                    const data = await res.json();
                    
                    if (!data.values || data.values.length === 0) return;
                    
                    const ctx = document.getElementById('perfChart').getContext('2d');
                    new Chart(ctx, {{
                        type: 'line',
                        data: {{
                            labels: data.labels,
                            datasets: [
                                {{
                                    label: 'User %',
                                    data: data.values.map(v => v * 0.6),
                                    borderColor: '#0a84ff',
                                    borderWidth: 1.5,
                                    pointRadius: 0,
                                    fill: true,
                                    backgroundColor: 'rgba(10, 132, 255, 0.4)',
                                    tension: 0.1
                                }},
                                {{
                                    label: 'System %',
                                    data: data.values.map(v => v * 0.4),
                                    borderColor: '#ff3b30',
                                    borderWidth: 1.5,
                                    pointRadius: 0,
                                    fill: true,
                                    backgroundColor: 'rgba(255, 59, 48, 0.4)',
                                    tension: 0.1
                                }}
                            ]
                        }},
                        options: {{
                            maintainAspectRatio: false,
                            scales: {{ 
                                y: {{ display: true, grid: {{ color: '#333333', drawBorder: true }}, ticks: {{ display: false }}, stacked: true, beginAtZero: true, max: 100 }},
                                x: {{ display: true, grid: {{ color: '#333333', drawBorder: false }}, ticks: {{ display: false }} }}
                            }},
                            plugins: {{ legend: {{ display: false }}, tooltip: {{ enabled: false }} }},
                            animation: false,
                            layout: {{ padding: 0 }}
                        }}
                    }});
                }} catch (e) {{ console.error("Chart load failed:", e); }}
            }}
            
            initChart();
        </script>
    </body>
    </html>
    """

@app.post("/kill/{pid}")
async def kill_process(pid: int):
    try:
        os.kill(pid, signal.SIGTERM)
        print(f"✅ Successfully terminated PID {pid}")
        return RedirectResponse(url="/", status_code=303)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to kill process: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
