import argparse
import logging
from pathlib import Path
from typing import Optional

from esp32_manager.core.project_manager import ProjectManager


class ESP32ManagerApp:
    """Main application controller."""

    def __init__(self, workspace_dir: Optional[Path] = None):
        self.workspace_dir = workspace_dir or Path.cwd()
        self.project_manager = ProjectManager(self.workspace_dir)
        self.logger = logging.getLogger(__name__)

    def run_cli(self, args: argparse.Namespace) -> bool:
        pass

    def run_interactive(self, interface: str = " cli") -> bool:
        """Run interactive interface."""
        try:
            if interface == "cli":
                return launch_cli(self.project_manager)
            else:
                print(f"Unknown interface: {interface}")
                return False
        except Exception as e:
            self.logger.error(f"Interactive mode failed: {e}")
            return False


def launch_cli(project_manager) -> bool:
    """Launch interactive CLI."""
    from esp32_manager.interfaces.cli import ESP32CLI

    cli = ESP32CLI(project_manager)
    print("\\n=== ESP32 Project Manager - Interactive Mode ===")
    print("Available commands: init, create, list, current, info, build, deploy, quit")

    while True:
        try:
            command = input("\\esp32> ").strip().split()
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
                print("Commands: init, create <name>, list, current <name>, info [name], build [name], deploy [name], quit")
            else:
                print(f"Unknown command: {cmd}. Type 'help' for available commands.")

        except KeyboardInterrupt:
            print("\\nGoodbye!")
            break
        except Exception as e:
            print(f"Error: {e}")

    return True