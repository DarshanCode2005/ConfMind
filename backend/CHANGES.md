# Backend Changes

## State Hydration & Serialization
- Added `hydrate_state` to `orchestrator.py` to convert dicts to Pydantic models.
- Added `_dump_state` to `main.py` to convert Pydantic models to dicts for JSON output.

## Chat Agent Integration
- Added `update_plan_parameter` tool to `ChatAgent`.
- Updated `/api/chat` to apply configuration updates and report agent status during reruns.
- Fixed `AttributeError` in agents by ensuring `AgentState` is hydrated before execution.
