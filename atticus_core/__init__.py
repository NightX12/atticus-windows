"""Platform-neutral parts of the Atticus brain, ported from SaarthurR/atticus-mac (MIT): the About-you profile, memory
rules, model choice and routing, feedback and opt-in telemetry. No osascript, no ctypes: the same code runs on
Windows, macOS and Linux CI.

atticus.py (or a test) points it at its folder and settings once:  atticus_core.config.setup(DIR, pref)"""
from . import config
