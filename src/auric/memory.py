"""Reference-counted memory management for Auric runtime."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class RefValue:
    """Reference-counted value for measurement."""

    data: Any
    rc: int = 1
    _id: int = None

    def __post_init__(self):
        if self._id is None:
            object.__setattr__(self, "_id", id(self))

    def __repr__(self):
        if isinstance(self.data, tuple):
            tag, *fields = self.data
            if not fields:
                return tag
            return f"{tag}({', '.join(str(f) for f in fields)})"
        if callable(self.data):
            return "<fn>"
        return str(self.data)


class Heap:
    """Track allocations for performance measurement."""

    allocations = 0
    peak_objects = 0
    current_objects = 0
    total_clones = 0
    enabled = False

    @classmethod
    def reset(cls):
        cls.allocations = 0
        cls.peak_objects = 0
        cls.current_objects = 0
        cls.total_clones = 0

    @classmethod
    def enable(cls):
        cls.enabled = True

    @classmethod
    def alloc(cls, data: Any) -> RefValue:
        if cls.enabled:
            cls.allocations += 1
            cls.current_objects += 1
            cls.peak_objects = max(cls.peak_objects, cls.current_objects)
        return RefValue(data, rc=1)

    @classmethod
    def clone(cls, v: RefValue) -> RefValue:
        if cls.enabled:
            cls.total_clones += 1
        v.rc += 1
        return v

    @classmethod
    def drop(cls, v: Optional[RefValue]) -> None:
        if v is None:
            return
        v.rc -= 1
        if v.rc == 0 and cls.enabled:
            cls.current_objects -= 1

    @classmethod
    def stats(cls):
        return {
            "allocations": cls.allocations,
            "peak_objects": cls.peak_objects,
            "current_objects": cls.current_objects,
            "total_clones": cls.total_clones,
        }
