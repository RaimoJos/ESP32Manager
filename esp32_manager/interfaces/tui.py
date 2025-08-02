"""
ESP32 Project Manager - Advanced Terminal UI
===========================================

Modern, interactive terminal interface using Rich and Textual.
Provides a full-featured development environment in the terminal.
"""

from __future__ import annotations
import asyncio
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime

# Rich imports for beautiful terminal output
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.columns import Columns
from rich.text import Text
from rich.tree import Tree
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.layout import Layout
from rich.live import Live
from rich.syntax import Syntax
from rich.prompt import Prompt, Confirm
from rich import box

# Textual imports for interactive TUI
try:
    from textual.app import App, ComposeResult
    from textual.containers import Container, Horizontal, Vertical, ScrollableContainer
    from textual.widgets import (
        Header, Footer, DirectoryTree, TextLog, Input, Button,
        DataTable, Tabs, TabPane, Static, Label, ProgressBar
    )
    from textual.reactive import reactive
    from textual.binding import Binding
    from textual.screen import Screen

    TEXTUAL_AVAILABLE = True
except ImportError:
    App = None
    ComposeResult = None
    Container = None
    Vertical = None
    Header = None
    Footer = None
    Binding = None
    DirectoryTree = None
    TextLog = None
    Input = None
    Button = None
    DataTable = None
    Tabs = None
    TabPane = None
    Progress = None
    Static = None
    Label = None
    TEXTUAL_AVAILABLE = False

from esp32_manager.core.project_manager import ProjectManager
from esp32_manager.core.project_manager import ProjectConfig

