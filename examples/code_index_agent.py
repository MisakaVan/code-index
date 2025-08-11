"""Try to implement an agent that can index code files and answer questions about them."""

import asyncio
import uuid
from pathlib import Path

from langchain_deepseek import ChatDeepSeek
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_mcp_adapters.tools import load_mcp_tools
from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import create_react_agent

current_file = Path(__file__).resolve()
project_root = current_file.parent.parent

# noinspection PyTypeChecker
client = MultiServerMCPClient(
    {
        "CodeIndex": {
            "transport": "stdio",
            "command": "uv",
            "args": [
                "run",
                "fastmcp",
                "run",
                "code_index/mcp_server/server.py:mcp",
                # "--project",
                # str(project_root),
            ],
        },
        "filesystem": {
            "transport": "stdio",
            "command": "npx",
            "args": [
                "-y",
                "@modelcontextprotocol/server-filesystem",
                str(project_root / "test_data"),
            ],
        },
    }
)

_tools = asyncio.run(client.get_tools())

# pprint(tools)
print("Got tools:")
for tool in _tools:
    print(f"  - {tool.name}")

llm = ChatDeepSeek(
    model="deepseek-chat", temperature=0, max_tokens=None, timeout=None, max_retries=2
)
memory_saver = MemorySaver()


async def chat_with_agent(code_index_session):
    """Main chat loop for interacting with the code index agent."""
    # Generate a unique thread ID for this conversation session
    thread_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}

    tools = await load_mcp_tools(code_index_session)
    agent = create_react_agent(model=llm, tools=tools, checkpointer=memory_saver)

    print("🤖 CodeIndex Agent Ready!")
    print("=" * 50)

    while True:
        try:
            # Get user input
            user_input = input("\n💬 You: ").strip()

            # Check for exit commands
            if user_input.lower() in ["quit", "exit", "bye", "q"]:
                print("\n👋 Goodbye!")
                break

            # Skip empty input
            if not user_input:
                continue

            # Stream the response from the agent

            # noinspection PyTypeChecker
            async for chunk in agent.astream(
                {"messages": [{"role": "user", "content": user_input}]},
                config=config,
                stream_mode="values",
            ):
                chunk["messages"][-1].pretty_print()

        except KeyboardInterrupt:
            print("\n\n👋 Chat interrupted. Goodbye!")
            break
        except EOFError:
            # User pressed Ctrl-D (EOF) – treat as graceful quit
            print("\n\n👋 Received EOF (Ctrl-D). Goodbye!")
            break
        except Exception as e:
            print(f"\n❌ Error: {e}")
            print("Please try again or type 'quit' to exit.")


async def main():
    """Entry point for the code index agent."""
    try:
        async with client.session("CodeIndex") as code_index_session:
            # maintain a session with the MCP server so that it does not restart every time
            await chat_with_agent(code_index_session)
    except Exception as e:
        print(f"Failed to start agent: {e}")
    finally:
        # Clean up the MCP client
        print("🧹 Cleaning up...")


if __name__ == "__main__":
    asyncio.run(main())
