import subprocess
import sys
import os

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
script = os.path.join(CURRENT_DIR, "download_hd_backgrounds.py")
subprocess.run([sys.executable, script])
