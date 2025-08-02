from __future__ import annotations
from dataclasses import dataclass, asdict
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Any, Dict, Optional

logger = logging.getLogger(__name__)

@dataclass
class ProjectConfig:
    """Project configuration."""
    name: str
    path: Path
    description: str = ""
    target_device: str = "esp32"
    main_file: str = "main.py"
    template: str = "basic"
    version: str = "1.0.0"
    author: str = ""
    dependencies: List[str] = None
    build_config: Dict[str, Any] = None
    deploy_config: Dict[str, Any] = None
    hardware_config: Dict[str, Any] = None
    tags: List[str] = None
    created_at: str = ""
    last_modified: str = ""
    last_deployed: str = ""
    git_repo: Optional[str] = None

    def __post_init__(self):
        if self.dependencies is None:
            self.dependencies = []
        if self.build_config is None:
            self.build_config = {
                "strip_type_hints": True,
                "optimize": True,
                "include_tests": False
            }
        if self.deploy_config is None:
            self.deploy_config = {
                "device": ":",
                "max_retries": 3,
                "backup_before_deploy": True,
                "verify_after_deploy": True
            }
        if self.hardware_config is None:
            self.hardware_config = {
                "board": "esp32",
                "flash_size": "4MB",
                "frequency": "240MHz"
            }
        if self.tags is None:
            self.tags = []
        if not self.created_at:
            self.created_at = datetime.now().isoformat()

    def update_modified(self):
        """Update the last modified timestamp."""
        self.last_modified = datetime.now().isoformat()

    def mark_deployed(self):
        """Mark project as deployed."""
        self.last_deployed = datetime.now().isoformat()

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary with path as string."""
        data = asdict(self)
        data['path'] = str(self.path)
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ProjectConfig:
        """Create from dictionary with path conversion."""
        data = data.copy()
        data['path'] =Path(data['path'])
        return cls(**data)