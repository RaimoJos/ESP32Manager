"""
ESP32 Build System
==================

Handles building, optimizing, and preparing ESP32 projects for deployment.
Supports code optimization, dependency management, and cross-compilation.
"""

import os
import ast
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Set, Any, Tuple
from dataclasses import dataclass
import logging
import json
import hashlib

from esp32_manager.core.config_manager import ProjectConfig
from esp32_manager.utils.exceptions import ProjectValidationError

logger = logging.getLogger(__name__)

@dataclass
class BuildResult:
    """Result of a build operation."""
    success: bool
    build_path: Path
    files_processed: int
    total_size: int
    warnings: List[str]
    errors: List[str]
    build_time: float
    optimization_savings: int = 0

@dataclass
class BuildConfig:
    """Build configuration options."""
    strip_comments: bool = True
    strip_docstrings: bool = True
    strip_type_hints: bool = True
    optimize_imports: bool = True
    minify_code: bool = False
    include_tests: bool = False
    cross_compile: bool = True
    target_platform: str = "esp32"
    python_version: str = "3.4"  # MicroPython compatibility
    output_format: str = "directory"  # directory, zip, tar

class DependencyResolver:
    """Resolves and manages project dependencies."""

    def __init__(self):
        self.micropython_stdlib = {
            'gc', 'sys', 'os', 'time', 'json', 'math', 'random',
            'struct', 'binascii', 'hashlib', 'io', 're', 'collections',
            'machine', 'network', 'socket', 'ssl', 'ubinascii',
            'ucollections', 'uerrno', 'uhashlib', 'uheapq', 'uio',
            'ujson', 'uos', 'ure', 'uselect', 'usocket', 'ussl',
            'ustruct', 'utime', 'uzlib'
        }

        self.esp32_modules = {
            'machine', 'network', 'esp', 'esp32', 'bluetooth',
            'wifi', 'webrepl', 'webrepl_setup'
        }

    def analyze_dependencies(self, source_files: List[Path]) -> Dict[str, Set[str]]:
        """Analyze dependencies in source files."""
        dependencies = {}

        for file_path in source_files:
            if file_path.suffix != '.py':
                continue

            deps = self._extract_imports(file_path)
            dependencies[str(file_path)] = deps

        return dependencies

    def _extract_imports(self, file_path: Path) -> Set[str]:
        """Extract import statements from a Python file."""
        imports = set()

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            tree = ast.parse(content)

            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        imports.add(alias.name.split('.')[0])
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        imports.add(node.module.split('.')[0])

        except Exception as e:
            logger.warning(f"Failed to parse {file_path}: {e}")

        return imports

    def validate_dependencies(self, dependencies: Set[str]) -> Tuple[Set[str], Set[str]]:
        """Validate dependencies against available modules."""
        available = self.micropython_stdlib | self.esp32_modules
        valid_deps = dependencies & available
        invalid_deps = dependencies - available

        return valid_deps, invalid_deps

