from dataclasses import dataclass, field
from collections import Counter


@dataclass
class TypeFeedbackEntry:
    code_id: str = ""
    _types: list[type] = field(default_factory=list)
    _max_entries: int = 100

    def record_type(self, value):
        self._types.append(type(value))
        if len(self._types) > self._max_entries:
            self._types = self._types[-self._max_entries:]

    def dominant_type(self) -> type | None:
        if not self._types:
            return None
        counter = Counter(self._types)
        return counter.most_common(1)[0][0]

    def type_distribution(self) -> dict[type, float]:
        if not self._types:
            return {}
        counter = Counter(self._types)
        total = len(self._types)
        return {t: c / total for t, c in counter.items()}

    def reset(self):
        self._types = []