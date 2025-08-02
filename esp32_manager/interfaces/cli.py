import os
import sys
import shutil
import subprocess
from pathlib import Path
from functools import wraps
from typing import List, Optional, Callable

from esp32_manager.core.project_manager import ProjectManager, ProjectConfig

# Optional Rich imports for enhanced CLI output
try:
    from rich.console import Console as RichConsole
    from rich.table import Table as RichTable
    from rich.prompt import Confirm as RichConfirm
    from rich import box
    RICH_AVAILABLE = True
except ImportError:
    RichConsole = None
    RichTable = None
    RichConfirm = None
    box = None
    RICH_AVAILABLE = False


def handle_errors(func: Callable[..., bool]) -> Callable[..., bool]:
    """
    Decorator to wrap CLI operations with consistent error handling.
    """
    @wraps(func)
    def wrapper(self, *args, **kwargs) -> bool:
        try:
            return func(self, *args, **kwargs)
        except ValueError as e:
            self._print(f"❌ {e}", "red")
        except subprocess.CalledProcessError as e:
            self._print(f"❌ Command failed: {e}", "red")
        except Exception as e:
            self._print(f"❌ Unexpected error: {e}", "red")
        return False
    return wrapper


class ESP32CLI:
    def __init__(self, project_manager: ProjectManager):
        self.pm = project_manager
        self.console = RichConsole() if RICH_AVAILABLE and RichConsole else None

    def _print(self, message: str, style: str = ""):
        if self.console:
            self.console.print(message, style=style)
        else:
            print(message)

    def _print_table(self, rows: List[List[str]], headers: List[str], title: str = ""):
        if self.console and RichTable:
            table = RichTable(title=title, box=box.ROUNDED)
            for header in headers:
                table.add_column(header)
            for row in rows:
                table.add_row(*row)
            self.console.print(table)
        else:
            if title:
                print(f"\n{title}")
                print("=" * len(title))
            # Header row
            print(" | ".join(headers))
            print("-" * (sum(len(h) for h in headers) + 3 * (len(headers) - 1)))
            # Data rows
            for row in rows:
                print(" | ".join(row))
            print()

    def _get_project(self, name: Optional[str]) -> ProjectConfig:
        project_name = name or self.pm.current_project
        if not project_name:
            raise ValueError("No project specified.")
        project = self.pm.get_project(project_name)
        if not project:
            raise ValueError(f"Project '{project_name}' not found.")
        return project

    @handle_errors
    def init_workspace(self) -> bool:
        base = self.pm.workspace_dir
        self._print(f"🚀 Initializing ESP32 workspace in: {base}", "bold blue")
        for dirname in ("utils", "templates", "build", "shared"):
            (base / dirname).mkdir(exist_ok=True)
            self._print(f"  ✅ Created: {dirname}", "green")
        if not self.pm.config_file.exists():
            self.pm.save_projects()
            self._print("  ✅ Configuration file created.", "green")
        self._print("✅ Workspace initialized!", "bold green")
        return True

    @handle_errors
    def create_project(self, name: str, description: str = "", template: str = "basic", author: str = "") -> bool:
        if self.console:
            with self.console.status(f"Creating project '{name}'..."):
                cfg = self.pm.create_project(name, description, template, author)
        else:
            print(f"Creating project '{name}'...")
            cfg = self.pm.create_project(name, description, template, author)
        self._print(f"✅ Project '{name}' created at {cfg.path}", "bold green")
        return True

    @handle_errors
    def list_projects(self, tag_filter: Optional[str] = None) -> bool:
        projects = self.pm.list_projects(tag_filter)
        if not projects:
            self._print("📂 No projects found.", "yellow")
            return True
        rows: List[List[str]] = []
        current = self.pm.current_project
        for proj in projects:
            status = "🔥 Current" if proj.name == current else ""
            modified = proj.last_modified or proj.created_at
            rows.append([proj.name, proj.template, modified, status])
        title = f"ESP32 Projects{' (filtered)' if tag_filter else ''}"
        self._print_table(rows, ["Name", "Template", "Modified", "Status"], title)
        return True

    @handle_errors
    def show_project_info(self, name: Optional[str] = None) -> bool:
        proj = self._get_project(name)
        stats = self.pm.get_project_stats(proj.name)
        info = [["Name", proj.name], ["Template", proj.template], ["Path", str(proj.path)]]
        self._print_table(info, ["Property", "Value"], f"Info: {proj.name}")
        metrics = [[k.replace('_', ' ').title(), str(v)] for k, v in stats.items() if isinstance(v, (int, str))]
        self._print_table(metrics, ["Metric", "Value"], "Statistics")
        return True

    @handle_errors
    def build_project(self, name: Optional[str] = None) -> bool:
        proj = self._get_project(name)
        build_dir = self.pm.workspace_dir / "build" / proj.name
        shutil.rmtree(build_dir, ignore_errors=True)
        shutil.copytree(proj.path / "src", build_dir, dirs_exist_ok=True)
        self._print(f"✅ Built {proj.name} -> {build_dir}", "green")
        return True

    @handle_errors
    def deploy_project(self, name: Optional[str] = None, device: str = ":") -> bool:
        proj = self._get_project(name)
        script = self.pm.workspace_dir / "deploy.py"
        if not script.exists():
            raise ValueError("Deploy script not found.")
        env = {**os.environ, 'PROJECT_NAME': proj.name, 'DEVICE': device}
        subprocess.run([sys.executable, str(script)], env=env, check=True)
        proj.mark_deployed()
        self.pm.save_projects()
        self._print("✅ Deployment completed!", "green")
        return True

    @handle_errors
    def run_tests(self, name: Optional[str] = None) -> bool:
        proj = self._get_project(name)
        tests_dir = proj.path / "tests"
        if not tests_dir.exists():
            raise ValueError("No tests directory found.")
        test_files = list(tests_dir.glob("test_*.py"))
        if not test_files:
            raise ValueError("No test files found (prefix 'test_').")
        subprocess.run([sys.executable, "-m", "pytest", str(tests_dir)], check=True)
        self._print("✅ All tests passed!", "green")
        return True

    @handle_errors
    def delete_project(self, name: str, remove_files: bool = False) -> bool:
        proj = self._get_project(name)
        if self.console and RichConfirm and not RichConfirm.ask(f"Delete project '{proj.name}'?", console=self.console):
            self._print("Deletion cancelled.", "yellow")
            return True
        if self.pm.delete_project(proj.name, remove_files):
            self._print(f"✅ Project '{proj.name}' deleted.", "green")
            return True
        raise ValueError("Failed to delete project.")

    @handle_errors
    def export_project(self, name: str, output: Optional[Path] = None) -> bool:
        proj = self._get_project(name)
        output_path = output or Path(f"{proj.name}.zip")
        if not self.pm.export_project(proj.name, output_path):
            raise ValueError("Export failed.")
        self._print(f"✅ Project exported to: {output_path}", "green")
        return True

    @handle_errors
    def search_projects(self, query: str) -> bool:
        results = self.pm.search_projects(query)
        if not results:
            self._print(f"🔍 No projects match '{query}'", "yellow")
            return True
        rows = [[p.name, p.template] for p in results]
        self._print_table(rows, ["Name", "Template"], f"Search Results: '{query}'")
        return True