class CodeOptimizer:
    """Optimizes Python code for MicroPython/ESP32 deployment."""

    def __init__(self, config: BuildConfig):
        self.config = config

    def optimize_file(self, source_path: Path, target_path: Path) -> int:
        """Optimize a single Python file."""
        try:
            with open(source_path, 'r', encoding='utf-8') as f:
                original_content = f.read()

            original_size = len(original_content)

            # Parse AST
            tree = ast.parse(original_content)

            # Apply optimizations
            if self.config.strip_type_hints:
                tree = self._strip_type_hints(tree)

            if self.config.strip_docstrings:
                tree = self._strip_docstrings(tree)

            if self.config.optimize_imports:
                tree = self._optimize_imports(tree)

            # Convert back to code
            import astor
            optimized_content = astor.to_source(tree)

            if self.config.strip_comments:
                optimized_content = self._strip_comments(optimized_content)

            if self.config.minify_code:
                optimized_content = self._minify_code(optimized_content)

            # Write optimized file
            target_path.parent.mkdir(parents=True, exist_ok=True)
            with open(target_path, 'w', encoding='utf-8') as f:
                f.write(optimized_content)

            optimized_size = len(optimized_content)
            savings = original_size - optimized_size

            logger.debug(f"Optimized {source_path.name}: {original_size} -> {optimized_size} bytes ({savings} saved)")
            return savings

        except ImportError:
            # Fallback without AST manipulation if astor not available
            logger.warning("astor not available, using basic optimization")
            return self._basic_optimize(source_path, target_path)
        except Exception as e:
            logger.error(f"Failed to optimize {source_path}: {e}")
            # Copy file as-is
            shutil.copy2(source_path, target_path)
            return 0

    def _basic_optimize(self, source_path: Path, target_path: Path) -> int:
        """Basic optimization without AST manipulation."""
        try:
            with open(source_path, 'r', encoding='utf-8') as f:
                content = f.read()

            original_size = len(content)

            if self.config.strip_comments:
                content = self._strip_comments(content)

            target_path.parent.mkdir(parents=True, exist_ok=True)
            with open(target_path, 'w', encoding='utf-8') as f:
                f.write(content)

            optimized_size = len(content)
            return original_size - optimized_size

        except Exception as e:
            logger.error(f"Failed to optimize {source_path}: {e}")
            shutil.copy2(source_path, target_path)
            return 0

    def _strip_type_hints(self, tree: ast.AST) -> ast.AST:
        """Remove type hints from AST."""
        class TypeHintRemover(ast.NodeTransformer):
            def visit_FunctionDef(self, node):
                # Remove return annotation
                node.returns = None
                # Remove argument annotations
                for arg in node.args.args:
                    arg.annotation = None
                return self.generic_visit(node)

            def visit_AnnAssign(self, node):
                # Convert annotated assignment to regular assignment
                if node.value:
                    return ast.Assign(targets=[node.target], value=node.value)
                return None

        return TypeHintRemover().visit(tree)

    def _strip_docstrings(self, tree: ast.AST) -> ast.AST:
        """Remove docstrings from AST."""
        class DocstringRemover(ast.NodeTransformer):
            def visit_FunctionDef(self, node):
                if (node.body and isinstance(node.body[0], ast.Expr) and
                    isinstance(node.body[0].value, ast.Str)):
                    node.body = node.body[1:]
                return self.generic_visit(node)

            def visit_ClassDef(self, node):
                if (node.body and isinstance(node.body[0], ast.Expr) and
                    isinstance(node.body[0].value, ast.Str)):
                    node.body = node.body[1:]
                return self.generic_visit(node)

            def visit_Module(self, node):
                if (node.body and isinstance(node.body[0], ast.Expr) and
                    isinstance(node.body[0].value, ast.Str)):
                    node.body = node.body[1:]
                return self.generic_visit(node)

        return DocstringRemover().visit(tree)

    def _optimize_imports(self, tree: ast.AST) -> ast.AST:
        """Optimize import statements."""
        # This is a placeholder for import optimization
        # Could include: removing unused imports, combining imports, etc.
        return tree

    def _strip_comments(self, content: str) -> str:
        """Remove comments from code."""
        lines = content.split('\n')
        stripped_lines = []

        for line in lines:
            # Find comment start (but not in strings)
            in_string = False
            quote_char = None
            i = 0

            while i < len(line):
                char = line[i]

                if not in_string and char == '#':
                    # Found comment, truncate line
                    line = line[:i].rstrip()
                    break
                elif char in ('"', "'") and (i == 0 or line[i-1] != '\\'):
                    if not in_string:
                        in_string = True
                        quote_char = char
                    elif char == quote_char:
                        in_string = False
                        quote_char = None

                i += 1

            if line.strip():  # Keep non-empty lines
                stripped_lines.append(line)

        return '\n'.join(stripped_lines)

    def _minify_code(self, content: str) -> str:
        """Basic code minification."""
        lines = content.split('\n')
        minified_lines = []

        for line in lines:
            stripped = line.strip()
            if stripped and not stripped.startswith('#'):
                minified_lines.append(stripped)

        return '\n'.join(minified_lines)

