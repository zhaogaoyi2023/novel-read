"""
Channels Module

This module contains different novel acquisition channels:
- Official channels (rankings, verified sources)
- Search-based channels (multi-engine search)
- Open source channels (community APIs)
"""

from .official import OfficialChannel
from .search import SearchChannel
from .opensource import OpenSourceChannel

__all__ = [
    "OfficialChannel",
    "SearchChannel",
    "OpenSourceChannel",
]