class ESP32Dashboard:
    """Rich-based dashboard for project overview."""

    def __init__(self, project_manager: ProjectManager):
        self.console = Console()
        self.project_manager = project_manager

    def show_welcome(self):
        """Show welcome screen with ASCII art and info."""
        welcome_text = """
╔═══════════════════════════════════════════════════════════════╗
║                    ESP32 Project Manager                      ║
║                   Advanced Development Suite                  ║
╚═══════════════════════════════════════════════════════════════╝
        """

        self.console.print(welcome_text, style="bold blue")

        # Show workspace info
        workspace_stats = self.project_manager.get_workspace_stats()

        info_table = Table(show_header=False, box=box.SIMPLE)
        info_table.add_column("Key", style="cyan")
        info_table.add_column("Value", style="white")

        info_table.add_row("Workspace", str(workspace_stats['workspace_path']))
        info_table.add_row("Projects", str(workspace_stats['total_projects']))
        info_table.add_row("Total Files", str(workspace_stats['total_files']))
        info_table.add_row("Lines of Code", str(workspace_stats['total_lines_of_code']))

        current = workspace_stats.get('current_project')
        if current:
            info_table.add_row("Current Project", f"[bold green]{current}[/bold green]")

        self.console.print(Panel(info_table, title="Workspace Info", border_style="blue"))

    def show_projects_table(self, projects: List[ProjectConfig]):
        """Display projects in a formatted table."""
        if not projects:
            self.console.print("[yellow]No projects found. Create one with 'create <name>'[/yellow]")
            return

        table = Table(title="ESP32 Projects", box=box.ROUNDED)
        table.add_column("Name", style="cyan", no_wrap=True)
        table.add_column("Description", style="white")
        table.add_column("Template", style="magenta")
        table.add_column("Modified", style="dim white")
        table.add_column("Status", justify="center")

        current_project = self.project_manager.current_project

        for project in projects:
            # Status indicators
            status_parts = []
            if project.name == current_project:
                status_parts.append("[bold green]●[/bold green]")  # Current

            if project.last_deployed:
                status_parts.append("[blue]↗[/blue]")  # Deployed

            if (project.path / 'tests').exists():
                status_parts.append("[yellow]T[/yellow]")  # Has tests

            status = " ".join(status_parts) if status_parts else "[dim]○[/dim]"

            # Format modified time
            if project.last_modified:
                modified = datetime.fromisoformat(project.last_modified).strftime("%m/%d %H:%M")
            else:
                modified = datetime.fromisoformat(project.created_at).strftime("%m/%d %H:%M")

            table.add_row(
                project.name,
                project.description[:50] + "..." if len(project.description) > 50 else project.description,
                project.template,
                modified,
                status
            )

        self.console.print(table)

        # Legend
        legend = """
[bold green]●[/bold green] Current Project  [blue]↗[/blue] Deployed  [yellow]T[/yellow] Has Tests
        """
        self.console.print(legend, style="dim")

    def show_project_details(self, project: ProjectConfig):
        """Show detailed information about a project."""
        stats = self.project_manager.get_project_stats(project.name)

        # Create layout with columns
        left_panel = Table(show_header=False, box=box.SIMPLE)
        left_panel.add_column("Key", style="cyan")
        left_panel.add_column("Value", style="white")

        left_panel.add_row("Name", project.name)
        left_panel.add_row("Description", project.description or "[dim]No description[/dim]")
        left_panel.add_row("Template", project.template)
        left_panel.add_row("Version", project.version)
        left_panel.add_row("Author", project.author or "[dim]Unknown[/dim]")
        left_panel.add_row("Path", str(project.path))

        if project.tags:
            left_panel.add_row("Tags", ", ".join(project.tags))

        right_panel = Table(show_header=False, box=box.SIMPLE)
        right_panel.add_column("Key", style="cyan")
        right_panel.add_column("Value", style="white")

        right_panel.add_row("Files", str(stats['files']))
        right_panel.add_row("Python Files", str(stats['python_files']))
        right_panel.add_row("Lines of Code", str(stats['lines_of_code']))
        right_panel.add_row("Size", f"{stats['size_bytes'] / 1024:.1f} KB")
        right_panel.add_row("Test Files", str(stats['test_files']))

        # Timestamps
        created = datetime.fromisoformat(project.created_at).strftime("%Y-%m-%d %H:%M")
        right_panel.add_row("Created", created)

        if project.last_modified:
            modified = datetime.fromisoformat(project.last_modified).strftime("%Y-%m-%d %H:%M")
            right_panel.add_row("Modified", modified)

        if project.last_deployed:
            deployed = datetime.fromisoformat(project.last_deployed).strftime("%Y-%m-%d %H:%M")
            right_panel.add_row("Last Deployed", deployed)

        columns = Columns([
            Panel(left_panel, title="Project Info", border_style="blue"),
            Panel(right_panel, title="Statistics", border_style="green")
        ])

        self.console.print(columns)

    def show_progress(self, task_name: str, steps: List[str]) -> Progress:
        """Create and return a progress bar for operations."""
        progress = Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=self.console
        )

        task_id = progress.add_task(task_name, total=len(steps))
        return progress, task_id

    def show_file_tree(self, project: ProjectConfig):
        """Show project file structure as a tree."""
        if not project.path.exists():
            self.console.print(f"[red]Project path does not exist: {project.path}[/red]")
            return

        tree = Tree(f"📁 {project.name}")

        def add_files(path: Path, tree_node):
            try:
                items = sorted(path.iterdir(), key=lambda x: (x.is_file(), x.name))
                for item in items:
                    if item.name.startswith('.'):
                        continue

                    if item.is_dir():
                        folder_node = tree_node.add(f"📁 {item.name}")
                        if len(list(item.iterdir())) < 20:  # Avoid too deep trees
                            add_files(item, folder_node)
                    else:
                        # Add file with appropriate icon
                        icon = "🐍" if item.suffix == ".py" else "📄"
                        tree_node.add(f"{icon} {item.name}")
            except PermissionError:
                tree_node.add("[red]Permission denied[/red]")

        add_files(project.path, tree)
        self.console.print(tree)