class BuildSystem:
    """Main build system coordinator."""

    def __init__(self, workspace_dir: Path):
        self.workspace_dir = workspace_dir
        self.build_dir = workspace_dir / "build"
        self.cache_dir = workspace_dir / ".build_cache"

        # Create directories
        self.build_dir.mkdir(exist_ok=True)
        self.cache_dir.mkdir(exist_ok=True)

        self.dependency_resolver = DependencyResolver()

    def build_project(self, project_config: ProjectConfig,
                     build_config: Optional[BuildConfig] = None) -> BuildResult:
        """Build a project."""
        if build_config is None:
            build_config = BuildConfig()

        start_time = time.time()

        logger.info(f"Building project: {project_config.name}")

        # Validate project
        self._validate_project(project_config)

        # Setup build environment
        project_build_dir = self.build_dir / project_config.name
        if project_build_dir.exists():
            shutil.rmtree(project_build_dir)
        project_build_dir.mkdir(parents=True)

        warnings = []
        errors = []
        files_processed = 0
        total_size = 0
        optimization_savings = 0

        try:
            # Copy and process source files
            src_dir = project_config.path / "src"
            target_src_dir = project_build_dir / "src"

            if src_dir.exists():
                savings = self._process_source_directory(
                    src_dir, target_src_dir, build_config
                )
                optimization_savings += savings
                files_processed += len(list(src_dir.rglob("*.py")))

            # Copy lib directory if exists
            lib_dir = project_config.path / "lib"
            if lib_dir.exists():
                shutil.copytree(lib_dir, project_build_dir / "lib")
                files_processed += len(list(lib_dir.rglob("*")))

            # Copy assets if exists
            assets_dir = project_config.path / "assets"
            if assets_dir.exists():
                shutil.copytree(assets_dir, project_build_dir / "assets")
                files_processed += len(list(assets_dir.rglob("*")))

            # Include tests if requested
            if build_config.include_tests:
                tests_dir = project_config.path / "tests"
                if tests_dir.exists():
                    shutil.copytree(tests_dir, project_build_dir / "tests")
                    files_processed += len(list(tests_dir.rglob("*.py")))

            # Analyze dependencies
            source_files = list((project_build_dir / "src").rglob("*.py"))
            dependencies = self.dependency_resolver.analyze_dependencies(source_files)
            all_deps = set()
            for deps in dependencies.values():
                all_deps.update(deps)

            valid_deps, invalid_deps = self.dependency_resolver.validate_dependencies(all_deps)

            if invalid_deps:
                warnings.append(f"Unknown dependencies: {', '.join(invalid_deps)}")

            # Generate build metadata
            self._generate_build_metadata(project_build_dir, project_config,
                                        build_config, valid_deps, invalid_deps)

            # Calculate total size
            total_size = self._calculate_directory_size(project_build_dir)

            # Cross-compile if requested
            if build_config.cross_compile:
                self._cross_compile_project(project_build_dir, build_config)

            # Package output if requested
            if build_config.output_format != "directory":
                self._package_build(project_build_dir, build_config)

            build_time = time.time() - start_time

            logger.info(f"Build completed in {build_time:.2f}s")
            logger.info(f"Files processed: {files_processed}")
            logger.info(f"Total size: {total_size / 1024:.1f} KB")
            if optimization_savings > 0:
                logger.info(f"Space saved: {optimization_savings / 1024:.1f} KB")

            return BuildResult(
                success=True,
                build_path=project_build_dir,
                files_processed=files_processed,
                total_size=total_size,
                warnings=warnings,
                errors=errors,
                build_time=build_time,
                optimization_savings=optimization_savings
            )

        except Exception as e:
            logger.error(f"Build failed: {e}")
            errors.append(str(e))

            return BuildResult(
                success=False,
                build_path=project_build_dir,
                files_processed=files_processed,
                total_size=total_size,
                warnings=warnings,
                errors=errors,
                build_time=time.time() - start_time
            )

    def _validate_project(self, project_config: ProjectConfig):
        """Validate project before building."""
        if not project_config.path.exists():
            raise ProjectValidationError(f"Project path does not exist: {project_config.path}")

        src_dir = project_config.path / "src"
        if not src_dir.exists():
            raise ProjectValidationError("Project must have a 'src' directory")

        main_file = src_dir / project_config.main_file
        if not main_file.exists():
            raise ProjectValidationError(f"Main file not found: {main_file}")

    def _process_source_directory(self, src_dir: Path, target_dir: Path,
                                 build_config: BuildConfig) -> int:
        """Process source directory with optimizations."""
        optimizer = CodeOptimizer(build_config)
        total_savings = 0

        for source_file in src_dir.rglob("*"):
            if source_file.is_file():
                relative_path = source_file.relative_to(src_dir)
                target_file = target_dir / relative_path

                if source_file.suffix == ".py":
                    # Optimize Python files
                    savings = optimizer.optimize_file(source_file, target_file)
                    total_savings += savings
                else:
                    # Copy other files as-is
                    target_file.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(source_file, target_file)

        return total_savings

    def _generate_build_metadata(self, build_dir: Path, project_config: ProjectConfig,
                                build_config: BuildConfig, valid_deps: Set[str],
                                invalid_deps: Set[str]):
        """Generate build metadata file."""
        import time

        metadata = {
            "project": {
                "name": project_config.name,
                "version": project_config.version,
                "template": project_config.template,
                "author": project_config.author
            },
            "build": {
                "timestamp": time.time(),
                "config": {
                    "strip_comments": build_config.strip_comments,
                    "strip_docstrings": build_config.strip_docstrings,
                    "strip_type_hints": build_config.strip_type_hints,
                    "optimize_imports": build_config.optimize_imports,
                    "minify_code": build_config.minify_code,
                    "target_platform": build_config.target_platform,
                    "python_version": build_config.python_version
                }
            },
            "dependencies": {
                "valid": list(valid_deps),
                "invalid": list(invalid_deps),
                "total": len(valid_deps) + len(invalid_deps)
            },
            "files": self._get_file_list(build_dir)
        }

        metadata_file = build_dir / "build_metadata.json"
        with open(metadata_file, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2)

    def _get_file_list(self, directory: Path) -> List[Dict[str, Any]]:
        """Get list of files with metadata."""
        files = []

        for file_path in directory.rglob("*"):
            if file_path.is_file() and file_path.name != "build_metadata.json":
                stat = file_path.stat()
                relative_path = file_path.relative_to(directory)

                files.append({
                    "path": str(relative_path),
                    "size": stat.st_size,
                    "modified": stat.st_mtime,
                    "type": file_path.suffix[1:] if file_path.suffix else "unknown"
                })

        return files

    def _calculate_directory_size(self, directory: Path) -> int:
        """Calculate total size of directory."""
        total_size = 0

        for file_path in directory.rglob("*"):
            if file_path.is_file():
                total_size += file_path.stat().st_size

        return total_size

    def _cross_compile_project(self, build_dir: Path, build_config: BuildConfig):
        """Cross-compile Python files to bytecode."""
        logger.info("Cross-compiling to bytecode...")

        # Find Python files
        python_files = list(build_dir.rglob("*.py"))

        for py_file in python_files:
            try:
                # Compile to bytecode
                import py_compile
                pyc_file = py_file.with_suffix('.pyc')
                py_compile.compile(py_file, pyc_file, doraise=True)

                # Optionally remove source file
                if build_config.minify_code:
                    py_file.unlink()

                logger.debug(f"Compiled {py_file.name} to bytecode")

            except Exception as e:
                logger.warning(f"Failed to compile {py_file}: {e}")

    def _package_build(self, build_dir: Path, build_config: BuildConfig):
        """Package build output."""
        if build_config.output_format == "zip":
            archive_path = build_dir.with_suffix('.zip')
            shutil.make_archive(str(build_dir), 'zip', build_dir)
            logger.info(f"Created ZIP archive: {archive_path}")

        elif build_config.output_format == "tar":
            archive_path = build_dir.with_suffix('.tar.gz')
            shutil.make_archive(str(build_dir), 'gztar', build_dir)
            logger.info(f"Created TAR archive: {archive_path}")

    def clean_build(self, project_name: Optional[str] = None):
        """Clean build artifacts."""
        if project_name:
            project_build_dir = self.build_dir / project_name
            if project_build_dir.exists():
                shutil.rmtree(project_build_dir)
                logger.info(f"Cleaned build for project: {project_name}")
        else:
            if self.build_dir.exists():
                shutil.rmtree(self.build_dir)
                self.build_dir.mkdir()
                logger.info("Cleaned all build artifacts")

    def get_build_cache_info(self) -> Dict[str, Any]:
        """Get build cache information."""
        if not self.cache_dir.exists():
            return {"cache_size": 0, "cached_builds": 0}

        cache_files = list(self.cache_dir.rglob("*"))
        cache_size = sum(f.stat().st_size for f in cache_files if f.is_file())

        return {
            "cache_size": cache_size,
            "cached_builds": len([f for f in cache_files if f.is_dir()]),
            "cache_dir": str(self.cache_dir)
        }

    def clean_cache(self):
        """Clean build cache."""
        if self.cache_dir.exists():
            shutil.rmtree(self.cache_dir)
            self.cache_dir.mkdir()
            logger.info("Build cache cleaned")

