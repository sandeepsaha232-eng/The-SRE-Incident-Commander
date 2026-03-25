import os
import json
from openai import OpenAI

from sre_incident_commander.server.sre_environment import SREEnvironment
from sre_incident_commander.models import SreIncidentCommanderAction as Action


def run_baseline_episode(env: SREEnvironment, task_level: str) -> float:
    """Run a single episode using gpt-4o-mini baseline agent."""
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return 0.0
        
    client = OpenAI(api_key=api_key)
    
    print(f"\n{'='*50}\nStarting '{task_level}' episode\n{'='*50}")
    obs = env.reset(task_level=task_level)
    
    # Simple system prompt defining the environment and action space
    system_prompt = (
        "You are an SRE Incident Commander. Your goal is to keep the system healthy "
        "by identifying and killing anomalous processes consuming excessive CPU or Memory. "
        "Available commands: 'check_metrics', 'list_processes', 'kill_process', 'restart_service'. "
        "If the command requires a target (like a PID), provide it in 'target'. "
        "Always respond with valid JSON matching this schema: "
        '{"command": "string", "target": "string or null"}'
    )
    
    messages = [{"role": "system", "content": system_prompt}]
    reward = 0.0

    for step_num in range(1, 11):
        print(f"\n--- Step {step_num} ---")
        print(f"Observation: {obs.model_dump_json(indent=2)}")
        
        messages.append({
            "role": "user",
            "content": f"Current observation: {obs.model_dump_json()}"
        })
        
        # Call LLM
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            response_format={"type": "json_object"}
        )
        
        # Parse output
        action_json_str = response.choices[0].message.content
        try:
            action_dict = json.loads(action_json_str)
            action = Action(**action_dict)
            print(f"Agent Action: {action.model_dump_json()}")
        except Exception as e:
            print(f"Error parsing agent action '{action_json_str}': {e}")
            break
            
        messages.append({
            "role": "assistant",
            "content": action_json_str
        })
        
        # Environment step
        obs, reward, done, info = env.step(action)
        
        if done:
            print(f"\n=> Episode Done! Final Reward: {reward}")
            break
            
    return reward


if __name__ == "__main__":
    if not os.environ.get("OPENAI_API_KEY"):
        print("WARNING: OPENAI_API_KEY environment variable not set. Please set it to run the baseline.")
        exit(1)
        
    env = SREEnvironment()
    
    scores = {}
    for level in ["easy", "medium", "hard"]:
        final_reward = run_baseline_episode(env, level)
        scores[level] = final_reward
        
    print(f"\n{'*'*50}\nBASELINE SCORES\n{'*'*50}")
    for level, score in scores.items():
        print(f"{level.capitalize():<10}: {score}")