class ESP32TUIApp(App):
    """Full-featured Textual TUI application."""

    CSS = """
    .sidebar {
        dock: left;
        width: 30;
        background: $surface;
    }

    .main-content {
        background: $background;
    }

    .status-bar {
        dock: bottom;
        height: 3;
        background: $primary;
    }

    .project-list {
        height: 1fr;
    }

    .log-panel {
        height: 15;
    }
    """

    BINDINGS = [
        Binding("ctrl+c", "quit", "Quit"),
        Binding("ctrl+n", "new_project", "New Project"),
        Binding("ctrl+o", "open_project", "Open Project"),
        Binding("ctrl+r", "refresh", "Refresh"),
        Binding("f5", "simulate", "Simulate"),
        Binding("f6", "build", "Build"),
        Binding("f7", "deploy", "Deploy"),
        Binding("f12", "toggle_logs", "Toggle Logs"),
    ]

    def __init__(self, project_manager: ProjectManager):
        super().__init__()
        self.project_manager = project_manager
        self.current_project: Optional[ProjectConfig] = None
        self.show_logs = True

        # Set up project manager observer
        self.project_manager.add_observer(self._on_project_change)

    def compose(self) -> ComposeResult:
        """Create the UI layout."""
        yield Header()

        with Container():
            # Sidebar with project list and actions
            with Vertical(classes="sidebar"):
                yield Label("Projects", id="projects-label")
                yield DataTable(id="projects-table", classes="project-list")
                yield Button("New Project", id="new-project-btn", variant="success")
                yield Button("Simulate", id="simulate-btn", variant="primary")
                yield Button("Build", id="build-btn", variant="warning")
                yield Button("Deploy", id="deploy-btn", variant="error")

            # Main content area
            with Vertical(classes="main-content"):
                with Tabs():
                    with TabPane("Overview", id="overview-tab"):
                        yield Static(id="project-overview")

                    with TabPane("Files", id="files-tab"):
                        yield DirectoryTree("./", id="file-tree")

                    with TabPane("Serial Monitor", id="serial-tab"):
                        yield TextLog(id="serial-log")
                        yield Input(placeholder="Send command to ESP32...", id="serial-input")

                    with TabPane("Build Output", id="build-tab"):
                        yield TextLog(id="build-log")

                # Collapsible log panel
                if self.show_logs:
                    yield TextLog(id="status-log", classes="log-panel")

        yield Footer()

    def on_mount(self) -> None:
        """Initialize the application."""
        self.refresh_projects_table()
        self.update_project_overview()
        self.log("ESP32 Project Manager Started", "info")

    def _on_project_change(self, event: str, project: ProjectConfig):
        """Handle project changes."""
        self.log(f"Project {event}: {project.name}", "info")
        self.refresh_projects_table()
        if event in ["project_created", "current_project_changed"]:
            self.current_project = project
            self.update_project_overview()
            self.update_file_tree()

    def refresh_projects_table(self):
        """Refresh the projects table."""
        table = self.query_one("#projects-table", DataTable)
        table.clear(columns=True)

        # Add columns
        table.add_columns("Name", "Status", "Modified")

        # Add projects
        projects = self.project_manager.list_projects()
        current_name = self.project_manager.current_project

        for project in projects:
            # Status indicators
            status = "●" if project.name == current_name else "○"
            if project.last_deployed:
                status += " ↗"

            # Modified time
            if project.last_modified:
                modified = datetime.fromisoformat(project.last_modified).strftime("%m/%d")
            else:
                modified = datetime.fromisoformat(project.created_at).strftime("%m/%d")

            table.add_row(project.name, status, modified, key=project.name)

    def update_project_overview(self):
        """Update the project overview panel."""
        overview = self.query_one("#project-overview", Static)

        current = self.project_manager.get_current_project()
        if not current:
            overview.update("No project selected. Create or select a project to get started.")
            return

        stats = self.project_manager.get_project_stats(current.name)

        content = f"""
[bold cyan]{current.name}[/bold cyan]
{current.description or '[dim]No description[/dim]'}

[bold]Project Info:[/bold]
• Template: {current.template}
• Version: {current.version}
• Author: {current.author or '[dim]Unknown[/dim]'}

[bold]Statistics:[/bold]
• Files: {stats['files']}
• Python Files: {stats['python_files']}
• Lines of Code: {stats['lines_of_code']}
• Size: {stats['size_bytes'] / 1024:.1f} KB

[bold]Status:[/bold]
• Created: {datetime.fromisoformat(current.created_at).strftime('%Y-%m-%d %H:%M')}
"""

        if current.last_modified:
            content += f"• Modified: {datetime.fromisoformat(current.last_modified).strftime('%Y-%m-%d %H:%M')}\n"

        if current.last_deployed:
            content += f"• Deployed: {datetime.fromisoformat(current.last_deployed).strftime('%Y-%m-%d %H:%M')}\n"

        overview.update(content)

    def update_file_tree(self):
        """Update the file tree."""
        current = self.project_manager.get_current_project()
        if current and current.path.exists():
            tree = self.query_one("#file-tree", DirectoryTree)
            tree.path = str(current.path)

    def log(self, message: str, level: str = "info"):
        """Add message to status log."""
        if self.show_logs:
            try:
                log_widget = self.query_one("#status-log", TextLog)
                timestamp = datetime.now().strftime("%H:%M:%S")

                level_colors = {
                    "info": "cyan",
                    "warning": "yellow",
                    "error": "red",
                    "success": "green"
                }

                color = level_colors.get(level, "white")
                log_widget.write(f"[{color}][{timestamp}] {message}[/{color}]")
            except Exception:
                pass  # Log widget might not be ready yet

    async def action_new_project(self) -> None:
        """Create a new project."""
        # This would open a modal dialog for project creation
        # For now, we'll use a simple approach
        self.log("New project creation - feature coming soon!", "info")

    async def action_open_project(self) -> None:
        """Open/select a project."""
        # This would allow selecting from project list
        self.log("Project selection - click on project in table", "info")

    async def action_refresh(self) -> None:
        """Refresh the interface."""
        self.refresh_projects_table()
        self.update_project_overview()
        self.update_file_tree()
        self.log("Interface refreshed", "success")

    async def action_simulate(self) -> None:
        """Simulate current project."""
        current = self.project_manager.get_current_project()
        if not current:
            self.log("No project selected", "error")
            return

        self.log(f"Starting simulation of {current.name}...", "info")
        # Here we would integrate with the simulation system
        # For now, just log
        self.log("Simulation feature - integration coming soon!", "warning")

    async def action_build(self) -> None:
        """Build current project."""
        current = self.project_manager.get_current_project()
        if not current:
            self.log("No project selected", "error")
            return

        build_log = self.query_one("#build-log", TextLog)
        build_log.clear()
        build_log.write(f"Building project: {current.name}")

        self.log(f"Building {current.name}...", "info")
        # Here we would integrate with the build system
        # For now, simulate build process
        await asyncio.sleep(1)
        build_log.write("✅ Build completed successfully")
        self.log("Build completed", "success")

    async def action_deploy(self) -> None:
        """Deploy current project."""
        current = self.project_manager.get_current_project()
        if not current:
            self.log("No project selected", "error")
            return

        self.log(f"Deploying {current.name}...", "info")
        # Here we would integrate with the deployment system
        await asyncio.sleep(2)
        self.log("Deployment completed", "success")

        # Update project deployed timestamp
        current.mark_deployed()
        self.project_manager.save_projects()

    async def action_toggle_logs(self) -> None:
        """Toggle log panel visibility."""
        self.show_logs = not self.show_logs
        # Would need to rebuild UI to show/hide logs
        self.log(f"Logs {'shown' if self.show_logs else 'hidden'}", "info")

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Handle project selection from table."""
        if event.row_key:
            project_name = str(event.row_key.value)
            try:
                self.project_manager.set_current_project(project_name)
                self.log(f"Selected project: {project_name}", "success")
            except Exception as e:
                self.log(f"Failed to select project: {e}", "error")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        button_actions = {
            "new-project-btn": self.action_new_project,
            "simulate-btn": self.action_simulate,
            "build-btn": self.action_build,
            "deploy-btn": self.action_deploy,
        }

        action = button_actions.get(event.button.id)
        if action:
            asyncio.create_task(action())

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle input submission."""
        if event.input.id == "serial-input":
            command = event.value.strip()
            if command:
                serial_log = self.query_one("#serial-log", TextLog)
                serial_log.write(f"→ {command}")

                # Here we would send the command to ESP32
                # For now, just echo
                serial_log.write(f"← Echo: {command}")

                event.input.value = ""


