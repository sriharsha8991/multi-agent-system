from mas.orchestrator.agent import build_agent
from mas.agents import specialists


sql_agent = specialists.sql_agent().get_graph().draw_mermaid_png()
graph_agent = specialists.graph_agent().get_graph().draw_mermaid_png()
coder_agent = specialists.coder_agent().get_graph().draw_mermaid_png()

orch = build_agent().get_graph().draw_mermaid_png()
print(build_agent().get_config_jsonschema())
with open("tests/sql_graph.png", "wb") as f:
    f.write(sql_agent)