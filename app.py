import argparse
import logging
from pathlib import Path
from typing import Optional

from esp32_manager.core.project_manager import ProjectManager
from esp32_manager.core.build_system import BuildManager, create_default_build_configs
from esp32_manager.core.device_manager import ESP32DeviceManager


class ESP32ManagerApp:
    """Main application controller with full integration."""

    def __init__(self, workspace_dir: Optional[Path] = None):
        self.workspace_dir = workspace_dir or Path.cwd()
        self.project_manager = ProjectManager(self.workspace_dir)
        self.build_manager = BuildManager(self.workspace_dir)
        self.device_manager = ESP32DeviceManager(self.workspace_dir)
        self.logger = logging.getLogger(__name__)

        # Setup default build configurations
        self._setup_build_configs()

        # Setup device scanning
        self.device_manager.start_scanning()

        self.logger.info(f"ESP32Manager initialized in workspace: {self.workspace_dir}")

    def _setup_build_configs(self):
        """Setup default build configurations."""
        default_configs = create_default_build_configs()
        for name, config in default_configs.items():
            self.build_manager.build_configs[name] = config

        self.logger.debug(f"Loaded {len(default_configs)} build configurations")

    def run_cli(self, args: argparse.Namespace) -> bool:
        """Handle CLI commands."""
        try:
            if args.command == 'init':
                return self._init_workspace()

            elif args.command == 'create':
                return self._create_project(args)

            elif args.command == 'list':
                return self._list_projects(args)

            elif args.command == 'current':
                return self._set_current_project(args)

            elif args.command == 'info':
                return self._show_project_info(args)

            elif args.command == 'simulate':
                return self._simulate_project(args)

            elif args.command == 'build':
                return self._build_project(args)

            elif args.command == 'deploy':
                return self._deploy_project(args)

            elif args.command == 'test':
                return self._test_project(args)

            elif args.command == 'delete':
                return self._delete_project(args)

            elif args.command == 'export':
                return self._export_project(args)

            elif args.command == 'stats':
                return self._show_stats(args)

            elif args.command == 'search':
                return self._search_projects(args)

            elif args.command == 'devices':
                return self._manage_devices(args)

            else:
                self.logger.error(f"Unknown command: {args.command}")
                return False

        except Exception as e:
            self.logger.error(f"Command failed: {e}")
            return False

    def _init_workspace(self) -> bool:
        """Initialize workspace."""
        try:
            # Create directories
            directories = ['build', 'templates', 'shared', 'backups']
            for dirname in directories:
                (self.workspace_dir / dirname).mkdir(exist_ok=True)
                print(f"✅ Created directory: {dirname}")

            # Initialize project manager
            if not self.project_manager.config_file.exists():
                self.project_manager.save_projects()
                print("✅ Created project configuration")

            # Save device configuration
            device_config_file = self.workspace_dir / 'devices.json'
            self.device_manager.save_device_config(device_config_file)

            print("🚀 Workspace initialized successfully!")
            return True

        except Exception as e:
            print(f"❌ Failed to initialize workspace: {e}")
            return False

    def _create_project(self, args: argparse.Namespace) -> bool:
        """Create a new project."""
        try:
            project = self.project_manager.create_project(
                name=args.name,
                description=getattr(args, 'description', ''),
                template=getattr(args, 'template', 'basic'),
                author=getattr(args, 'author', '')
            )

            print(f"✅ Created project '{project.name}' at {project.path}")
            return True

        except Exception as e:
            print(f"❌ Failed to create project: {e}")
            return False

    def _list_projects(self, args: argparse.Namespace) -> bool:
        """List projects."""
        try:
            projects = self.project_manager.list_projects(
                tag_filter=getattr(args, 'filter', None)
            )

            if not projects:
                print("📂 No projects found")
                return True

            current = self.project_manager.current_project

            print(f"\n📁 Projects ({len(projects)} found):")
            print("-" * 80)

            for project in projects:
                status = "🔥 CURRENT" if project.name == current else ""
                template = f"[{project.template}]"

                print(f"{project.name:20} {template:12} {project.description[:40]:40} {status}")

            print("-" * 80)
            return True

        except Exception as e:
            print(f"❌ Failed to list projects: {e}")
            return False

    def _set_current_project(self, args: argparse.Namespace) -> bool:
        """Set current project."""
        try:
            self.project_manager.set_current_project(args.name)
            print(f"✅ Set current project to '{args.name}'")
            return True

        except Exception as e:
            print(f"❌ Failed to set current project: {e}")
            return False

    def _show_project_info(self, args: argparse.Namespace) -> bool:
        """Show project information."""
        try:
            project_name = getattr(args, 'name', None) or self.project_manager.current_project
            if not project_name:
                print("❌ No project specified")
                return False

            project = self.project_manager.get_project(project_name)
            if not project:
                print(f"❌ Project '{project_name}' not found")
                return False

            stats = self.project_manager.get_project_stats(project_name)
            build_status = self.build_manager.get_build_status(project_name)

            print(f"\n📊 Project Information: {project.name}")
            print("=" * 60)
            print(f"Description:     {project.description or 'No description'}")
            print(f"Template:        {project.template}")
            print(f"Version:         {project.version}")
            print(f"Author:          {project.author or 'Unknown'}")
            print(f"Path:            {project.path}")
            print(f"Created:         {project.created_at}")

            if project.last_modified:
                print(f"Modified:        {project.last_modified}")

            if project.tags:
                print(f"Tags:            {', '.join(project.tags)}")

            print("\n📈 Statistics:")
            print(f"Files:           {stats['files']}")
            print(f"Python files:    {stats['python_files']}")
            print(f"Lines of code:   {stats['lines_of_code']}")
            print(f"Size:            {stats['size_bytes'] / 1024:.1f} KB")
            print(f"Test files:      {stats['test_files']}")

            print(f"\n🔧 Build Status:")
            if build_status['built']:
                print("Built:           ✅ Yes")
                if build_status['build_time']:
                    import datetime
                    build_time = datetime.datetime.fromtimestamp(build_status['build_time'])
                    print(f"Build time:      {build_time}")
                print(f"File count:      {build_status.get('file_count', 'Unknown')}")
            else:
                print("Built:           ❌ No")

            return True

        except Exception as e:
            print(f"❌ Failed to show project info: {e}")
            return False

    def _simulate_project(self, args: argparse.Namespace) -> bool:
        """Simulate project locally."""
        try:
            project_name = getattr(args, 'name', None) or self.project_manager.current_project
            if not project_name:
                print("❌ No project specified")
                return False

            project = self.project_manager.get_project(project_name)
            if not project:
                print(f"❌ Project '{project_name}' not found")
                return False

            print(f"🔄 Starting simulation of '{project_name}'...")
            print("💡 Press Ctrl+C to stop simulation")

            # Add hardware stubs to path
            import sys
            utils_path = self.workspace_dir / "esp32_manager" / "utils"
            if str(utils_path) not in sys.path:
                sys.path.insert(0, str(utils_path))

            # Add project src to Python path
            src_path = project.path / "src"
            if str(src_path) not in sys.path:
                sys.path.insert(0, str(src_path))

            # Import hardware stubs
            try:
                import hardware_stubs
                print("🔧 Hardware simulation stubs loaded")

                # Show simulation controls
                hardware_stubs.SimulationControls.help()

            except ImportError:
                print("⚠️  Hardware stubs not found, running without simulation")

            # Import and run the main module
            main_file = src_path / project.main_file
            if not main_file.exists():
                print(f"❌ Main file not found: {main_file}")
                return False

            # Execute the project
            print(f"▶️  Running {main_file}")
            import importlib.util
            spec = importlib.util.spec_from_file_location("project_main", main_file)
            module = importlib.util.module_from_spec(spec)

            try:
                spec.loader.exec_module(module)
                print("✅ Simulation completed")
                return True
            except KeyboardInterrupt:
                print("\n⏹️ Simulation stopped by user")
                return True

        except Exception as e:
            print(f"❌ Simulation failed: {e}")
            return False

    def _build_project(self, args: argparse.Namespace) -> bool:
        """Build project."""
        try:
            project_name = getattr(args, 'name', None) or self.project_manager.current_project
            if not project_name:
                print("❌ No project specified")
                return False

            project = self.project_manager.get_project(project_name)
            if not project:
                print(f"❌ Project '{project_name}' not found")
                return False

            # Determine build config
            config_name = getattr(args, 'config', 'production')

            print(f"🔨 Building project '{project_name}' with '{config_name}' configuration...")

            result = self.build_manager.build_project(project, config_name)

            if result.success:
                print(f"✅ Build completed successfully!")
                print(f"   Files processed: {result.files_processed}")
                print(f"   Build time: {result.build_time:.2f}s")
                print(f"   Output size: {result.total_size / 1024:.1f} KB")

                if result.optimization_savings > 0:
                    print(f"   Space saved: {result.optimization_savings / 1024:.1f} KB")

                if result.warnings:
                    print(f"⚠️  Warnings: {len(result.warnings)}")
                    for warning in result.warnings:
                        print(f"   - {warning}")

                return True
            else:
                print(f"❌ Build failed!")
                for error in result.errors:
                    print(f"   - {error}")
                return False

        except Exception as e:
            print(f"❌ Build failed: {e}")
            return False

    def _deploy_project(self, args: argparse.Namespace) -> bool:
        """Deploy project to ESP32."""
        try:
            project_name = getattr(args, 'name', None) or self.project_manager.current_project
            if not project_name:
                print("❌ No project specified")
                return False

            project = self.project_manager.get_project(project_name)
            if not project:
                print(f"❌ Project '{project_name}' not found")
                return False

            # Check if project is built
            build_dir = self.build_manager.build_system.build_dir / project_name
            if not build_dir.exists():
                print("⚠️  Project not built. Building now...")
                build_result = self.build_manager.build_project(project, 'production')
                if not build_result.success:
                    print("❌ Failed to build project")
                    return False

            # Get target device
            device_port = getattr(args, 'device', None)

            if not device_port:
                # Auto-detect devices
                devices = self.device_manager.get_devices()
                connected_devices = [d for d in devices if d.state.value == 'connected']

                if not connected_devices:
                    print("❌ No ESP32 devices found. Connect a device and try again.")
                    return False
                elif len(connected_devices) == 1:
                    device_port = connected_devices[0].port
                    print(f"📱 Auto-selected device: {device_port}")
                else:
                    print("🔍 Multiple devices found:")
                    for i, device in enumerate(connected_devices):
                        print(f"   {i + 1}. {device.port} - {device.description}")

                    try:
                        choice = int(input("Select device (number): ")) - 1
                        device_port = connected_devices[choice].port
                    except (ValueError, IndexError):
                        print("❌ Invalid selection")
                        return False

            print(f"🚀 Deploying '{project_name}' to {device_port}...")

            # Progress callback
            def progress_callback(message, progress):
                bar_length = 30
                filled_length = int(bar_length * progress)
                bar = '█' * filled_length + '-' * (bar_length - filled_length)
                print(f"\r[{bar}] {progress * 100:.1f}% - {message}", end='', flush=True)

            result = self.device_manager.deploy_project(
                build_dir, device_port, progress_callback
            )

            print()  # New line after progress bar

            if result.success:
                print(f"✅ Deployment completed successfully!")
                print(f"   Files transferred: {result.files_transferred}")
                print(f"   Data transferred: {result.bytes_transferred / 1024:.1f} KB")
                print(f"   Transfer time: {result.transfer_time:.2f}s")

                # Mark project as deployed
                project.mark_deployed()
                self.project_manager.save_projects()

                return True
            else:
                print(f"❌ Deployment failed!")
                for error in result.errors:
                    print(f"   - {error}")
                return False

        except Exception as e:
            print(f"❌ Deployment failed: {e}")
            return False

    def _test_project(self, args: argparse.Namespace) -> bool:
        """Run project tests."""
        try:
            project_name = getattr(args, 'name', None) or self.project_manager.current_project
            if not project_name:
                print("❌ No project specified")
                return False

            project = self.project_manager.get_project(project_name)
            if not project:
                print(f"❌ Project '{project_name}' not found")
                return False

            tests_dir = project.path / "tests"
            if not tests_dir.exists():
                print("❌ No tests directory found")
                return False

            test_files = list(tests_dir.glob("test_*.py"))
            if not test_files:
                print("❌ No test files found (must start with 'test_')")
                return False

            print(f"🧪 Running tests for '{project_name}'...")

            # Add project to Python path
            import sys
            project_src = project.path / "src"
            if str(project_src) not in sys.path:
                sys.path.insert(0, str(project_src))

            # Run tests
            import subprocess
            result = subprocess.run([
                sys.executable, "-m", "pytest", str(tests_dir), "-v"
            ], capture_output=True, text=True)

            print(result.stdout)
            if result.stderr:
                print("Errors:", result.stderr)

            if result.returncode == 0:
                print("✅ All tests passed!")
                return True
            else:
                print("❌ Some tests failed")
                return False

        except Exception as e:
            print(f"❌ Test execution failed: {e}")
            return False

    def _delete_project(self, args: argparse.Namespace) -> bool:
        """Delete project."""
        try:
            remove_files = getattr(args, 'remove_files', False)

            # Confirmation
            response = input(f"Are you sure you want to delete '{args.name}'? (y/N): ")
            if response.lower() != 'y':
                print("❌ Deletion cancelled")
                return False

            if remove_files:
                response = input("This will also remove all project files. Continue? (y/N): ")
                if response.lower() != 'y':
                    print("❌ Deletion cancelled")
                    return False

            success = self.project_manager.delete_project(args.name, remove_files)

            if success:
                print(f"✅ Project '{args.name}' deleted")
                return True
            else:
                print(f"❌ Failed to delete project '{args.name}'")
                return False

        except Exception as e:
            print(f"❌ Delete failed: {e}")
            return False

    def _export_project(self, args: argparse.Namespace) -> bool:
        """Export project as archive."""
        try:
            output_path = Path(getattr(args, 'output', f"{args.name}.zip"))

            success = self.project_manager.export_project(args.name, output_path)

            if success:
                print(f"✅ Project exported to: {output_path}")
                return True
            else:
                print(f"❌ Failed to export project")
                return False

        except Exception as e:
            print(f"❌ Export failed: {e}")
            return False

    def _show_stats(self, args: argparse.Namespace) -> bool:
        """Show workspace statistics."""
        try:
            workspace_stats = self.project_manager.get_workspace_stats()
            device_stats = self.device_manager.get_device_status()
            build_cache_info = self.build_manager.build_system.get_build_cache_info()

            print("\n📊 ESP32Manager Workspace Statistics")
            print("=" * 60)

            print("\n📁 Projects:")
            print(f"   Total projects:    {workspace_stats['total_projects']}")
            print(f"   Total files:       {workspace_stats['total_files']}")
            print(f"   Total size:        {workspace_stats['total_size_bytes'] / 1024:.1f} KB")
            print(f"   Lines of code:     {workspace_stats['total_lines_of_code']}")
            print(f"   Current project:   {workspace_stats['current_project'] or 'None'}")

            print("\n📱 Devices:")
            print(f"   Total devices:     {device_stats['total_devices']}")
            print(f"   Connected:         {device_stats['connected_devices']}")
            print(f"   Scanning:          {'✅ Yes' if device_stats['scanning'] else '❌ No'}")

            print("\n🔧 Build System:")
            print(f"   Cache size:        {build_cache_info['cache_size'] / 1024:.1f} KB")
            print(f"   Cached builds:     {build_cache_info['cached_builds']}")

            print(f"\n🏠 Workspace:        {workspace_stats['workspace_path']}")

            return True

        except Exception as e:
            print(f"❌ Failed to show stats: {e}")
            return False

    def _search_projects(self, args: argparse.Namespace) -> bool:
        """Search projects."""
        try:
            results = self.project_manager.search_projects(args.query)

            if not results:
                print(f"🔍 No projects found matching '{args.query}'")
                return True

            print(f"\n🔍 Search Results for '{args.query}' ({len(results)} found):")
            print("-" * 60)

            current = self.project_manager.current_project

            for project in results:
                status = "🔥 CURRENT" if project.name == current else ""
                template = f"[{project.template}]"

                print(f"{project.name:20} {template:12} {project.description[:30]:30} {status}")

            print("-" * 60)
            return True

        except Exception as e:
            print(f"❌ Search failed: {e}")
            return False

    def _manage_devices(self, args: argparse.Namespace) -> bool:
        """Manage ESP32 devices."""
        try:
            action = getattr(args, 'action', 'list')

            if action == 'list':
                devices = self.device_manager.get_devices()

                if not devices:
                    print("📱 No ESP32 devices found")
                    print("💡 Make sure your device is connected and drivers are installed")
                    return True

                print(f"\n📱 ESP32 Devices ({len(devices)} found):")
                print("-" * 80)

                for device in devices:
                    state_icon = {
                        'connected': '🟢',
                        'disconnected': '🔴',
                        'busy': '🟡',
                        'error': '❌'
                    }.get(device.state.value, '⚫')

                    print(f"{state_icon} {device.port:15} {device.name:10} {device.description[:40]:40}")

                print("-" * 80)

            elif action == 'info':
                port = getattr(args, 'port', None)
                if not port:
                    print("❌ Device port required for info command")
                    return False

                info = self.device_manager.get_device_info(port)
                if info:
                    print(f"\n📱 Device Information: {port}")
                    print("=" * 40)
                    for key, value in info.items():
                        print(f"{key:15}: {value}")
                else:
                    print(f"❌ Failed to get device info for {port}")

            elif action == 'monitor':
                port = getattr(args, 'port', None)
                if not port:
                    print("❌ Device port required for monitor command")
                    return False

                print(f"📟 Monitoring {port} (Ctrl+C to stop)")

                def output_callback(text):
                    print(text, end='')

                try:
                    self.device_manager.start_monitor(port, callback=output_callback)

                    while True:
                        import time
                        time.sleep(0.1)

                except KeyboardInterrupt:
                    self.device_manager.stop_monitor(port)
                    print("\n📟 Monitoring stopped")

            elif action == 'reset':
                port = getattr(args, 'port', None)
                if not port:
                    print("❌ Device port required for reset command")
                    return False

                if self.device_manager.reset_device(port):
                    print(f"✅ Device {port} reset successfully")
                else:
                    print(f"❌ Failed to reset device {port}")

            else:
                print(f"❌ Unknown device action: {action}")
                return False

            return True

        except Exception as e:
            print(f"❌ Device management failed: {e}")
            return False

    def run_interactive(self, interface: str = "cli") -> bool:
        """Run interactive interface."""
        try:
            if interface == "cli":
                return self._launch_cli()
            elif interface == "tui":
                return self._launch_tui()
            else:
                print(f"❌ Unknown interface: {interface}")
                return False
        except Exception as e:
            self.logger.error(f"Interactive mode failed: {e}")
            return False

    def _launch_cli(self) -> bool:
        """Launch interactive CLI."""
        from esp32_manager.interfaces.cli import ESP32CLI

        cli = ESP32CLI(self.project_manager)
        print("\n=== ESP32 Project Manager - Interactive Mode ===")
        print("Available commands: init, create, list, current, info, build, deploy, devices, quit")
        print("Type 'help' for detailed command information")

        while True:
            try:
                current = self.project_manager.current_project or "none"
                devices = len([d for d in self.device_manager.get_devices()
                               if d.state.value == 'connected'])

                prompt = f"\n[{current}|{devices} devices] esp32> "
                command = input(prompt).strip().split()
                if not command:
                    continue

                cmd = command[0].lower()

                if cmd in ['quit', 'exit', 'q']:
                    print("👋 Goodbye!")
                    break

                elif cmd == 'init':
                    cli.init_workspace()

                elif cmd == 'create' and len(command) > 1:
                    cli.create_project(command[1])

                elif cmd == 'list':
                    cli.list_projects()

                elif cmd == 'current' and len(command) > 1:
                    cli.set_current_project(command[1])

                elif cmd == 'info':
                    name = command[1] if len(command) > 1 else None
                    cli.show_project_info(name)

                elif cmd == 'build':
                    name = command[1] if len(command) > 1 else None
                    cli.build_project(name)

                elif cmd == 'deploy':
                    name = command[1] if len(command) > 1 else None
                    cli.deploy_project(name)

                elif cmd == 'simulate':
                    name = command[1] if len(command) > 1 else None
                    cli.simulate_project(name)

                elif cmd == 'test':
                    name = command[1] if len(command) > 1 else None
                    cli.run_tests(name)

                elif cmd == 'devices':
                    action = command[1] if len(command) > 1 else 'list'
                    if action == 'list':
                        devices = self.device_manager.get_devices()
                        if devices:
                            print("\n📱 Connected Devices:")
                            for device in devices:
                                state = device.state.value
                                print(f"  {device.port} - {device.description} [{state}]")
                        else:
                            print("📱 No devices found")

                elif cmd == 'stats':
                    cli.show_workspace_stats()

                elif cmd == 'help':
                    self._show_cli_help()

                else:
                    print(f"❌ Unknown command: {cmd}. Type 'help' for available commands.")

            except KeyboardInterrupt:
                print("\n👋 Goodbye!")
                break
            except Exception as e:
                print(f"❌ Error: {e}")

        return True

    def _launch_tui(self) -> bool:
        """Launch Terminal UI with safety checks."""
        try:
            import importlib
            tui_mod = importlib.import_module('esp_manager.interfaces.tui')

            launch = getattr(tui_mod, 'launch_tui', None)
            if not callable(launch):
                self.logger.error(
                    "TUI interface module does not expose a callable 'launch_tui'."
                )
                return False

            # Call and ensure a boolean return
            result = launch(self.project_manager)
            return bool(result)

        except ImportError:
            print("❌ TUI not available. Install with: pip install textual rich")
            return False

    def _show_cli_help(self):
        """Show CLI help."""
        help_text = """
📖 ESP32 Project Manager - Command Help

Project Management:
  init                    - Initialize workspace
  create <name>          - Create new project
  list                   - List all projects
  current <name>         - Set current project
  info [name]           - Show project information
  delete <name>         - Delete project

Development:
  simulate [name]       - Simulate project locally
  build [name]          - Build project
  deploy [name]         - Deploy to ESP32
  test [name]           - Run project tests

Device Management:
  devices               - List connected devices
  devices info <port>   - Get device information
  devices monitor <port> - Monitor device output
  devices reset <port>  - Reset device

Utilities:
  stats                 - Show workspace statistics
  search <query>        - Search projects
  export <name>         - Export project
  help                  - Show this help
  quit, exit, q         - Exit application

💡 Commands in brackets [] are optional
💡 Use Tab completion where available
        """
        print(help_text)

    def run_web(self, host: str = "127.0.0.1", port: int = 8000) -> bool:
        """Run web interface."""
        try:
            from esp32_manager.interfaces.web_app import create_app
            import uvicorn

            fastapi_app = create_app(
                self.project_manager,  self.build_manager, self.device_manager
            )
            uvicorn.run(fastapi_app, host=host, port=port)
            return True
        except Exception as e:
            self.logger.error(f"Web interface failed: {e}")
            return False

    def cleanup(self):
        """Clean up resources."""
        try:
            self.device_manager.cleanup()
            self.logger.info("Application cleanup completed")
        except Exception as e:
            self.logger.error(f"Cleanup failed: {e}")

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.cleanup()


