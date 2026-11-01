"""
Signal2Insight CLI Runner
Usage:
  python run.py api        # Run FastAPI backend on port 8000
  python run.py dashboard  # Run Streamlit dashboard on port 8501
  python run.py all        # Run both FastAPI & Streamlit concurrently
"""

import argparse
import subprocess
import sys
import time


def run_api():
    print("🚀 Launching Signal2Insight FastAPI server on http://localhost:8000 ...")
    print("📖 Swagger Docs: http://localhost:8000/docs")
    print("📊 Web Dashboard: http://localhost:8000/dashboard")
    subprocess.run([
        sys.executable, "-m", "uvicorn", "app.main:app",
        "--host", "0.0.0.0",
        "--port", "8000",
        "--reload"
    ])


def run_dashboard():
    print("🚀 Launching Signal2Insight Streamlit dashboard on http://localhost:8501 ...")
    subprocess.run([
        sys.executable, "-m", "streamlit", "run", "frontend/dashboard.py",
        "--server.port", "8501",
        "--server.headless", "true"
    ])


def run_all():
    print("🚀 Launching Signal2Insight Full Stack (FastAPI + Streamlit)...")
    print("• FastAPI Backend:     http://localhost:8000")
    print("• Built-in Dashboard:  http://localhost:8000/dashboard")
    print("• Streamlit Dashboard: http://localhost:8501")
    print("• Interactive Docs:    http://localhost:8000/docs")

    api_proc = subprocess.Popen([
        sys.executable, "-m", "uvicorn", "app.main:app",
        "--host", "0.0.0.0",
        "--port", "8000"
    ])

    time.sleep(2)

    dash_proc = subprocess.Popen([
        sys.executable, "-m", "streamlit", "run", "frontend/dashboard.py",
        "--server.port", "8501",
        "--server.headless", "true"
    ])

    try:
        api_proc.wait()
        dash_proc.wait()
    except KeyboardInterrupt:
        print("\nStopping services...")
        api_proc.terminate()
        dash_proc.terminate()


def main():
    parser = argparse.ArgumentParser(description="Signal2Insight Runner")
    parser.add_argument(
        "mode",
        nargs="?",
        default="all",
        choices=["api", "dashboard", "all"],
        help="Component to run ('api', 'dashboard', or 'all')",
    )
    args = parser.parse_args()

    if args.mode == "api":
        run_api()
    elif args.mode == "dashboard":
        run_dashboard()
    else:
        run_all()


if __name__ == "__main__":
    main()
