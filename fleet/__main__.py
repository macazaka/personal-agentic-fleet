"""
Executable module entrypoint for Personal Agentic Fleet.
Enables running the fleet directly via:
  python -m fleet [command]
"""

import sys
from fleet.cli import main

if __name__ == "__main__":
    sys.exit(main())

