"""
Patches for third-party libraries to fix compatibility issues.
"""


def apply_all_patches():
    """Apply all patches for third-party libraries."""
    from . import gemini_compat

    gemini_compat.apply_patch()
