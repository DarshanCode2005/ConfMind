# LangChain & LangSmith Monitoring Skill

This document provides instructions on how to enable and use LangSmith for monitoring the ConfMind agentic backend.

## 1. Setup LangSmith

To monitor LangChain and LangGraph execution, you need a LangSmith account and an API key.

1.  Sign up at [smith.langchain.com](https://smith.langchain.com/).
2.  Create a new API key in Settings.
3.  Add the following variables to your `.env` file:

```bash
# LangSmith Monitoring
LANGCHAIN_TRACING_V2=true
LANGCHAIN_ENDPOINT="https://api.smith.langchain.com"
LANGCHAIN_API_KEY="ls__your_api_key_here"
LANGCHAIN_PROJECT="confmind-backend"
```

## 2. Dependencies

Ensure you have the `langsmith` package installed:

```bash
pip install langsmith
```

## 3. How it Works

LangChain and LangGraph are instrumented to automatically send traces to LangSmith if `LANGCHAIN_TRACING_V2=true` is set in the environment.

- **LLM Calls**: Every request to OpenAI, Ollama, etc., will be logged with inputs, outputs, and tokens.
- **Graph Execution**: The full LangGraph workflow in `orchestrator.py` will be visualized as a trace, showing the path through different agents.
- **Tools**: Tool execution, including searches and scraping, will be captured in the trace.

## 4. Manual Tracing (Optional)

If you need to trace custom functions that are NOT part of a LangChain runnable, you can use the `@traceable` decorator:

```python
from langsmith import traceable

@traceable
def my_custom_function(arg1):
    # ... logic ...
    return result
```

## 5. View Traces

Go to [LangSmith Projects](https://smith.langchain.com/projects) and select your project (`confmind-backend`) to see live traces of your agents' execution.