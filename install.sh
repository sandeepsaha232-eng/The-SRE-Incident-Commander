#!/bin/bash
echo "🚀 ENROLLING IN SRE FLEET COMMANDER..."
curl -sSL https://huggingface.co/spaces/sandeep8327/sre-incident-commander/raw/main/fleet_agent.py -o fleet_agent.py
pip3 install psutil requests --quiet
nohup python3 fleet_agent.py > sre_agent.log 2>&1 &
echo "🎖️ SUCCESS. SYSTEM IS PROTECTED."
