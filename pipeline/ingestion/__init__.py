from dataclasses import dataclass, field
from typing import Dict, List, Any

@dataclass
class RawRecord:
    source_name: str
    raw_fields: Dict[str, Any] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)
