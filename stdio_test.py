import asyncio

from fastmcp import Client
from fastmcp.client.transports import StdioTransport


async def test_stdio():
    print("Testing MCP over Stdio...")

    # Absolute path to python and cli.py
    python_path = "/Users/rahebalmutairi/Documents/saudi-open-data-mcp/.venv/bin/python"
    cli_path = "/Users/rahebalmutairi/Documents/saudi-open-data-mcp/src/saudi_open_data_mcp/cli.py"

    transport = StdioTransport(
        command=python_path,
        args=[cli_path, "run-stdio"],
        cwd="/Users/rahebalmutairi/Documents/saudi-open-data-mcp",
    )

    async with Client(transport=transport) as client:
        print("\n1. Listing tools...")
        tools = await client.list_tools()
        print(f"Found {len(tools)} tools.")

        print("\n2. Calling search_datasets(query='money'):")
        search_result = await client.call_tool("search_datasets", {"query": "money"})
        print(search_result.content[0].text)


if __name__ == "__main__":
    asyncio.run(test_stdio())
