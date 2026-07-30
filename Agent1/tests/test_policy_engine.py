from agent1.policies import PolicyEngine


def test_policy_blocks_dangerous_command() -> None:
    engine = PolicyEngine()
    decision = engine.evaluate_command("git reset --hard HEAD")
    assert decision.allowed is False


def test_policy_allows_safe_command() -> None:
    engine = PolicyEngine()
    decision = engine.evaluate_command("pytest -q")
    assert decision.allowed is True
