import json
from pathlib import Path

from esp32_manager.core.build_system import BuildSystem, BuildConfig
from esp32_manager.core.config_manager import ProjectConfig


def test_build_creates_metadata(tmp_path):
    project_dir = tmp_path / 'proj'
    src_dir = project_dir / 'src'
    src_dir.mkdir(parents=True)
    (src_dir / 'main.py').write_text('print("hello")')

    config = ProjectConfig(name='proj', path=project_dir)
    build_system = BuildSystem(tmp_path)
    build_config = BuildConfig(
        strip_comments=False,
        strip_docstrings=False,
        strip_type_hints=False,
        optimize_imports=False,
        minify_code=False,
        include_tests=False,
        cross_compile=False,
    )

    result = build_system.build_project(config, build_config)
    assert result.success

    metadata_path = build_system.build_dir / 'proj' / 'build_metadata.json'
    assert metadata_path.exists()
    data = json.loads(metadata_path.read_text())
    assert data['project']['name'] == 'proj'