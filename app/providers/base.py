from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ProviderInfo:
    code: str
    name: str
    adapter: str
    status: str
    auth_required: bool
    capabilities: tuple[str, ...]
