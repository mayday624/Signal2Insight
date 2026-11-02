"""
Streamlit Community Cloud Main Entrypoint
Auto-detected by share.streamlit.io upon repository selection.
"""
import sys
from pathlib import Path

# Ensure root workspace directory is on sys.path
ROOT_DIR = Path(__file__).resolve().parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from frontend.dashboard import render_dashboard

if __name__ == "__main__":
    render_dashboard()

