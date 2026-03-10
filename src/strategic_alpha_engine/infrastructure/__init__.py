from importlib import import_module

__all__ = [
    "FakeBrainSimulationClient",
    "LocalFileArtifactLedger",
    "LocalFileStateLedger",
    "OpenAICompatibleStructuredLLMClient",
    "WorldQuantBrainSimulationClient",
]


def __getattr__(name: str):
    if name == "LocalFileArtifactLedger":
        return import_module("strategic_alpha_engine.infrastructure.artifacts").LocalFileArtifactLedger
    if name == "LocalFileStateLedger":
        return import_module("strategic_alpha_engine.infrastructure.state").LocalFileStateLedger
    if name == "FakeBrainSimulationClient":
        return import_module("strategic_alpha_engine.infrastructure.brain").FakeBrainSimulationClient
    if name == "WorldQuantBrainSimulationClient":
        return import_module("strategic_alpha_engine.infrastructure.brain").WorldQuantBrainSimulationClient
    if name == "OpenAICompatibleStructuredLLMClient":
        return import_module("strategic_alpha_engine.infrastructure.llm").OpenAICompatibleStructuredLLMClient
    raise AttributeError(name)

