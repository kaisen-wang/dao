#!/usr/bin/env python3
r"""道语言 —— 跨平台系统级安装包构建脚本。

由 GitHub Actions / Gitee Go 调用，也可在本地运行。流程：
  1. 从 ``dao/version.py`` 读取版本号（单一来源）；
  2. 用 Nuitka 把 ``main.py`` 编译为 onefile 单文件可执行；
  3. 按当前平台生成系统级安装包：
       - Linux   → .deb   （dpkg-deb，安装到 /usr/bin/dao）
       - macOS   → .pkg   （pkgbuild，安装到 /usr/local/bin/dao）
       - Windows → setup.exe（Inno Setup，安装到 Program Files\Dao）
  4. 产物统一输出到 ``dist/installers/``。

用法：
    python 构建安装包.py                    # 构建 + 打包
    python 构建安装包.py --no-build         # 跳过编译，用已有 dist/nuitka/dao
    python 构建安装包.py --arch-label arm64 # 覆盖架构标签（交叉产物命名）
"""

from __future__ import annotations

import argparse
import os
import platform
import shutil
import subprocess
import sys
import sysconfig
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "源码"
sys.path.insert(0, str(SRC))

from dao.version import __version__ as DEFAULT_VERSION

BUILD_DIR = ROOT / "dist" / "nuitka"
OUT_DIR = ROOT / "dist" / "installers"


def run(cmd: list[str], *, cwd: Path | None = None) -> None:
    """执行命令，失败立即抛错（中文提示）。"""
    print(f"[执行] {' '.join(cmd)}", flush=True)
    subprocess.run([str(c) for c in cmd], cwd=cwd, check=True)


def detect_os() -> str:
    """返回 linux / macos / windows。"""
    if sys.platform.startswith("linux"):
        return "linux"
    if sys.platform == "darwin":
        return "macos"
    if sys.platform == "win32":
        return "windows"
    raise RuntimeError(f"不支持的构建平台：{sys.platform}")


def detect_arch() -> tuple[str, str]:
    """返回 (Debian 架构名, 通用架构标签)。"""
    machine = platform.machine().lower()
    if machine in ("x86_64", "amd64"):
        return "amd64", "x86_64"
    if machine in ("aarch64", "arm64"):
        return "arm64", "arm64"
    return machine, machine


def ensure_patchelf() -> None:
    """Linux 下确保 patchelf 可用（Nuitka onefile/standalone 必需）。

    Gitee Go / GitHub Actions 的干净 runner 常缺此工具，且未必有 sudo/apt
    权限。PyPI 的 ``patchelf`` wheel 自带二进制，pip 安装后 exe 落在解释器
    同目录（已在 PATH 或 sysconfig scripts 目录），是最稳的补装方式。
    """
    if shutil.which("patchelf") is not None:
        return
    print("[提示] 未检测到 patchelf，Nuitka Linux onefile 需要它，正在通过 pip 安装…", flush=True)
    run([sys.executable, "-m", "pip", "install", "patchelf"])
    if shutil.which("patchelf") is None:
        # pip 装到用户 scripts 目录（如 ~/.local/bin）时可能未进 PATH，补加。
        scripts = Path(sysconfig.get_path("scripts"))
        candidate = scripts / "patchelf"
        if candidate.exists():
            os.environ["PATH"] = f"{scripts}{os.pathsep}{os.environ.get('PATH', '')}"
            print(f"[提示] 已将 {scripts} 加入 PATH", flush=True)
        else:
            raise RuntimeError("patchelf 安装后仍不可用，请手动安装：python -m pip install patchelf")


def build_onefile(os_name: str) -> Path:
    """用 Nuitka 编译 onefile，返回可执行文件绝对路径。"""
    exe_name = "dao.exe" if os_name == "windows" else "dao"
    BUILD_DIR.mkdir(parents=True, exist_ok=True)
    if os_name == "linux":
        ensure_patchelf()
    run([
        sys.executable, "-m", "nuitka",
        "--onefile",
        "--include-package=dao",
        f"--output-filename={exe_name}",
        f"--output-dir={BUILD_DIR}",
        "--assume-yes-for-downloads",
        "main.py",
    ], cwd=SRC)
    exe = BUILD_DIR / exe_name
    if not exe.exists():
        raise RuntimeError(f"编译未生成预期产物：{exe}")
    return exe


def require_tool(name: str) -> None:
    """检查外部工具是否在 PATH 中。"""
    if shutil.which(name) is None:
        raise RuntimeError(f"缺少打包工具 {name}，请先安装（见文档 17）")


