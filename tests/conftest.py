"""
Make sure that pytest detects the fixtures in fix.py.
"""

pytest_plugins = ["tests.fix"]  # Load test fixtures
