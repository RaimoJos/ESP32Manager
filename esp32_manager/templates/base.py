from typing import List, Dict

from pyexpat import features


class BaseTemplate:
    """Base class for all project templates."""

    description: str = "Base template"
    author: str = "ESP32Manager"
    version: str = "1.0.0"
    dependencies: List[str] = []
    features: List[str] = []

    def __init__(self, config):
        self.config = config
        self.project_name = config.name
        self.description = config.description
        self.author = config.author

    def generate_files(self) ->  Dict[str, str]:
        """Generate project files. Must be implemented by subclasses."""
        raise NotImplementedError("Subclasses must implement generate_files")

    def get_common_files(self) -> Dict[str, str]:
        """Get common files that all templates should have."""
        return {
            'README.md': self._generate_readme(),
            '.gitignore': self._generate_gitignore(),
            'requirements.txt': self._generate_requirements(),
            'projects.json': self._generate_project_config(),
        }

    def _generate_readme(self) -> str:
        """Generate README.md content."""
        return f"""# {self.project_name}

{self.description or 'ESP32 project created with ESP32Manager'}

## Description
This project was created using the **{self.__class__.__name__.replace('Template', '')}** template.

## Author
{self.author or 'Unknown'}

## Getting Started

### Prerequisites
- ESP32 development board
- MicroPython firmware
- USB cable for programming

### Installation
1. Connect your ESP32 to your computer
2. Deploy the project using ESP32Manager:
    ```bash
    python main.py deploy {self.project_name}

### Usage
{self._get_usage_instructions()}

## Project structure
```
{self.project_name}/
├── src/           # Source code
├── tests/         # Test files
├── docs/          # Documentation
├── assets/        # Assets (images, data files)
└── lib/           # Libraries
```

## Features
{self._format_features()}

## License
This project is licensed under the MIT License.
"""

    @staticmethod
    def _get_usage_instructions() -> str:
        """Get template-specific usage instructions."""
        return "Add your usage instructions here."

    def _format_features(self) -> str:
        """Format features list for README."""
        if not self.features:
            return "- Basic ESP32 functionality"

        return "\n".join(f"- {features}" for feature in self.features)

    @staticmethod
    def _generate_gitignore() -> str:
        """Generate .gitignore content."""
        return """# Byte-compiled / optimized / DLL files
__pycache__/
*.py[cod]
*$py.class

# MicroPython
*.mpy

# IDE
.vscode/
.idea/

# OS
.DS_Store
Thumbs.db

# Project specific
build/
dist/
*.log
"""

    def _generate_requirements(self) -> str:
        """Generate requirements.txt content."""
        if not self.dependencies:
            return "# No additional dependencies required\n"

        return "\n".join(self.dependencies) + "\n"

    def _generate_project_config(self) -> str:
        """Generate project.json content."""
        import json
        config_data = {
            'name': self.project_name,
            'description': self.description,
            'template': self.__class__.__name__.replace('Template', '').lower(),
            'version': '1.0.0',
            'author': self.author,
            'created_with': 'ESP32Manager',
            'micropython_version': '1.20+',
            'board': 'esp32',
        }
        return json.dumps(config_data, indent=2)