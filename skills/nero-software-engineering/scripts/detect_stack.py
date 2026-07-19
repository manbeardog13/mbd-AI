#!/usr/bin/env python3
"""Detect source languages and build manifests without third-party packages."""

from __future__ import annotations

import argparse
import fnmatch
import json
import os
import sys
from collections import Counter
from pathlib import Path
from typing import Iterable


IGNORE_DIRS = {
    ".git",
    ".hg",
    ".svn",
    ".idea",
    ".vscode",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".tox",
    ".venv",
    "venv",
    "node_modules",
    "bower_components",
    "vendor",
    "dist",
    "build",
    "target",
    "out",
    "bin",
    "obj",
    ".next",
    ".nuxt",
    ".gradle",
    ".terraform",
    "coverage",
}

EXTENSIONS = {
    ".adb": "Ada",
    ".ads": "Ada",
    ".agda": "Agda",
    ".asm": "Assembly",
    ".astro": "Astro",
    ".c": "C",
    ".cabal": "Haskell",
    ".cc": "C++",
    ".clj": "Clojure",
    ".cljs": "ClojureScript",
    ".cljc": "Clojure",
    ".cls": "Apex",
    ".cmake": "CMake",
    ".cob": "COBOL",
    ".cobol": "COBOL",
    ".coffee": "CoffeeScript",
    ".cpp": "C++",
    ".cr": "Crystal",
    ".cs": "C#",
    ".css": "CSS",
    ".cu": "CUDA",
    ".cuh": "CUDA",
    ".cxx": "C++",
    ".d": "D",
    ".dart": "Dart",
    ".ex": "Elixir",
    ".exs": "Elixir",
    ".f": "Fortran",
    ".f03": "Fortran",
    ".f08": "Fortran",
    ".f90": "Fortran",
    ".f95": "Fortran",
    ".fish": "fish shell",
    ".fs": "F#",
    ".fsx": "F#",
    ".go": "Go",
    ".graphql": "GraphQL",
    ".gql": "GraphQL",
    ".groovy": "Groovy",
    ".h": "C/C++ header",
    ".hcl": "HCL",
    ".hh": "C++ header",
    ".hpp": "C++ header",
    ".hs": "Haskell",
    ".html": "HTML",
    ".hx": "Haxe",
    ".hxx": "C++ header",
    ".idr": "Idris",
    ".java": "Java",
    ".jl": "Julia",
    ".js": "JavaScript",
    ".json": "JSON",
    ".jsx": "JavaScript JSX",
    ".kt": "Kotlin",
    ".kts": "Kotlin",
    ".lean": "Lean",
    ".less": "Less",
    ".lhs": "Haskell",
    ".lisp": "Common Lisp",
    ".lua": "Lua",
    ".m": "Objective-C/MATLAB",
    ".mdx": "MDX",
    ".metal": "Metal Shading Language",
    ".ml": "OCaml",
    ".mli": "OCaml",
    ".mm": "Objective-C++",
    ".move": "Move",
    ".nim": "Nim",
    ".nix": "Nix",
    ".pas": "Pascal",
    ".php": "PHP",
    ".pl": "Perl",
    ".pm": "Perl",
    ".pro": "Prolog",
    ".proto": "Protocol Buffers",
    ".ps1": "PowerShell",
    ".py": "Python",
    ".pyi": "Python typing",
    ".r": "R",
    ".raku": "Raku",
    ".rb": "Ruby",
    ".res": "ReScript",
    ".rs": "Rust",
    ".sass": "Sass",
    ".scala": "Scala",
    ".scm": "Scheme",
    ".scss": "SCSS",
    ".sh": "Shell",
    ".sol": "Solidity",
    ".sql": "SQL",
    ".svelte": "Svelte",
    ".swift": "Swift",
    ".tcl": "Tcl",
    ".tf": "Terraform HCL",
    ".toml": "TOML",
    ".ts": "TypeScript",
    ".tsx": "TypeScript TSX",
    ".v": "Verilog/Coq",
    ".vb": "Visual Basic .NET",
    ".vhd": "VHDL",
    ".vhdl": "VHDL",
    ".vue": "Vue SFC",
    ".wgsl": "WGSL",
    ".xml": "XML",
    ".yaml": "YAML",
    ".yml": "YAML",
    ".zig": "Zig",
}

BASENAME_LANGUAGES = {
    "dockerfile": "Dockerfile",
    "jenkinsfile": "Jenkins Pipeline",
    "makefile": "Make",
    "rakefile": "Ruby",
    "gemfile": "Ruby",
    "vagrantfile": "Ruby",
}

