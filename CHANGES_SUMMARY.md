# Changes made in `backend/`

## 1. Orchestrator Improvements (`backend/orchestrator.py`)
- **Implemented `hydrate_state`**: A utility function to convert plain dictionary states (common when loading from JSON caches or API requests) back into their proper Pydantic model equivalents (`EventConfigInput`, `SponsorSchema`, etc.).
- **Updated `rerun_nodes`**: Now automatically hydrates the state before execution. This prevents `AttributeError` in agents that use dot-notation (e.g., `cfg.category`) when being re-run from the Chat Agent.
- **Updated `run_plan` and `_initial_state`**: Added safety checks to ensure `event_config` is always a proper `EventConfigInput` object.

## 2. Testing & Verification
- **Added `tests/test_state_hydration.py`**: Unit tests verifying that the hydration logic correctly converts dicts to models and that agents can access fields successfully.

# Changes made in `frontend/`

## 1. UI/UX Improvements
- **Resolved Horizontal Scrolling**: Removed `overflow-x-hidden` from the root layout to allow side-scrolling when content (like long logs or graphs) exceeds screen width.
- **Improved Dashboard Spacing**: Restructured the main dashboard grid to provide more horizontal room for high-density components (Agent Graph, What-If Simulator, Agent Logs).
- **Markdown Support**: Integrated `react-markdown` and `remark-gfm` into the chat widget to correctly render AI responses (headers, bold text, etc.).
- **Text Wrapping**: Applied word-breaking styles to chat bubbles, log entries, and schedule items to prevent layout distortion from long strings.
