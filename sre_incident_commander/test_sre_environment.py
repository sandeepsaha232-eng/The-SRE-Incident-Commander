from sre_incident_commander.server.sre_environment import SREEnvironment
from sre_incident_commander.models import SreIncidentCommanderAction as Action

def test_sre_environment_easy():
    env = SREEnvironment()
    obs = env.reset("easy")
    
    # 5 + 10 + 2 + 90 = 107 -> capped at 100.0
    assert obs.cpu_usage == 100.0
    assert obs.system_status == "CRITICAL"
    
    obs, reward, done, info = env.step(Action(command="kill_process", target="miner.sh"))
    # cpu: 5 + 10 + 2 = 17.0
    assert obs.cpu_usage == 17.0
    assert obs.system_status == "HEALTHY"
    assert reward == 1.0
    assert done is True
    assert "miner.sh" not in obs.command_output

def test_sre_environment_medium():
    env = SREEnvironment()
    obs = env.reset("medium")
    
    assert obs.cpu_usage == 87.0
    assert obs.system_status == "CRITICAL"
    
    obs, reward, done, info = env.step(Action(command="kill_process", target="crypto_miner"))
    assert obs.cpu_usage == 17.0
    assert reward == 1.0
    assert done is True

def test_sre_environment_hard():
    env = SREEnvironment()
    obs = env.reset("hard")
    
    assert obs.cpu_usage == 100.0
    assert obs.system_status == "CRITICAL"
    
    obs, reward, done, info = env.step(Action(command="kill_process", target="malware"))
    assert obs.cpu_usage == 17.0
    assert reward == 1.0
    assert done is True

if __name__ == "__main__":
    test_sre_environment_easy()
    test_sre_environment_medium()
    test_sre_environment_hard()
    print("All tests passed!")
