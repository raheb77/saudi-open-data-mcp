import os

import httpx

HTTP_AUTH_TOKEN = os.getenv("HTTP_AUTH_TOKEN", "dev-internal-token")
BASE_URL = os.getenv("MCP_HTTP_URL", "http://127.0.0.1:9000/mcp")
PROTOCOL_VERSION = "2025-11-25"

def test_mcp():
    print(f"Testing MCP over HTTP at {BASE_URL}...")
    
    with httpx.Client(timeout=30.0) as client:
        # 1. Initialize
        print("\n1. Initializing...")
        init_req = {
            "jsonrpc": "2.0",
            "id": "init-1",
            "method": "initialize",
            "params": {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": {"name": "test-client", "version": "0.1.0"},
            },
        }
        headers = {
            "Accept": "application/json, text/event-stream",
            "Content-Type": "application/json",
            "Authorization": f"Bearer {HTTP_AUTH_TOKEN}",
        }
        resp = client.post(BASE_URL, json=init_req, headers=headers)
        print(f"Status: {resp.status_code}")
        if resp.status_code != 200:
            print(f"Error: {resp.text}")
            return
            
        session_id = resp.headers.get("mcp-session-id")
        print(f"Session ID: {session_id}")
        
        # 2. Initialized notification
        print("\n2. Sending initialized notification...")
        headers["mcp-session-id"] = session_id
        headers["mcp-protocol-version"] = PROTOCOL_VERSION
        notif = {
            "jsonrpc": "2.0",
            "method": "notifications/initialized",
        }
        resp = client.post(BASE_URL, json=notif, headers=headers)
        print(f"Status: {resp.status_code}")
        
        # 3. List tools
        print("\n3. Listing tools...")
        list_tools_req = {
            "jsonrpc": "2.0",
            "id": "list-tools-1",
            "method": "tools/list",
        }
        resp = client.post(BASE_URL, json=list_tools_req, headers=headers)
        print(f"Status: {resp.status_code}")
        tools = resp.json().get("result", {}).get("tools", [])
        print(f"Found {len(tools)} tools:")
        for tool in tools:
            print(f"- {tool['name']}")
            
        # 4. Search datasets
        print("\n4. Searching datasets for 'money'...")
        search_req = {
            "jsonrpc": "2.0",
            "id": "search-1",
            "method": "tools/call",
            "params": {
                "name": "search_datasets",
                "arguments": {"query": "money"},
            },
        }
        resp = client.post(BASE_URL, json=search_req, headers=headers)
        print(f"Status: {resp.status_code}")
        print(resp.json()["result"]["content"][0]["text"])

        # 5. Dataset Health
        print("\n5. Checking health for 'sama-money-supply-weekly'...")
        health_req = {
            "jsonrpc": "2.0",
            "id": "health-1",
            "method": "tools/call",
            "params": {
                "name": "dataset_health",
                "arguments": {"dataset_id": "sama-money-supply-weekly"},
            },
        }
        resp = client.post(BASE_URL, json=health_req, headers=headers)
        print(f"Status: {resp.status_code}")
        print(resp.json()["result"]["content"][0]["text"])

        # 6. Auth failure test
        print("\n6. Testing auth failure with wrong token...")
        bad_headers = headers.copy()
        bad_headers["Authorization"] = "Bearer wrong-token"
        resp = client.post(BASE_URL, json=list_tools_req, headers=bad_headers)
        print(f"Status: {resp.status_code}")
        print(f"Response: {resp.json()}")

if __name__ == "__main__":
    test_mcp()
