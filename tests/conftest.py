import sys
from pathlib import Path

# Let tests import app.py from the project folder.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
