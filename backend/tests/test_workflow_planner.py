from groundline.config import Settings
from groundline.workflow import OllamaPlanner


class FakeModelClient:
    def __init__(self, payload: dict):
        self.payload = payload
        self.prompts: list[str] = []

    async def complete(self, prompt: str) -> dict:
        self.prompts.append(prompt)
        return self.payload


async def test_planner_uses_configured_model_client() -> None:
    client = FakeModelClient({"tools": ["vector"], "kind": "semantic"})
    settings = Settings(chat_provider="openrouter")

    plan = await OllamaPlanner(settings, client=client).plan("How does retrieval work?")

    assert plan.tools == ["vector"]
    assert client.prompts


async def test_planner_falls_back_when_model_client_fails() -> None:
    class FailingModelClient:
        async def complete(self, prompt: str) -> dict:
            raise RuntimeError("provider unavailable")

    plan = await OllamaPlanner(
        Settings(chat_provider="openrouter"), client=FailingModelClient()
    ).plan("Who owns the API?")

    assert plan.tools