class BuildManager:
    """High-level build management interface."""

    def __init__(self, workspace_dir: Path):
        self.build_system = BuildSystem(workspace_dir)
        self.build_configs = {}

    def create_build_config(self, name: str, **kwargs) -> BuildConfig:
        """Create a named build configuration."""
        config = BuildConfig(**kwargs)
        self.build_configs[name] = config
        return config

    def get_build_config(self, name: str) -> Optional[BuildConfig]:
        """Get a build configuration by name."""
        return self.build_configs.get(name)

    def build_project(self, project_config: ProjectConfig,
                     config_name: str = "default") -> BuildResult:
        """Build project with named configuration."""
        build_config = self.build_configs.get(config_name)
        if build_config is None:
            build_config = BuildConfig()  # Use default

        return self.build_system.build_project(project_config, build_config)

    def get_build_status(self, project_name: str) -> Dict[str, Any]:
        """Get build status for a project."""
        build_dir = self.build_system.build_dir / project_name

        if not build_dir.exists():
            return {"built": False, "build_time": None}

        metadata_file = build_dir / "build_metadata.json"
        if metadata_file.exists():
            try:
                with open(metadata_file, 'r', encoding='utf-8') as f:
                    metadata = json.load(f)
                return {
                    "built": True,
                    "build_time": metadata["build"]["timestamp"],
                    "config": metadata["build"]["config"],
                    "file_count": len(metadata["files"]),
                    "dependencies": metadata["dependencies"]
                }
            except Exception as e:
                logger.warning(f"Failed to read build metadata: {e}")

        return {"built": True, "build_time": None}

