#!/usr/bin/env python3
import sys
from pathlib import Path

# Add src directory to Python path
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

# Now import and run the server
from census_mcp_server import main
import asyncio

if __name__ == "__main__":
    asyncio.run(main())
