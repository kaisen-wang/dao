#!/usr/bin/env python3
"""
统一性能基准测试运行器
====================

运行所有性能基准测试并输出报告。
"""

import subprocess
import sys
import os
import time


def run_benchmark(name: str, module_path: str, args: list[str] | None = None) -> None:
    """运行单个基准测试"""
    print(f"\n{'=' * 50}")
    print(f"  {name}")
    print(f"{'=' * 50}")
    cmd = [sys.executable, module_path] + (args or [])
    start = time.time()
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=os.path.dirname(module_path))
    elapsed = time.time() - start
    print(result.stdout)
    if result.stderr:
        print(f"  [stderr] {result.stderr.strip()}")
    print(f"  耗时: {elapsed:.2f}s")


def run_pytest(path: str, benchmark_name: str) -> None:
    """通过 pytest 运行基准测试"""
    print(f"\n{'=' * 50}")
    print(f"  {benchmark_name} (pytest)")
    print(f"{'=' * 50}")
    cmd = [sys.executable, "-m", "pytest", path, "-v", "--benchmark", "-q"]
    start = time.time()
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=os.path.join(os.path.dirname(__file__), '..', '..'))
    elapsed = time.time() - start
    print(result.stdout[-2000:] if len(result.stdout) > 2000 else result.stdout)
    print(f"  耗时: {elapsed:.2f}s")


def main():
    print("道语言统一性能基准测试")
    print("=" * 50)

    benchmarks_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.join(benchmarks_dir, '..', '..')

    # 1. 通用性能基准
    run_benchmark("通用性能基准", os.path.join(benchmarks_dir, '性能基准.py'))

    # 2. 宏系统性能基准
    run_benchmark("宏系统性能基准", os.path.join(benchmarks_dir, 'test_macro_benchmark.py'))

    # 3. 逻辑编程性能基准
    run_benchmark("逻辑编程性能基准", os.path.join(benchmarks_dir, 'test_logic_benchmark.py'))

    # 4. 并发编程性能基准（通过 unittest）
    print(f"\n{'=' * 50}")
    print(f"  并发编程性能基准")
    print(f"{'=' * 50}")
    cmd = [sys.executable, "-m", "pytest", os.path.join(benchmarks_dir, 'test_concurrency_benchmark.py'), "-v", "-q"]
    start = time.time()
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=project_root)
    elapsed = time.time() - start
    output = result.stdout
    # 只显示结果摘要
    for line in output.split('\n'):
        if any(kw in line for kw in ['PASSED', 'FAILED', 'ERROR', 'benchmark', '平均', '吞吐', 'μs', 'ns', 'ms', 'ops']):
            print(f"  {line.strip()}")
    print(f"  耗时: {elapsed:.2f}s")

    print(f"\n{'=' * 50}")
    print(f"  全部完成")
    print(f"{'=' * 50}")


if __name__ == '__main__':
    main()
