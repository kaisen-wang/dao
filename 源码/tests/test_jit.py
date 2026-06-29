import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dao.jit.hotspot import HotspotDetector, HotspotRecord
from dao.jit.type_feedback import TypeFeedbackEntry
from dao.jit.compiler import JitCompiler
from dao.bytecode.code_object import CodeObject


class TestHotspotDetector:
    def test_not_hot_initially(self):
        detector = HotspotDetector(threshold=3)
        assert not detector.is_hot("f")

    def test_becomes_hot(self):
        detector = HotspotDetector(threshold=3)
        detector.record_execution("f")
        detector.record_execution("f")
        detector.record_execution("f")
        assert detector.is_hot("f")

    def test_count(self):
        detector = HotspotDetector()
        detector.record_execution("f")
        detector.record_execution("f")
        assert detector.get_count("f") == 2

    def test_reset(self):
        detector = HotspotDetector(threshold=2)
        detector.record_execution("f")
        detector.record_execution("f")
        assert detector.is_hot("f")
        detector.reset("f")
        assert not detector.is_hot("f")


class TestTypeFeedback:
    def test_dominant_type(self):
        entry = TypeFeedbackEntry(code_id="f.x")
        entry.record_type(42)
        entry.record_type(10)
        entry.record_type("hello")
        assert entry.dominant_type() == int

    def test_type_distribution(self):
        entry = TypeFeedbackEntry(code_id="f.x")
        entry.record_type(42)
        entry.record_type("hello")
        dist = entry.type_distribution()
        assert abs(dist[int] - 0.5) < 0.01
        assert abs(dist[str] - 0.5) < 0.01

    def test_empty_feedback(self):
        entry = TypeFeedbackEntry(code_id="f.x")
        assert entry.dominant_type() is None
        assert entry.type_distribution() == {}

    def test_reset(self):
        entry = TypeFeedbackEntry(code_id="f.x")
        entry.record_type(42)
        entry.reset()
        assert entry.dominant_type() is None


class TestJitCompiler:
    def test_compile_hotspot(self):
        detector = HotspotDetector(threshold=1)
        compiler = JitCompiler(detector)
        code = CodeObject(name="f")
        result = compiler.compile_hotspot("f", code, {})
        assert result is not None
        assert result.name == "f_jit"

    def test_get_specialized(self):
        detector = HotspotDetector(threshold=1)
        compiler = JitCompiler(detector)
        code = CodeObject(name="f")
        compiler.compile_hotspot("f", code, {})
        assert compiler.get_specialized("f") is not None

    def test_deoptimization(self):
        detector = HotspotDetector(threshold=1)
        compiler = JitCompiler(detector)
        code = CodeObject(name="f")
        compiler.compile_hotspot("f", code, {})
        compiler.handle_deoptimization("f")
        assert compiler.get_specialized("f") is None

    def test_max_deopt(self):
        detector = HotspotDetector(threshold=1)
        compiler = JitCompiler(detector)
        code = CodeObject(name="f")
        for _ in range(3):
            compiler.handle_deoptimization("f")
        result = compiler.compile_hotspot("f", code, {})
        assert result is None