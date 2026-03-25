from __future__ import annotations

from typing import List, Dict, Any

from openenv.core.env_server.interfaces import Environment
from openenv.core.env_server.types import State as ServerState

from ..models import (
    SreIncidentCommanderAction as Action,
    SreIncidentCommanderObservation as Observation,
    ProcessInfo,
    State as EnvState,
)


class SREEnvironment(Environment):
    """Deterministic SRE incident commander environment.

    Tracks a list of ``ProcessInfo`` objects, a website health flag, and aggregates
    CPU / memory usage. Supports three difficulty levels that inject a single
    anomalous process.
    """

    def __init__(self) -> None:
        from uuid import uuid4
        self._server_state = ServerState(episode_id=str(uuid4()), step_count=0)
        self._state: EnvState = EnvState(processes=[], is_website_up=True)
        self._anomaly_name: str | None = None
        self._current_task_level: str | None = None
        self._done: bool = False

    @property
    def state(self) -> ServerState:
        return self._server_state

    # ---------------------------------------------------------------------
    # Helper utilities
    # ---------------------------------------------------------------------
    def _calc_usage(self) -> tuple[float, float]:
        total_cpu = sum((p.cpu_cost for p in self._state.processes), 0.0)
        total_mem = sum((p.memory_cost for p in self._state.processes), 0.0)
        return min(total_cpu, 100.0), min(total_mem, 100.0)

    def _system_status(self, cpu: float, mem: float) -> str:
        if cpu > 80.0 or mem > 80.0:
            return "CRITICAL"
        if cpu > 60.0 or mem > 60.0:
            return "WARNING"
        return "HEALTHY"

    # ---------------------------------------------------------------------
    # Public API required by OpenEnv
    # ---------------------------------------------------------------------
    def reset(self, task_level: str) -> Observation:
        """Reset the environment to a known difficulty.

        Parameters
        ----------
        task_level: str
            One of ``"easy"``, ``"medium"`` or ``"hard"``.
        """
        if task_level not in {"easy", "medium", "hard"}:
            raise ValueError("task_level must be 'easy', 'medium' or 'hard'")
            
        self._current_task_level = task_level

        normal = [
            ProcessInfo(pid=1, name="systemd", cpu_cost=5.0, memory_cost=5.0),
            ProcessInfo(pid=2, name="nginx", cpu_cost=10.0, memory_cost=8.0),
            ProcessInfo(pid=3, name="ssh", cpu_cost=2.0, memory_cost=2.0),
        ]

        if task_level == "easy":
            anomaly = ProcessInfo(pid=99, name="miner.sh", cpu_cost=90.0, memory_cost=30.0)
        elif task_level == "medium":
            anomaly = ProcessInfo(pid=100, name="crypto_miner", cpu_cost=70.0, memory_cost=40.0)
        else:  # hard
            anomaly = ProcessInfo(pid=101, name="worker", cpu_cost=85.0, memory_cost=60.0)

        self._state = EnvState(processes=normal + [anomaly], is_website_up=True)
        self._anomaly_name = anomaly.name
        self._done = False

        from uuid import uuid4
        self._server_state = ServerState(episode_id=str(uuid4()), step_count=0)
        
        cpu, mem = self._calc_usage()
        return Observation(
            cpu_usage=cpu,
            memory_usage=mem,
            system_status=self._system_status(cpu, mem),
            command_output="environment reset",
        )

    def step(self, action: Action) -> tuple[Observation, float, bool, Dict[str, Any]]:
        """Execute an action and return observation, reward, done flag and info.
        """
        self._server_state.step_count += 1
        
        # --- Dynamics: Telemetry Noise ---
        import random
        for p in self._state.processes:
            p.cpu_cost = max(0.1, p.cpu_cost + random.uniform(-2.0, 2.0))
            p.memory_cost = max(0.1, p.memory_cost + random.uniform(-2.0, 2.0))
            
        # --- Dynamics: Evolving Memory Leak ---
        if self._current_task_level == "hard":
            for p in self._state.processes:
                if p.name == "worker":
                    p.memory_cost *= 1.12
                    
        # --- Dynamics: OOM Killer ---
        oom_warning = ""
        total_mem_raw = sum(p.memory_cost for p in self._state.processes)
        if total_mem_raw > 100.0 and self._state.processes:
            victim = random.choice(self._state.processes)
            self._state.processes.remove(victim)
            oom_warning = f" [WARNING: OOM Killer invoked: killed {victim.name}]"
        
        cmd_output = ""
        if action.command == "list_processes":
            cmd_output = ", ".join(p.name for p in self._state.processes)
        elif action.command == "kill_process":
            target = action.target
            if not target:
                cmd_output = "no target provided"
            else:
                matched = [p for p in self._state.processes if str(p.pid) == target or p.name == target]
                if not matched:
                    cmd_output = f"bash: kill: ({target}) - No such process"
                else:
                    self._state.processes = [p for p in self._state.processes if p not in matched]
                    cmd_output = f"killed {len(matched)} process(es)"
        elif action.command == "restart_service":
            target = action.target
            if target == "nginx":
                for p in self._state.processes:
                    if p.name == "nginx":
                        p.cpu_cost = 10.0
                        p.memory_cost = 8.0
                cmd_output = "nginx restarted"
            else:
                cmd_output = f"service {target} not recognized"
        elif action.command == "check_metrics":
            cmd_output = "metrics checked"
        else:
            cmd_output = "unknown command"
            
        cmd_output += oom_warning

        cpu, mem = self._calc_usage()
        status = self._system_status(cpu, mem)
        
        # --- Dynamics: Cascading Failure ---
        if not any(p.name == "nginx" for p in self._state.processes):
            self._state.is_website_up = False
            status = "CRITICAL"

        observation = Observation(
            cpu_usage=cpu,
            memory_usage=mem,
            system_status=status,
            command_output=cmd_output.strip(),
        )

        reward = 0.0
        done = False
        
        if cpu < 60.0 and mem < 60.0 and self._state.is_website_up:
            reward = 1.0
            done = True
            
        if self._anomaly_name and any(p.name == self._anomaly_name for p in self._state.processes):
            reward = 0.0
            
        if not self._state.is_website_up:
            reward = 0.0
            done = True
            
        if status == "CRITICAL":
            done = True
            
        self._done = done

        info = {
            "processes": [p.model_dump() for p in self._state.processes],
            "is_website_up": self._state.is_website_up,
        }
        return observation, reward, done, info
