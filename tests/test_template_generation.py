from esp32_manager.templates import get_template_files
from esp32_manager.core.config_manager import ProjectConfig


def test_basic_template_files(tmp_path):
    config = ProjectConfig(name='demo', path=tmp_path)
    files = get_template_files('basic', config)
    assert 'src/main.py' in files
    assert 'README.md' in files