"""
Configuration script to set up sys.path for running tests from verification_test directory
"""

import sys
import os
from pathlib import Path

def setup_paths():
    """Setup Python path to import from backend modules"""
    # Get the verification_test directory
    verification_test_dir = Path(__file__).parent
    
    # Get the backend directory (parent of verification_test)
    backend_dir = verification_test_dir.parent
    
    # Add backend to sys.path so we can import verification, models, etc.
    if str(backend_dir) not in sys.path:
        sys.path.insert(0, str(backend_dir))
    
    # Load .env file from project root
    try:
        from dotenv import load_dotenv
        # Go up 3 levels: verification_test -> backend -> apps -> vergil
        project_root = backend_dir.parent.parent
        env_path = project_root / ".env"
        if env_path.exists():
            load_dotenv(env_path)
    except ImportError:
        pass
    
    return backend_dir

if __name__ == "__main__":
    backend = setup_paths()
    print(f"Paths configured. Backend: {backend}")
    print(f"Python path includes: {sys.path[:2]}")
