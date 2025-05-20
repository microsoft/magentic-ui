"""
Simple check to verify version file imports.
"""
import os
import importlib.util

def load_module_from_path(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

base_dir = os.path.dirname(__file__)
version_module = load_module_from_path("version", os.path.join(base_dir, "src/magentic_ui/version.py"))
print(f"Version module: VERSION={version_module.VERSION}, __version__={version_module.__version__}")

# Try to import the module as if from backend
try:
    import sys
    sys.path.insert(0, os.path.join(base_dir, "src"))
    from magentic_ui.backend import __version__ as backend_version
    print(f"Backend version: {backend_version}")
except Exception as e:
    print(f"Error importing backend version: {e}")
    
print("Version imports test completed.")