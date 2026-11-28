from ..bytecode.code_object import CodeObject
from .hotspot import HotspotDetector
from .native import NativeCodegen, _Deopt
from .type_feedback import TypeFeedbackEntry


class JitCompiler:
    def __init__(self, hotspot_detector: HotspotDetector):
        self._hotspot_detector = hotspot_detector
        self._specialized: dict[str, CodeObject] = {}
        self._natives: dict = {}
        self._code_refs: dict = {}
        self._deopt_counts: dict[str, int] = {}
        self._max_deopt: int = 3

    def compile_hotspot(self, code_id: str, code: CodeObject,
                        feedback: dict[str, TypeFeedbackEntry]) -> CodeObject | None:
        if code_id in self._deopt_counts and self._deopt_counts[code_id] >= self._max_deopt:
            return None
        specialized = self._specialize(code, feedback)
        if specialized is not None:
            self._specialized[code_id] = specialized
            self._code_refs[code_id] = code
            generated = NativeCodegen(code, feedback, code_id).generate()
            if generated is not None:
                self._natives[code_id] = generated
        return specialized

    def get_specialized(self, code_id: str) -> CodeObject | None:
        return self._specialized.get(code_id)

    def get_native(self, code_id: str):
        """返回 ``(native_fn, ip_to_block)``；不存在时返回 ``None``。"""
        return self._natives.get(code_id)

    def deopt_count(self, code_id: str) -> int:
        return self._deopt_counts.get(code_id, 0)

    def native_count(self) -> int:
        return len(self._natives)

    def total_deopts(self) -> int:
        return sum(self._deopt_counts.values())

    def is_disabled(self, code_id: str) -> bool:
        return self._deopt_counts.get(code_id, 0) >= self._max_deopt

    def handle_deoptimization(self, code_id: str):
        if code_id not in self._deopt_counts:
            self._deopt_counts[code_id] = 0
        self._deopt_counts[code_id] += 1
        if code_id in self._specialized:
            del self._specialized[code_id]
        if code_id in self._natives:
            del self._natives[code_id]

    def _specialize(self, code: CodeObject, feedback: dict[str, TypeFeedbackEntry]) -> CodeObject | None:
        return CodeObject(
            name=f"{code.name}_jit",
            instructions=list(code.instructions),
            constants=list(code.constants),
            local_names=list(code.local_names),
            upvalue_names=list(code.upvalue_names),
            child_codes=list(code.child_codes),
            stack_size=code.stack_size,
        )


__all__ = ["JitCompiler", "_Deopt"]
