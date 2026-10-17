import os

from adapters.gemini import build_agent_model
from bara_agent.agent import build_coordinator
from config import load_settings
from evals.agent_eval.scenarios import build_scenarios
from evals.agent_eval.world import build_world_tools

settings = load_settings(os.environ)
root_agent = build_coordinator(
    build_agent_model(settings),
    build_world_tools(build_scenarios(), settings.grid_cell_m),
)
