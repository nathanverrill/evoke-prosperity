"""
LMS Adapters for EVOKE Prosperity

Provides interfaces and implementations for connecting EVOKE to various LMS platforms.
Currently supports Brightspace (D2L).
"""

from .brightspace_lms import BrightspaceLMS, get_brightspace_lms

__all__ = ["BrightspaceLMS", "get_brightspace_lms"]
