import json
import shutil
from pathlib import Path
import sys

import pytest

# Ensure project root is on sys.path for imports
sys.path.append(str(Path(__file__).resolve().parents[1]))

from esp32_manager.core.project_manager import ProjectManager
from esp32_manager.core.config_manager import ProjectConfig
from esp32_manager.utils.exceptions import ProjectValidationError


def create_zip_with_project(tmp_path: Path, with_config: bool = True):
    source = tmp_path / 'src_project'
    source.mkdir()
    if with_config:
        data = {
            'name': 'ImportedProject',
            'path': '.'
        }
        with open(source / 'project.json', 'w', encoding='utf-8') as f:
            json.dump(data, f)
    # create a dummy file
    (source / 'dummy.txt').write_text('hello', encoding='utf-8')

    archive = tmp_path / 'archive.zip'
    shutil.make_archive(str(archive.with_suffix('')), 'zip', source)
    return archive


def test_import_project_with_project_json(tmp_path):
    archive = create_zip_with_project(tmp_path, with_config=True)
    workspace = tmp_path / 'workspace'
    workspace.mkdir()
    pm = ProjectManager(workspace)

    config = pm.import_project(archive)

    assert config is not None
    assert config.name == 'ImportedProject'
    assert pm.get_project('ImportedProject') is not None
    assert pm.current_project == 'ImportedProject'
    assert (workspace / 'ImportedProject').exists()
    # Ensure project.json from archive is preserved/updated
    assert (workspace / 'ImportedProject' / 'project.json').exists()


def test_import_project_without_project_json(tmp_path):
    archive = create_zip_with_project(tmp_path, with_config=False)
    workspace = tmp_path / 'workspace'
    workspace.mkdir()
    pm = ProjectManager(workspace)

    config = pm.import_project(archive, name='ManualName')

    assert config is not None
    assert config.name == 'ManualName'
    assert pm.get_project('ManualName') is not None
    assert (workspace / 'ManualName' / 'project.json').exists()

def test_validate_project_name(tmp_path):
    manager = ProjectManager(tmp_path)
    manager.projects['existing'] = ProjectConfig(name='existing', path=tmp_path / 'existing')

    with pytest.raises(ProjectValidationError):
        manager.validate_project_name('existing')
    with pytest.raises(ProjectValidationError):
        manager.validate_project_name('invalid/name')
    assert manager.validate_project_name('new_project')


def test_create_project_creates_structure(tmp_path):
    manager = ProjectManager(tmp_path)
    config = manager.create_project('demo', template='basic')

    project_path = tmp_path / 'demo'
    assert project_path.exists()
    assert (project_path / 'src' / 'main.py').exists()
    assert manager.projects['demo'].name == 'demo'