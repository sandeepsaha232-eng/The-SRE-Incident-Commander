from __future__ import annotations

from typing import Any, List, Literal, Optional

from pydantic import BaseModel, Field, ValidationInfo, field_validator


class SreIncidentCommanderAction(BaseModel):
    """Model representing an action that the agent can request.

    Attributes
    ----------
    command: Literal['check_metrics', 'list_processes', 'kill_process', 'restart_service']
        The type of command to execute.
    target: Optional[str]
        An optional identifier for the command, such as a process ID or service name.
    """

    command: Literal['check_metrics', 'list_processes', 'kill_process', 'restart_service'] = Field(
        ..., description="The command to be performed."
    )
    target: Optional[str] = Field(
        None, description="Target identifier for the command, e.g., PID or service name."
    )

    @field_validator('target')
    @classmethod
    def target_required_for_certain_commands(cls, v: str | None, info: ValidationInfo) -> str | None:
        """Ensure that commands which need a target provide one.

        ``kill_process`` and ``restart_service`` require a non-empty ``target``.
        """
        # Access the 'command' field from the validation context
        command = info.data.get('command')
        if command in {'kill_process', 'restart_service'} and not v:
            raise ValueError(f"'target' must be provided for command {command}")
        return v


class SreIncidentCommanderObservation(BaseModel):
    """Model representing the environment's observation after an action.

    Attributes
    ----------
    cpu_usage: float
        Current CPU usage as a percentage (0-100).
    memory_usage: float
        Current memory usage as a percentage (0-100).
    system_status: Literal['CRITICAL', 'WARNING', 'HEALTHY']
        Overall health status of the system.
    command_output: str
        The textual output produced by the most recent command.
    """

    cpu_usage: float = Field(..., ge=0.0, le=100.0, description="CPU usage percentage.")
    memory_usage: float = Field(..., ge=0.0, le=100.0, description="Memory usage percentage.")
    system_status: Literal['CRITICAL', 'WARNING', 'HEALTHY'] = Field(
        ..., description="Overall system health status."
    )
    command_output: str = Field(..., description="Result of the last executed command.")


class ProcessInfo(BaseModel):
    """Helper model describing a running process.

    Attributes
    ----------
    pid: int
        Process identifier.
    name: str
        Human-readable name of the process.
    cpu_cost: float
        CPU consumption of the process (percentage).
    memory_cost: float
        Memory consumption of the process (percentage).
    """

    pid: int = Field(..., description="Process ID.")
    name: str = Field(..., description="Process name.")
    cpu_cost: float = Field(..., ge=0.0, le=100.0, description="CPU cost as a percentage.")
    memory_cost: float = Field(..., ge=0.0, le=100.0, description="Memory cost as a percentage.")


class State(BaseModel):
    """Internal truth model of the OpenEnv environment.

    Attributes
    ----------
    processes: List[ProcessInfo]
        List of currently running processes.
    is_website_up: bool
        Flag indicating whether the monitored website is reachable.
    """

    processes: List[ProcessInfo] = Field(..., description="List of running processes.")
    is_website_up: bool = Field(..., description="Website availability flag.")