def make_deb(exe: Path, version: str, arch_deb: str, arch_label: str) -> Path:
    """生成 Debian 包，安装到 /usr/bin/dao。"""
    require_tool("dpkg-deb")
    stage = OUT_DIR / f".debwork-{version}-{arch_label}"
    if stage.exists():
        shutil.rmtree(stage)
    (stage / "DEBIAN").mkdir(parents=True)
    bindir = stage / "usr" / "bin"
    bindir.mkdir(parents=True)

    target = bindir / "dao"
    shutil.copy2(exe, target)
    target.chmod(0o755)

    control = (
        f"Package: dao\n"
        f"Version: {version}\n"
        f"Section: utils\n"
        f"Priority: optional\n"
        f"Architecture: {arch_deb}\n"
        f"Maintainer: 道语言项目组 <dao-lang@example.com>\n"
        f"Homepage: https://gitee.com/kaisen-wang/dao\n"
        f"Description: 道（Dao）编程语言解释器\n"
        f" 中文多范式编程语言，支持命令式、函数式、面向对象与逻辑编程。\n"
        f" 单文件原生可执行，包含 AST 解释器与字节码 VM/JIT 双执行模式。\n"
    )
    (stage / "DEBIAN" / "control").write_text(control, encoding="utf-8")
    (stage / "DEBIAN" / "control").chmod(0o644)

    deb = OUT_DIR / f"dao_{version}_linux_{arch_label}.deb"
    # --root-owner-group：CI 中以非 root 构建时，避免所有权警告且保证安装后属主为 root
    run(["dpkg-deb", "--build", "--root-owner-group", str(stage), str(deb)])
    shutil.rmtree(stage)
    return deb


def make_pkg(exe: Path, version: str, arch_label: str) -> Path:
    """生成 macOS 安装包，安装到 /usr/local/bin/dao。"""
    require_tool("pkgbuild")
    stage = OUT_DIR / f".pkgroot-{version}-{arch_label}"
    if stage.exists():
        shutil.rmtree(stage)
    bindir = stage / "usr" / "local" / "bin"
    bindir.mkdir(parents=True)

    target = bindir / "dao"
    shutil.copy2(exe, target)
    target.chmod(0o755)

    pkg = OUT_DIR / f"dao_{version}_macos_{arch_label}.pkg"
    run([
        "pkgbuild",
        "--root", str(stage),
        "--identifier", "cn.dao.lang",
        "--version", version,
        "--install-location", "/",
        "--ownership", "recommended",
        str(pkg),
    ])
    shutil.rmtree(stage)
    return pkg


def make_windows_installer(exe: Path, version: str, arch_label: str) -> Path:
    """用 Inno Setup 生成 Windows 安装器 setup.exe。"""
    require_tool("iscc")
    exe_win = str(exe).replace("/", "\\")
    out_win = str(OUT_DIR).replace("/", "\\")
    base = f"dao_{version}_windows_{arch_label}_setup"

    iss = OUT_DIR / f".{base}.iss"
    iss.write_text(
        f"[Setup]\n"
        f"AppName=Dao Language\n"
        f"AppVersion={version}\n"
        f"DefaultDirName={{autopf}}\\Dao\n"
        f"DefaultGroupName=Dao Language\n"
        f"OutputDir={out_win}\n"
        f"OutputBaseFilename={base}\n"
        f"Compression=lzma2\n"
        f"SolidCompression=yes\n"
        f"PrivilegesRequired=admin\n"
        f"\n"
        f"[Languages]\n"
        f'Name: "english"; MessagesFile: "compiler:Default.isl"\n'
        f"\n"
        f"[Files]\n"
        f'Source: "{exe_win}"; DestDir: "{{app}}"; Flags: ignoreversion\n'
        f"\n"
        f"[Icons]\n"
        f'Name: "{{group}}\\Dao Language"; Filename: "{{app}}\\dao.exe"\n',
        encoding="utf-8",
    )
    run(["iscc", "/Qp", str(iss)])
    iss.unlink(missing_ok=True)

    installer = OUT_DIR / f"{base}.exe"
    if not installer.exists():
        raise RuntimeError(f"Inno Setup 未生成预期产物：{installer}")
    return installer


def main() -> int:
    parser = argparse.ArgumentParser(description="构建道语言系统级安装包")
    parser.add_argument("--no-build", action="store_true", help="跳过 Nuitka 编译，使用已有 dist/nuitka 产物")
    parser.add_argument("--version", default=DEFAULT_VERSION, help=f"版本号（默认 {DEFAULT_VERSION}）")
    parser.add_argument("--arch-label", default=None, help="覆盖架构标签（如 x86_64 / arm64）")
    args = parser.parse_args()

    os_name = detect_os()
    arch_deb, arch_detected = detect_arch()
    arch_label = args.arch_label or arch_detected

    print(f"=== 道语言安装包构建：{os_name} / {arch_label} / v{args.version} ===", flush=True)
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    if args.no_build:
        exe_name = "dao.exe" if os_name == "windows" else "dao"
        exe = BUILD_DIR / exe_name
        if not exe.exists():
            raise RuntimeError(f"--no-build 指定的产物不存在：{exe}")
    else:
        exe = build_onefile(os_name)

    if os_name == "linux":
        artifact = make_deb(exe, args.version, arch_deb, arch_label)
    elif os_name == "macos":
        artifact = make_pkg(exe, args.version, arch_label)
    else:
        artifact = make_windows_installer(exe, args.version, arch_label)

    size_mb = artifact.stat().st_size / 1024 / 1024
    print("\n=== 构建完成 ===", flush=True)
    print(f"产物：{artifact}", flush=True)
    print(f"大小：{size_mb:.1f} MB", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
