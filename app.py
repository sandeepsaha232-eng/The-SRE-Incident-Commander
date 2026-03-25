from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import uvicorn

from sre_incident_commander.server.sre_environment import SREEnvironment
from sre_incident_commander.models import SreIncidentCommanderAction as Action
from sre_incident_commander.models import SreIncidentCommanderObservation as Observation
from baseline import run_baseline_episode

app = FastAPI(title="SRE Incident Commander Environment API")
env = SREEnvironment()

class ResetRequest(BaseModel):
    task_level: str

@app.post("/reset")
def reset_environment(request: ResetRequest):
    """Reset the environment to the given difficulty level."""
    if request.task_level not in ["easy", "medium", "hard"]:
        raise HTTPException(status_code=400, detail="Invalid task_level. Must be 'easy', 'medium', or 'hard'")
        
    obs = env.reset(request.task_level)
    return obs

@app.post("/step")
def step_environment(action: Action):
    """Execute an action and return observation and step details."""
    try:
        obs, reward, done, info = env.step(action)
        return {
            "observation": obs,
            "reward": reward,
            "done": done,
            "info": info
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/state")
def get_state():
    """Returns the environment internal state."""
    return env.state

@app.get("/baseline")
def run_baseline():
    """Runs the baseline episode for easy, medium, and hard tasks and returns the scores."""
    scores = {}
    for level in ["easy", "medium", "hard"]:
        scores[level] = run_baseline_episode(env, level)
    return scores

@app.get("/tasks")
def get_tasks():
    """Returns the available tasks and the JSON schema for the Action model."""
    return {
        "tasks": ["easy", "medium", "hard"],
        "action_schema": Action.model_json_schema()
    }

@app.get("/grader")
def get_grader():
    """Returns the current reward/grade from the environment."""
    # Since reward is calculated per step, we will recalculate it based on current usage.
    cpu, mem = env._calc_usage()
    reward = 0.0
    if cpu < 60.0 and mem < 60.0 and env._state.is_website_up:
        reward = 1.0
        
    if env._anomaly_name and any(p.name == env._anomaly_name for p in env._state.processes):
        reward = 0.0
        
    if not any(p.name == "nginx" for p in env._state.processes):
        reward = 0.0
        
    return {"current_reward": reward}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