## =========
    def set_current_project(self, name: str) -> bool:
        """Set current project."""
        try:
            self.pm.set_current_project(name)
            self._print(f"✅ Set current project to '{name}'", "green")
            return True
        except Exception as e:
            self._print(f"❌ Failed to set current project: {e}", "red")
            return False

    def simulate_project(self, name: Optional[str] = None) -> bool:
        """Simulate a project locally."""
        try:
            project_name = name or self.pm.current_project
            if not project_name:
                self._print("❌ No project specified", "red")
                return False

            project = self.pm.get_project(project_name)
            if not project:
                self._print(f"❌ Project '{project_name}' not found", "red")
                return False

            self._print(f"🔄 Starting simulation of '{project_name}'...", "blue")
            self._print("💡 Press Ctrl+C to stop simulation", "dim")

            # Add project src to Python path
            src_path = project.path / "src"
            if str(src_path) not in sys.path:
                sys.path.insert(0, str(src_path))

            # Add utils to path for hardware stubs
            utils_path = self.pm.workspace_dir / "utils"
            if str(utils_path) not in sys.path:
                sys.path.insert(0, str(utils_path))

            # Import and run the main module
            main_file = src_path / project.main_file
            if not main_file.exists():
                self._print(f"❌ Main file not found: {main_file}", "red")
                return False

            # Execute the project
            import importlib.util
            spec = importlib.util.spec_from_file_location("project_main", main_file)
            module = importlib.util.module_from_spec(spec)

            try:
                spec.loader.exec_module(module)
                self._print("✅ Simulation completed", "green")
                return True
            except KeyboardInterrupt:
                self._print("\n⏹️ Simulation stopped by user", "yellow")
                return True

        except Exception as e:
            self._print(f"❌ Simulation failed: {e}", "red")
            return False


    def show_workspace_stats(self) -> bool:
        """Show workspace statistics."""
        try:
            stats = self.pm.get_workspace_stats()

            stats_data = [
                ["Total Projects", str(stats['total_projects'])],
                ["Total Files", str(stats['total_files'])],
                ["Total Size", f"{stats['total_size_bytes'] / 1024:.1f} KB"],
                ["Total Lines of Code", str(stats['total_lines_of_code'])],
                ["Current Project", stats['current_project'] or "None"],
                ["Workspace Path", stats['workspace_path']]
            ]

            self._print_table(stats_data, ["Metric", "Value"], "Workspace Statistics")
            return True

        except Exception as e:
            self._print(f"❌ Failed to get workspace stats: {e}", "red")
            return False
