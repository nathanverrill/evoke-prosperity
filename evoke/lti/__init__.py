"""
LTI (Learning Tools Interoperability) implementations for EVOKE Prosperity

Provides LTI 1.3 platform integration for launching EVOKE from LMS courses.
Currently supports D2L Brightspace.
"""

from .brightspace_lti_provider import BrightspaceLTIProvider, get_brightspace_lti_provider

__all__ = ["BrightspaceLTIProvider", "get_brightspace_lti_provider"]
