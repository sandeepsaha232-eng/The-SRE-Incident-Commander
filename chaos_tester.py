from sre_incident_commander.server.sre_environment import SREEnvironment
from sre_incident_commander.models import SreIncidentCommanderAction as Action


def main():
    print("🚀 Initializing SREEnvironment for Chaos Testing...")
    env = SREEnvironment()

    print("\n" + "=" * 60)
    print("--- Test 1: The Evolving Memory Leak & OOM Killer ---")
    
    # 1. Init 'hard' mode
    obs = env.reset(task_level="hard")
    print(f"Initial Memory Usage: {obs.memory_usage:.2f}%")
    print("-" * 60)

    # 2. Loop 15 times to trigger memory leak and OOM
    for step_num in range(1, 16):
        action = Action(command="check_metrics")
        obs, reward, done, info = env.step(action)
        
        print(f"Step {step_num:02d} | Memory: {obs.memory_usage:6.2f}% | Output: {obs.command_output}")
        
        if done:
            print("-" * 60)
            print(f"Episode Done at Step {step_num}!")
            print(f"Final Reward: {reward}")
            print(f"Final Status: {obs.system_status}")
            break

    print("\n" + "=" * 60)
    print("--- Test 2: Graceful Bash Error Handling ---")
    
    # 3. Init 'easy' mode
    env.reset(task_level="easy")
    
    # 4. Try to kill non-existent PID 9999
    bad_action = Action(command="kill_process", target="9999")
    obs, reward, done, info = env.step(bad_action)
    
    print("Action Executed: kill_process (Target: 9999)")
    print(f"Command Output : {obs.command_output}")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()
