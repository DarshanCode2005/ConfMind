import asyncio
import os
import sys
from pathlib import Path

# Add root to sys.path
root_dir = Path(__file__).parent.parent.resolve()
sys.path.append(str(root_dir))

from langchain_ollama import ChatOllama
from langchain_core.messages import HumanMessage, SystemMessage

async def check_thinking():
    print("="*60)
    print("    TESTING GEMMA4 THINKING & REASONING")
    print("="*60)
    
    # We use the confmind-planner model we created
    model_name = "confmind-planner"
    print(f"\n[OLLAMA] Initializing model: {model_name}")
    
    llm = ChatOllama(
        model=model_name,
        temperature=0.7, # higher temp for more "thinking"
        num_ctx=4096
    )

    prompt = (
        "Think step-by-step: How would you organize a community outreach strategy "
        "for an AI conference in London? Provide a detailed plan with 3 specific steps."
    )
    
    print(f"\n[PROMPT] {prompt}\n")
    print("-" * 60)
    print("[THINKING...]\n")

    messages = [
        SystemMessage(content="You are a strategic conference planner. Think deeply before answering."),
        HumanMessage(content=prompt)
    ]

    try:
        # Using stream to see the thinking in real-time
        async for chunk in llm.astream(messages):
            print(chunk.content, end="", flush=True)
        print("\n")
    except Exception as e:
        print(f"\n[ERROR] Failed to communicate with Ollama: {e}")

if __name__ == "__main__":
    asyncio.run(check_thinking())
