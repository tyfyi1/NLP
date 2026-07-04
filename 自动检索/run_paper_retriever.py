import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import asyncio
from paper_retriever.main import interactive_mode

if __name__ == "__main__":
    asyncio.run(interactive_mode())