MANIFEST_PATTERNS = (
    ("package.json", "JavaScript/TypeScript package"),
    ("pnpm-lock.yaml", "pnpm lockfile"),
    ("yarn.lock", "Yarn lockfile"),
    ("package-lock.json", "npm lockfile"),
    ("deno.json*", "Deno project"),
    ("bun.lock*", "Bun lockfile"),
    ("pyproject.toml", "Python project"),
    ("requirements*.txt", "Python requirements"),
    ("pdm.lock", "PDM lockfile"),
    ("poetry.lock", "Poetry lockfile"),
    ("uv.lock", "uv lockfile"),
    ("go.mod", "Go module"),
    ("go.work", "Go workspace"),
    ("cargo.toml", "Rust package"),
    ("cargo.lock", "Rust lockfile"),
    ("pom.xml", "Maven project"),
    ("build.gradle*", "Gradle project"),
    ("settings.gradle*", "Gradle settings"),
    ("*.sbt", "Scala sbt project"),
    ("*.csproj", ".NET project"),
    ("*.fsproj", "F# project"),
    ("*.vbproj", "Visual Basic project"),
    ("*.sln", ".NET solution"),
    ("global.json", ".NET SDK selection"),
    ("package.swift", "Swift package"),
    ("pubspec.yaml", "Dart/Flutter package"),
    ("composer.json", "PHP Composer project"),
    ("gemfile", "Ruby Bundler project"),
    ("*.gemspec", "Ruby gem"),
    ("mix.exs", "Elixir Mix project"),
    ("rebar.config", "Erlang Rebar project"),
    ("stack.yaml", "Haskell Stack project"),
    ("cabal.project", "Haskell Cabal project"),
    ("dune-project", "OCaml Dune project"),
    ("project.toml", "Julia project"),
    ("manifest.toml", "Julia manifest"),
    ("description", "R package"),
    ("cmakelists.txt", "CMake project"),
    ("meson.build", "Meson project"),
    ("build.zig", "Zig build"),
    ("makefile", "Make project"),
    ("justfile", "Just task file"),
    ("flake.nix", "Nix flake"),
    ("terraform.lock.hcl", "Terraform lockfile"),
    ("foundry.toml", "Foundry Solidity project"),
    ("hardhat.config.*", "Hardhat Solidity project"),
    ("anchor.toml", "Anchor/Solana project"),
)

SHEBANG_LANGUAGES = {
    "python": "Python",
    "node": "JavaScript",
    "deno": "TypeScript/JavaScript",
    "bun": "TypeScript/JavaScript",
    "ruby": "Ruby",
    "perl": "Perl",
    "php": "PHP",
    "bash": "Shell",
    "sh": "Shell",
    "zsh": "Shell",
    "pwsh": "PowerShell",
    "powershell": "PowerShell",
}


def manifest_kind(name: str) -> str | None:
    lowered = name.lower()
    for pattern, kind in MANIFEST_PATTERNS:
        if fnmatch.fnmatch(lowered, pattern):
            return kind
    return None


def shebang_language(path: Path) -> str | None:
    try:
        with path.open("rb") as handle:
            first = handle.readline(256).decode("utf-8", errors="ignore").lower()
    except (OSError, PermissionError):
        return None
    if not first.startswith("#!"):
        return None
    for token, language in SHEBANG_LANGUAGES.items():
        if token in first:
            return language
    return None


def language_for(path: Path) -> str | None:
    lowered = path.name.lower()
    if lowered in BASENAME_LANGUAGES:
        return BASENAME_LANGUAGES[lowered]
    if lowered.endswith(".d.ts"):
        return "TypeScript declarations"
    suffix = path.suffix.lower()
    if suffix in EXTENSIONS:
        return EXTENSIONS[suffix]
    if not suffix:
        return shebang_language(path)
    return None


def iter_files(root: Path, max_files: int) -> tuple[Iterable[Path], dict[str, bool | int]]:
    state: dict[str, bool | int] = {"visited": 0, "truncated": False}

    def generate() -> Iterable[Path]:
        if root.is_file():
            state["visited"] = 1
            yield root
            return
        for current, dirs, files in os.walk(root, topdown=True, followlinks=False):
            dirs[:] = sorted(d for d in dirs if d.lower() not in IGNORE_DIRS)
            for name in sorted(files):
                if int(state["visited"]) >= max_files:
                    state["truncated"] = True
                    return
                state["visited"] = int(state["visited"]) + 1
                yield Path(current) / name

    return generate(), state


def detect(root: Path, max_files: int) -> dict[str, object]:
    counts: Counter[str] = Counter()
    manifests: list[dict[str, str]] = []
    ci_files: list[str] = []
    files, state = iter_files(root, max_files)

    for path in files:
        language = language_for(path)
        if language:
            counts[language] += 1

        kind = manifest_kind(path.name)
        relative = path.relative_to(root).as_posix() if root.is_dir() else path.name
        if kind:
            manifests.append({"path": relative, "kind": kind})

        lower_relative = relative.lower()
        if (
            lower_relative.startswith(".github/workflows/")
            or lower_relative in {
                ".gitlab-ci.yml",
                "azure-pipelines.yml",
                "bitbucket-pipelines.yml",
                "circle.yml",
                ".circleci/config.yml",
            }
        ):
            ci_files.append(relative)

    recognized = sum(counts.values())
    languages = [
        {
            "name": name,
            "files": count,
            "percent_of_recognized": round((count / recognized) * 100, 2)
            if recognized
            else 0.0,
        }
        for name, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    ]

    return {
        "root": str(root),
        "scanned_files": int(state["visited"]),
        "truncated": bool(state["truncated"]),
        "recognized_source_files": recognized,
        "languages": languages,
        "manifests": sorted(manifests, key=lambda item: (item["path"], item["kind"])),
        "ci_files": sorted(set(ci_files)),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Detect repository languages and build manifests."
    )
    parser.add_argument("root", nargs="?", default=".", help="File or directory to scan")
    parser.add_argument(
        "--max-files",
        type=int,
        default=200_000,
        help="Stop after this many files (default: 200000)",
    )
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.max_files < 1:
        print("--max-files must be positive", file=sys.stderr)
        return 2
    root = Path(args.root).expanduser().resolve()
    if not root.exists():
        print(f"Path does not exist: {root}", file=sys.stderr)
        return 2
    result = detect(root, args.max_files)
    print(json.dumps(result, indent=2 if args.pretty else None, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

