import platformdirs
from pathlib import Path
import os

USER_DATA_DIR = Path(platformdirs.user_data_dir("f1-dashboard", ensure_exists=True))
AUTH_DATA_FILE = USER_DATA_DIR / "f1auth.json"

print(f"Expected Auth File: {AUTH_DATA_FILE}")
print(f"Exists: {AUTH_DATA_FILE.exists()}")

if AUTH_DATA_FILE.exists():
    with open(AUTH_DATA_FILE, 'r') as f:
        content = f.read()
        print(f"Content length: {len(content)}")
        print(f"Content preview: {content[:20]}...")
else:
    print("File does not exist.")
    # List directory contents
    if USER_DATA_DIR.exists():
        print(f"Directory contents of {USER_DATA_DIR}:")
        print(os.listdir(USER_DATA_DIR))
    else:
        print(f"Directory {USER_DATA_DIR} does not exist.")
