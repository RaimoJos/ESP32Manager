import argparse
import logging
import sys
from pathlib import Path

from app import ESP32ManagerApp
from esp32_manager.utils.logger import setup_logging

sys.path.insert(0, str(Path(__file__).parent))

def create_parser() -> argparse.ArgumentParser:
    """Create command-line argument parser."""
    parser = argparse.ArgumentParser(
        description="ESP32 Project Manager - Development Suite",
        epilog="""
Examples:
    %(prog)s init                           # Initialize workspace
    %(prog)s create my_project              # Create new project
    %(prog)s list                           # List all projects
    %(prog)s interactive                    # Interactive CLI mode
    %(prog)s interactive --interface tui    # Terminal UI mode
    %(prog)s web                            # Web interface
        """,
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    # Global options
    parser.add_argument('--workspace', '-w', type=Path,
                        help='Workspace directory (default: current directory)')
    parser.add_argument('--verbose', '-v', action='store_true',
                        help='Enable verbose logging')
    parser.add_argument('--log-file', help='Log file path')

    subparsers = parser.add_subparsers(dest='command', help='Available commands')

    # Initialize workspace
    subparsers.add_parser('init', help='Initialize workspace in current directory')

    # Project management commands
    create_cmd_parser = subparsers.add_parser('create', help='Create new project')
    create_cmd_parser.add_argument('name', help='Project name')
    create_cmd_parser.add_argument('--description', help='Project description')
    create_cmd_parser.add_argument('--template', choices=['basic', 'iot', 'sensors', 'webserver'],
                                   help='Project template')
    create_cmd_parser.add_argument('--author', '-a', default='', help='Project author name')

    # List projects
    list_parser = subparsers.add_parser('list', help='List all projects')
    list_parser.add_argument('--filter', '-f', help='Filter by tag')

    # Set current project
    current_parser = subparsers.add_parser('current', help='Set current project')
    current_parser.add_argument('name', help='Project name')

    # Project info
    info_parser = subparsers.add_parser('info', help='Show project information')
    info_parser.add_argument('name', nargs='?', help='Project name (current if not specified)')

    # Development commands
    sim_parser = subparsers.add_parser('simulate', help='Simulate project locally')
    sim_parser.add_argument('name', nargs='?', help='Project name (current if not specified)')

    build_parser = subparsers.add_parser('build', help='Build project')
    build_parser.add_argument('name', nargs='?', help='Project name (current if not specified)')

    deploy_parser = subparsers.add_parser('deploy', help='Deploy project to ESP32')
    deploy_parser.add_argument('name', nargs='?', help='Project name (current if not specified)')
    deploy_parser.add_argument('--device', '-d', default='/dev/ttyUSB0', help='Target device')

    test_parser = subparsers.add_parser('test', help='Run tests for project')
    test_parser.add_argument('name', nargs='?', help='Project name (current if not specified)')

    # Utility commands
    delete_parser = subparsers.add_parser('delete', help='Delete project')
    delete_parser.add_argument('name', help='Project name')
    delete_parser.add_argument('--remove-files', action='store_true', help='Remove project files')

    export_parser = subparsers.add_parser('export', help='Export project as archive')
    export_parser.add_argument('name', help='Project name')
    export_parser.add_argument('--output', '-o', help='Output path')

    stats_parser = subparsers.add_parser('stats', help='Show workspace statistics')
    stats_parser.add_argument('--workspace', '-w', type=Path,
                        help='Workspace directory (default: current directory)')

    search_parser = subparsers.add_parser('search', help='Search projects')
    search_parser.add_argument('query', help='Search query')

    interactive_parser = subparsers.add_parser('interactive', help='Start interactive mode')
    interactive_parser.add_argument('--interface', '-i', choices=['cli', 'tui'],
                                    default='cli', help='Interface type')

    # Web interface
    web_parser = subparsers.add_parser('web', help='Start web interface')
    web_parser.add_argument('--host', default='127.0.0.1', help='Host address')
    web_parser.add_argument('--port', '-p', type=int, default=8000, help='Port number')

    return parser

def main():
    """Main entry point."""
    parser = create_parser()
    args = parser.parse_args()

    # Set up logging
    log_level = "DEBUG" if args.verbose else "INFO"
    setup_logging(log_level, args.log_file)

    logger = logging.getLogger(__name__)
    logger.info("ESP32 Project Manager starting...")

    try:
        # Initialize application
        app = ESP32ManagerApp(args.workspace)

        # Route to appropriate interface
        if args.command == 'interactive':
            success = app.run_interactive(args.interface)
        elif args.command == 'web':
            success = app.run_web(args.host, args.port)
        elif args.command:
            success = app.run_cli(args)
        else:
            # No command specified, show help and offer interactive mode
            parser.print_help()
            print("\n" + "=" * 60)
            print("No command specified. Starting interactive mode.")
            print("=" * 60)
            success = app.run_interactive('cli')

        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Application failed: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()