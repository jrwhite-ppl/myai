"""
Storage layer for MyAI.

This package provides storage abstractions and implementations for
configuration files, agent specifications, and other data persistence needs.
"""

from myai.storage.agent import AgentStorage
from myai.storage.base import Storage, StorageError
from myai.storage.config import ConfigStorage
from myai.storage.filesystem import FileSystemStorage

__all__ = [
    "Storage",
    "StorageError",
    "FileSystemStorage",
    "ConfigStorage",
    "AgentStorage",
]
