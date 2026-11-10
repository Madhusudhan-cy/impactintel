"""
Shared pytest configuration and fixtures for backend tests.

Sets ALLOW_DEV_BYPASS=true for all tests so that mock OAuth and sample-repo
fallbacks are available without requiring real GitHub credentials.
"""
import os

# Enable dev bypass for all tests (before any app modules are imported by pytest-collection)
os.environ.setdefault("ALLOW_DEV_BYPASS", "true")
