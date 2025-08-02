from pathlib import Path

from esp32_manager.core.config_manager import ProjectConfig

def test_post_init_defaults():
    pc =  ProjectConfig(name='TestProject', path=('.'))

    assert pc.dependencies == []
    assert pc.build_config['strip_type_hints'] is True
    assert pc.deploy_config['max_retries'] == 3
    assert pc.hardware_config['board'] == 'esp32'
    assert pc.tags == []
    assert pc.created_at != ""