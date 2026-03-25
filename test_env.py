import json

from sre_incident_commander.server.sre_environment import SREEnvironment
from sre_incident_commander.models import SreIncidentCommanderAction as Action


def print_section(title: str, data: any = None) -> None:
    print(f"\n{'='*60}")
    print(f"--- {title} ---")
    if data is not None:
        if hasattr(data, "model_dump_json"):
            # Pretty print Pydantic models
            print(json.dumps(json.loads(data.model_dump_json()), indent=2))
        else:
            print(data)
    print(f"{'='*60}")


def main():
    print("🚀 Initializing SREEnvironment...")
    env = SREEnvironment()

    # Step 1: Reset Environment (easy mode)
    initial_obs = env.reset(task_level="easy")
    print_section("Initial Observation (Reset: 'easy')", initial_obs)

    # Step 2: List Processes Action
    list_action = Action(command="list_processes")
    print("⚡ Executing Action: list_processes")
    obs, reward, done, info = env.step(list_action)
    
    print_section("Observation after 'list_processes'", obs)
    print(f"Command Output: {obs.command_output}")
    print("\nEnvironment Internal State (Processes):")
    print(json.dumps(info, indent=2))

    # Step 3: Kill Anomalous Process Action
    # The anomaly for 'easy' is miner.sh (PID 99)
    kill_action = Action(command="kill_process", target="99")
    print("\n⚡ Executing Action: kill_process (Target: 99 / miner.sh)")
    final_obs, final_reward, final_done, final_info = env.step(kill_action)

    print_section("Final Observation after 'kill_process'", final_obs)
    print(f"Reward: {final_reward}")
    print(f"Done:   {final_done}")
    print(f"Command Output: {final_obs.command_output}")


if __name__ == "__main__":
    main()
