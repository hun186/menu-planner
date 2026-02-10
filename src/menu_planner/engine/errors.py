# src/menu_planner/engine/errors.py
from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass
class PlanError(Exception):
    code: str
    message: str
    day_index: Optional[int] = None
    details: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        out: Dict[str, Any] = {"code": self.code, "message": self.message}
        if self.day_index is not None:
            out["day_index"] = self.day_index
        if self.details:
            out["details"] = self.details
        return out
