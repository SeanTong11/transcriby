#!/usr/bin/env python3

import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from transcriby import transcriby

if __name__ == "__main__":
    transcriby.main()