def launch_cli(project_manager) -> bool:
    """Legacy function for compatibility."""
    from esp32_manager.interfaces.cli import ESP32CLI

    cli = ESP32CLI(project_manager)
    print("\n=== ESP32 Project Manager - Interactive Mode ===")
    print("Available commands: init, create, list, current, info, build, deploy, quit")

    while True:
        try:
            command = input("\nesp32> ").strip().split()
            if not command:
                continue

            cmd = command[0].lower()

            if cmd in ['quit', 'exit', 'q']:
                print("Goodbye!")
                break
            elif cmd == 'init':
                cli.init_workspace()
            elif cmd == 'create' and len(command) > 1:
                cli.create_project(command[1])
            elif cmd == 'list':
                cli.list_projects()
            elif cmd == 'current' and len(command) > 1:
                cli.set_current_project(command[1])
            elif cmd == 'info':
                name = command[1] if len(command) > 1 else None
                cli.show_project_info(name)
            elif cmd == 'build':
                name = command[1] if len(command) > 1 else None
                cli.build_project(name)
            elif cmd == 'deploy':
                name = command[1] if len(command) > 1 else None
                cli.deploy_project(name)
            elif cmd == 'help':
                print(
                    "Commands: init, create <name>, list, current <name>, info [name], build [name], deploy [name], quit")
            else:
                print(f"Unknown command: {cmd}. Type 'help' for available commands.")

        except KeyboardInterrupt:
            print("\nGoodbye!")
            break
        except Exception as e:
            print(f"Error: {e}")

    return True