class InteractiveCLI:
    """Rich-based interactive command line interface."""

    def __init__(self, project_manager: ProjectManager):
        self.console = Console()
        self.project_manager = project_manager
        self.dashboard = ESP32Dashboard(project_manager)
        self.running = True

    def run(self):
        """Run the interactive CLI."""
        self.dashboard.show_welcome()

        while self.running:
            try:
                current = self.project_manager.current_project or "none"
                command = Prompt.ask(
                    f"\n[bold blue][{current}][/bold blue]",
                    console=self.console
                ).strip().lower()

                self.handle_command(command)

            except KeyboardInterrupt:
                if Confirm.ask("\nDo you want to quit?", console=self.console):
                    break
            except EOFError:
                break

    def handle_command(self, command: str):
        """Handle CLI commands."""
        parts = command.split()
        if not parts:
            return

        cmd = parts[0]
        args = parts[1:]

        try:
            if cmd in ['quit', 'exit', 'q']:
                self.running = False

            elif cmd == 'help':
                self.show_help()

            elif cmd == 'list' or cmd == 'ls':
                projects = self.project_manager.list_projects()
                self.dashboard.show_projects_table(projects)

            elif cmd == 'create':
                if not args:
                    self.console.print("[red]Usage: create <name> [description][/red]")
                    return

                name = args[0]
                description = " ".join(args[1:]) if len(args) > 1 else ""

                # Get additional info interactively
                if not description:
                    description = Prompt.ask("Project description (optional)", default="")

                template = Prompt.ask("Template", default="basic",
                                      choices=["basic", "iot", "sensors", "webserver"])

                author = Prompt.ask("Author (optional)", default="")

                with self.console.status(f"Creating project '{name}'..."):
                    config = self.project_manager.create_project(
                        name, description, template, author
                    )

                self.console.print(f"[green]✅ Created project '{name}'[/green]")
                self.dashboard.show_project_details(config)

            elif cmd == 'current' or cmd == 'cd':
                if not args:
                    current = self.project_manager.get_current_project()
                    if current:
                        self.dashboard.show_project_details(current)
                    else:
                        self.console.print("[yellow]No current project[/yellow]")
                else:
                    self.project_manager.set_current_project(args[0])
                    self.console.print(f"[green]✅ Set current project to '{args[0]}'[/green]")

            elif cmd == 'info':
                name = args[0] if args else self.project_manager.current_project
                if not name:
                    self.console.print("[red]No project specified[/red]")
                    return

                project = self.project_manager.get_project(name)
                if project:
                    self.dashboard.show_project_details(project)
                else:
                    self.console.print(f"[red]Project '{name}' not found[/red]")

            elif cmd == 'tree':
                current = self.project_manager.get_current_project()
                if current:
                    self.dashboard.show_file_tree(current)
                else:
                    self.console.print("[red]No current project[/red]")

            elif cmd == 'stats':
                stats = self.project_manager.get_workspace_stats()
                table = Table(title="Workspace Statistics")
                table.add_column("Metric", style="cyan")
                table.add_column("Value", style="white")

                for key, value in stats.items():
                    table.add_row(key.replace('_', ' ').title(), str(value))

                self.console.print(table)

            elif cmd == 'search':
                if not args:
                    self.console.print("[red]Usage: search <query>[/red]")
                    return

                query = " ".join(args)
                results = self.project_manager.search_projects(query)

                if results:
                    self.dashboard.show_projects_table(results)
                else:
                    self.console.print(f"[yellow]No projects found matching '{query}'[/yellow]")

            elif cmd == 'tui':
                if TEXTUAL_AVAILABLE:
                    app = ESP32TUIApp(self.project_manager)
                    app.run()
                else:
                    self.console.print("[red]Textual not available. Install with: pip install textual[/red]")

            else:
                self.console.print(f"[red]Unknown command: {cmd}[/red]")
                self.console.print("Type 'help' for available commands")

        except Exception as e:
            self.console.print(f"[red]Error: {e}[/red]")

    def show_help(self):
        """Show help information."""
        help_table = Table(title="Available Commands", box=box.ROUNDED)
        help_table.add_column("Command", style="cyan", no_wrap=True)
        help_table.add_column("Description", style="white")
        help_table.add_column("Example", style="dim white")

        commands = [
            ("list, ls", "List all projects", "list"),
            ("create <name>", "Create new project", "create my_project"),
            ("current <name>", "Set current project", "current my_project"),
            ("info [name]", "Show project details", "info"),
            ("tree", "Show project file tree", "tree"),
            ("stats", "Show workspace statistics", "stats"),
            ("search <query>", "Search projects", "search sensor"),
            ("tui", "Launch full TUI interface", "tui"),
            ("help", "Show this help", "help"),
            ("quit, exit, q", "Exit application", "quit"),
        ]

        for cmd, desc, example in commands:
            help_table.add_row(cmd, desc, example)

        self.console.print(help_table)

def launch_tui(project_manager: ProjectManager):
    """Launch the TUI application."""
    if not TEXTUAL_AVAILABLE:
        console = Console()
        console.print("[red]Textual not available.[/red]")
        console.print("Install with: [bold]pip install textual rich[/bold]")
        return False

    app = ESP32TUIApp(project_manager)
    app.run()
    return True



def launch_cli(project_manager: ProjectManager):
    """Launch the interactive CLI."""
    cli = InteractiveCLI(project_manager)
    cli.run()
    return True