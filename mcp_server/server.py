import os
import base64
from mcp.server.fastmcp import FastMCP

# Initialize FastMCP server
mcp = FastMCP("MemoirPhotoServer")

PHOTO_DIR = "/Users/avyukt/Desktop/memoir-agent/mock_data/photos"

@mcp.tool()
def list_photos() -> str:
    """Lists all available mock historical photos in the directory."""
    if not os.path.exists(PHOTO_DIR):
        return "Photo directory not found."
    files = os.listdir(PHOTO_DIR)
    return f"Available photos: {', '.join(files)}"

@mcp.tool()
def read_photo(filename: str) -> str:
    """
    Reads a photo and returns its base64 encoding.
    Args:
        filename: The exact name of the file (e.g., 'vintage_roadtrip_123.jpg')
    """
    path = os.path.join(PHOTO_DIR, filename)
    if not os.path.exists(path):
        return f"File {filename} not found."
    
    with open(path, "rb") as f:
        encoded = base64.b64encode(f.read()).decode("utf-8")
        
    return f"data:image/jpeg;base64,{encoded}"

if __name__ == "__main__":
    mcp.run(transport='stdio')
