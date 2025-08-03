import json
import shutil
import importlib
import inspect
import pkgutil
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, Callable, List, Any

from esp32_manager.core.config_manager import ProjectConfig, logger
from esp32_manager.utils.exceptions import ProjectValidationError
from esp32_manager.plugins.base_plugin import BasePlugin


class ProjectManager:
    """Core project management functionality."""
    def __init__(self, workspace_dir: Path):
        self.workspace_dir = Path(workspace_dir or Path.cwd())
        self.config_file = self.workspace_dir / "projects.json"
        self.projects: Dict[str, ProjectConfig] = {}
        self.current_project: Optional[str] = None
        self._observers: List[Callable[[str, ProjectConfig], None]] = []

        self.plugins: Dict[str, BasePlugin] = {}

        self.load_projects()
        self.load_plugins()

    def add_observer(self, callback: Callable[[str, ProjectConfig], None]):
        """Add observer for project changes."""
        self._observers.append(callback)

    def _notify_observers(self, event: str, project: ProjectConfig):
        """Notify observers of project changes."""
        for callback in self._observers:
            try:
                callback(event, project)
            except Exception as e:
                logger.warning(f"Observer callback failed: {e}")

    def load_projects(self) -> bool:
        """Load project configuration from file."""
        if not self.config_file.exists():
            return False

        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

                # Load projects
                for name, config_data in data.get('projects', {}).items():
                    self.projects[name] = ProjectConfig.from_dict(config_data)

                # Load current project
                self.current_project = data.get('current_project')

            logger.info(f"Loaded {len(self.projects)} projects")
            return True
        except Exception as e:
            logger.error(f"Failed to load projects: {e}")
            return False

    def load_plugins(self) -> None:
        """Discover and load available plugins.

        Plugins are discovered by scanning the :mod:`esp32_manager.plugins`
        package for subclasses of :class:`BasePlugin`. Each plugin is
        instantiated with this project manager instance and its
        :meth:`load` hook is invoked.
        """
        try:
            import esp32_manager.plugins as plugins_pkg
        except Exception as exc: # pragma: no cover - very unlikely
            logger.error(f"Unable to import plugins package: {exc}")
            return
        for _, module_name, _ in pkgutil.iter_modules(plugins_pkg.__path__):
            if module_name.startswith('_') or module_name == 'base_plugin':
                continue
            try:
                module = importlib.import_module(f'esp32_manager.plugins.{module_name}')
            except Exception as exc:
                logger.error(f"Failed to import plugin '{module_name}': {exc}")
                continue

            for obj in module.__dict__.values():
                if inspect.isclass(obj) and issubclass(obj, BasePlugin) and obj is not BasePlugin:
                    try:
                        plugin = obj(self)
                        plugin.load()
                    except Exception as exc:
                        logger.error(f"Failed to initialize plugin '{obj.__name__}': {exc}")
                        continue
                    self.plugins[plugin.name] = plugin

    def get_plugin(self, name: str) -> Optional[BasePlugin]:
        """Return the loaded plugin with *name* if available."""
        return self.plugins.get(name)

    def run_plugin(self, name: str, command: str, **kwargs: Any ) -> Any:
        """Execute *command* using the plugin *name*.

         The plugin's :meth:`BasePlugin.execute` method is called with the
         provided command and keyword arguments. Raise :class:`ValueError`
        if the plugin is not loaded."""
        plugin = self.get_plugin(name)
        if not plugin:
            raise ValueError(f"Plugin '{name}' not found")
        return plugin.execute(command, **kwargs)

    def save_projects(self) -> bool:
        """Save project configuration to file."""
        try:
            data = {
                'projects': {
                    name: config.to_dict()
                    for name, config in self.projects.items()
                },
                'current_project': self.current_project,
                'last_updated': datetime.now().isoformat(),
                'version': "2.0"
            }

            if self.config_file.exists():
                backup_file = self.config_file.with_suffix('.json.bak')
                shutil.copy2(self.config_file, backup_file)

            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)

            logger.info("Projects saved successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to save projects: {e}")
            return False

    def validate_project_name(self, name: str) -> bool:
        """Validate project name."""
        if not name or not name.strip():
            raise ProjectValidationError("Project name cannot be empty")

        if name in self.projects:
            raise ProjectValidationError(f"Project '{name}' already exists")

        if any(char in name for char in r'<>:"/\|?*'):
            raise ProjectValidationError("Project name contains invalid characters")

        return True

    def create_project(self,
                       name: str,
                       description: str = "",
                       template: str = "basic",
                       author: str = "",
                       tags: List[str] = None) -> ProjectConfig:
        """Create a new ESP32 project."""
        self.validate_project_name(name)

        project_path = self.workspace_dir / name

        # Create project config
        config = ProjectConfig(
            name=name,
            path=project_path,
            description=description,
            template=template,
            author=author,
            tags=tags or []
        )

        # Create project structure
        self._create_project_structure(project_path, template, config)

        # Add to projects
        self.projects[name] = config

        # Set as current if it's the first project
        if len(self.projects) == 1:
            self.current_project = name

        # Save and notify
        self.save_projects()
        self._notify_observers('project_created', config)

        logger.info(f"Created project '{name}' at {project_path}")
        return config

    @staticmethod
    def _create_project_structure(project_path: Path, template: str, config: ProjectConfig):
        """Create the physical project structure."""
        # Create directories
        directories = ['src', 'tests', 'docs', 'assets', 'lib']
        for dir_name in directories:
            (project_path / dir_name).mkdir(parents=True, exist_ok=True)

        # Create files from template
        from ..templates import get_template_files
        template_files = get_template_files(template, config)

        for file_path, content in template_files.items():
            full_path = project_path / file_path
            full_path.parent.mkdir(parents=True, exist_ok=True)

            with open(full_path, 'w', encoding='utf-8') as f:
                f.write(content)

        # Create project-specific config
        project_config_file = project_path / 'project.json'
        with open(project_config_file, 'w', encoding='utf-8') as f:
            json.dump(config.to_dict(), f, indent=2)

    def get_project(self, name: str) -> Optional[ProjectConfig]:
        """Get project by name."""
        return self.projects.get(name)

    def get_current_project(self) -> Optional[ProjectConfig]:
        """Get current active project."""
        if self.current_project:
            return self.projects.get(self.current_project)
        return None

    def set_current_project(self, name: str) -> bool:
        """Set the current active project."""
        if name not in self.projects:
            raise ValueError(f"Project '{name}' not found")

        old_current = self.current_project
        self.current_project = name

        if self.save_projects():
            logger.info(f"Set current project to '{name}'")
            if old_current != name:
                self._notify_observers('current_project_changed', self.projects[name])
            return True
        return False

    def update_project(self, name: str, **kwargs) -> bool:
        """Update project configuration."""
        if name not in self.projects:
            raise ValueError(f"Project '{name}' not found")

        config = self.projects[name]

        # Update fields
        for key, value in kwargs.items():
            if hasattr(config, key):
                setattr(config, key, value)


        config.update_modified()

        if self.save_projects():
            self._notify_observers('project_updated', config)
            return True
        return False

    def delete_project(self, name: str, remove_files: bool = False) -> bool:
        """Delete a project."""
        if name not in self.projects:
            raise ValueError(f"Project '{name}' not found")

        config = self.projects[name]

        # Remove files if requested
        if remove_files and config.path.exists():
            try:
                shutil.rmtree(config.path)
                logger.info(f"Removed project files {config.path}")
            except Exception as e:
                logger.error(f"Failed to remove project files: {e}")
                return False

        # Remove from projects
        del self.projects[name]

        # Update current project if needed
        if self.current_project == name:
            self.current_project = next(iter(self.projects), None)

        if self.save_projects():
            self._notify_observers('project_deleted', config)
            return True
        return False

    def list_projects(self, tag_filter: Optional[str] = None) -> List[ProjectConfig]:
        """List all projects, optionally filtered by tag."""
        projects = list(self.projects.values())

        if tag_filter:
            projects = [p for p in projects if tag_filter in p.tags]

        # Sort by last modified
        projects.sort(key=lambda p: p.last_modified or p.created_at, reverse=True)
        return projects

    def get_project_stats(self, name: str) -> Dict[str, Any]:
        """Get project statistics."""
        if name not in self.projects:
            raise ValueError(f"Project '{name}' not found")

        config = self.projects[name]
        base_path = config.path
        src_path = base_path / 'src'
        tests_path = base_path / 'tests'
        docs_path = base_path / 'docs'

        stats: Dict[str, Any] = {
            'name': name,
            'files': 0,
            'lines_of_code': 0,
            'size_bytes': 0,
            'python_files': 0,
            'test_files': 0,
            'last_modified': config.last_modified,
            'created_at': config.created_at,
            'has_tests': tests_path.exists(),
            'has_docs': docs_path.exists()
        }

        if src_path.is_dir():
            for file_path in src_path.rglob('*'):
                if not file_path.is_file():
                    continue

                stats['files'] += 1
                try:
                    stats['size_bytes'] += file_path.stat().st_size
                except OSError as e:
                    logger.warning("Could not stat %s: %s", file_path, e)
                    continue

                if file_path.suffix == '.py':
                    stats['python_files'] += 1
                    try:
                        # read in one go is often faster than readlines()
                        content = file_path.read_text(encoding='utf-8')
                        stats['lines_of_code'] += content.count("\n") + 1
                    except (UnicodeDecodeError, OSError) as e:
                        logger.warning("Could not read %s: %s", file_path, e)

        # Count test_*.py in tests/
        if tests_path.exists():
            stats['test_files'] = sum(1 for _ in tests_path.glob("test_*.py"))

        return stats

    def search_projects(self, query: str) -> List[ProjectConfig]:
        """Search projects by name, description, or tags."""
        query = query.lower()
        results = []

        for config in self.projects.values():
            if (query in config.name.lower() or
                    query in config.description.lower() or
                    any(query in tag.lower() for tag in config.tags)):
                results.append(config)

        return results

    def export_project(self, name: str, export_path: Path) -> bool:
        """Export project as archive."""
        if name not in self.projects:
            raise ValueError(f"Project '{name}' not found")

        config = self.projects[name]

        try:
            shutil.make_archive(
                str(export_path.with_suffix('')),
                'zip',
                config.path
            )
            logger.info(f"Exported project '{name}' to {export_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to export project: {e}")
            return False

    def import_project(self, archive_path: Path, name: Optional[str] = None) -> Optional[ProjectConfig]:
        """Import project from archive."""
        archive_path = Path(archive_path)

        if not archive_path.exists():
            logger.error(f"Archive not found: {archive_path}")
            return None

        if archive_path.suffix.lower() != '.zip':
            logger.error("Only .zip archives are supported for import")
            return

        try:
            # Extract to temporary directory first
            from tempfile import TemporaryDirectory

            with TemporaryDirectory(dir=self.workspace_dir) as tmp_dir:
                shutil.unpack_archive(str(archive_path), tmp_dir, 'zip')

                tmp_path = Path(tmp_dir)

                # Handle archives that contain a single root directory
                entries = list(tmp_path.iterdir())
                if len(entries) == 1 and entries[0].is_dir():
                    project_root = entries[0]
                else:
                    project_root = tmp_path

                project_json = project_root / 'project.json'

                if project_json.exists():
                    with open(project_json, 'r', encoding='utf-8') as f:
                        data = json.load(f)

                    proj_name = name or data.get('name') or archive_path.stem
                    self.validate_project_name(proj_name)

                    # Ensure path and name match the final location
                    data['name'] = proj_name
                    data['path'] = str(self.workspace_dir / proj_name)
                    config = ProjectConfig.from_dict(data)
                else:
                    proj_name = name or archive_path.stem
                    self.validate_project_name(proj_name)
                    config = ProjectConfig(name=proj_name, path=self.workspace_dir / proj_name)

                final_path = self.workspace_dir / proj_name
                if final_path.exists():
                    raise ProjectValidationError(f"Destination path {final_path} already exists")

                shutil.move(str(project_root), str(final_path))

                # Write project.json if it didn't exist
                if not (final_path / 'project.json').exists():
                    with open(final_path / 'project.json', 'w', encoding='utf-8') as f:
                        json.dump(config.to_dict(), f, indent=2)
        except Exception as e:
            logger.error(f"Failed to import project: {e}")
            return None

        # Register project
        self.projects[proj_name] = config

        # Set as current if no project is currently selected
        if not self.current_project:
            self.current_project = proj_name

        if self.save_projects():
            self._notify_observers('project_imported', config)
            logger.info(f"Imported project '{proj_name}' from {archive_path}")
            return config

        return None

    def get_workspace_stats(self) -> Dict[str, Any]:
        """Get overall workspace statistics."""
        total_files = 0
        total_size = 0
        total_loc = 0

        for config in self.projects.values():
            stats = self.get_project_stats(config.name)
            total_files += stats['files']
            total_size += stats['size_bytes']
            total_loc += stats['lines_of_code']

        return {
            'total_projects': len(self.projects),
            'total_files': total_files,
            'total_size_bytes': total_size,
            'total_lines_of_code': total_loc,
            'current_project': self.current_project,
            'workspace_path': str(self.workspace_dir)
        }