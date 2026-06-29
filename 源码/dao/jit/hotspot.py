from dataclasses import dataclass, field


@dataclass
class HotspotRecord:
    code_id: str = ""
    count: int = 0
    threshold: int = 100

    def is_hot(self) -> bool:
        return self.count >= self.threshold


class HotspotDetector:
    def __init__(self, threshold: int = 100):
        self._threshold = threshold
        self._records: dict[str, HotspotRecord] = {}

    def record_execution(self, code_id: str):
        if code_id not in self._records:
            self._records[code_id] = HotspotRecord(code_id=code_id, threshold=self._threshold)
        self._records[code_id].count += 1

    def is_hot(self, code_id: str) -> bool:
        if code_id not in self._records:
            return False
        return self._records[code_id].is_hot()

    def get_count(self, code_id: str) -> int:
        if code_id not in self._records:
            return 0
        return self._records[code_id].count

    def reset(self, code_id: str):
        if code_id in self._records:
            self._records[code_id].count = 0