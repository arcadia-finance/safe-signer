import os
import sys

_tests_dir = os.path.dirname(__file__)
_project_dir = os.path.join(_tests_dir, "..")

sys.path.insert(0, _project_dir)
sys.path.insert(0, _tests_dir)