# Utility functions
def create_default_build_configs() -> Dict[str, BuildConfig]:
    """Create default build configurations."""
    return {
        "development": BuildConfig(
            strip_comments=False,
            strip_docstrings=False,
            strip_type_hints=False,
            optimize_imports=False,
            minify_code=False,
            include_tests=True,
            cross_compile=False
        ),
        "production": BuildConfig(
            strip_comments=True,
            strip_docstrings=True,
            strip_type_hints=True,
            optimize_imports=True,
            minify_code=True,
            include_tests=False,
            cross_compile=True
        ),
        "debug": BuildConfig(
            strip_comments=False,
            strip_docstrings=False,
            strip_type_hints=False,
            optimize_imports=False,
            minify_code=False,
            include_tests=True,
            cross_compile=False,
            output_format="directory"
        )
    }

# Import time module for build system
import time

if __name__ == "__main__":
    # Example usage
    workspace = Path(".")
    build_system = BuildSystem(workspace)

    # Create example project config
    from esp32_manager.core.config_manager import ProjectConfig

    config = ProjectConfig(
        name="example_project",
        path=Path("example_project"),
        description="Example project for testing"
    )

    # Build project
    result = build_system.build_project(config)
    print(f"Build successful: {result.success}")
    print(f"Files processed: {result.files_processed}")
    print(f"Build time: {result.build_time:.2f}s")