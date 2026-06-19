from fastmcp import FastMCP
import requests
import argparse

mcp = FastMCP(name="Media Stack MCP")

# TRAKT_API_BASE = "https://api.trakt.tv"

@mcp.tool
def get_ip_address() -> str:
    """
    Get IP address of server
    """

    response = requests.get("https://ipinfo.io/json")
    if response.status_code == 200:
        return response.json().get("ip")
    else:
        return "Unable to fetch IP address"
    
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the Media Stack MCP server.")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="Host address to bind the server to")
    parser.add_argument("--port", type=int, default=8000, help="Port to bind the server to")
    parser.add_argument("--transport", type=str, default="streamable-http", help="Transport protocol to use (default: streamable-http)")
    args = parser.parse_args()

    mcp.run(transport=args.transport, host=args.host, port=args.port)