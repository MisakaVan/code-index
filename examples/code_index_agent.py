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


def get_user_input() -> str:
    """
    Read a multi-line user message.
    A single blank line is kept as an intentional blank line.
    Two consecutive blank lines (double Enter) terminate input (the second is not included).
    Returns a single string (may contain '\n').
    """
    lines = []
    empty_streak = 0
    first = True
    try:
        while True:
            prompt = "\n💬 You: " if first else "... "
            first = False
            line = input(prompt)
            if line == "":
                empty_streak += 1
                if empty_streak == 2:
                    break  # second empty line ends input
                # keep first empty line as content
                lines.append("")
            else:
                empty_streak = 0
                lines.append(line)
    except EOFError:
        # propagate so outer loop can handle as exit
        raise
    except KeyboardInterrupt:
        # Return empty so outer loop can decide
        return ""
    return "\n".join(lines)


async def chat_with_agent(code_index_session):
    """Main chat loop for interacting with the code index agent."""
    # Generate a unique thread ID for this conversation session
    thread_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}

    tools = await load_mcp_tools(code_index_session)
    agent = create_react_agent(model=llm, tools=tools, checkpointer=memory_saver).with_config(
        recursion_limit=1000,
    )

    print("🤖 CodeIndex Agent Ready!")
    print("=" * 50)

    while True:
        try:
            user_input = get_user_input()

            # exit commands (checked on stripped single-line equivalent)
            if user_input.strip().lower() in ["quit", "exit", "bye", "q"]:
                print("\n👋 Goodbye!")
                break

            if not user_input.strip():
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
