"""
后端国际化支持模块

提供多语言支持，根据用户设置返回对应的提示信息
"""

from .translations import get_text, get_language_from_settings
from .messages import BackendMessages

__all__ = ["get_text", "get_language_from_settings", "BackendMessages"] 