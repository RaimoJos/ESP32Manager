import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from esp32_manager.core.project_manager import ProjectManager

def test_git_plugin_init_commit_and_status(tmp_path):
    manager = ProjectManager(tmp_path)

    plugin = manager.get_plugin('git_integration')
    assert plugin is not None

    repo_dir = tmp_path / 'repo'
    repo_dir.mkdir()

    # Initialize repository
    manager.run_plugin('git_integration', 'init_repo', path=repo_dir)

    # Create a file and commit it
    (repo_dir / 'test.txt').write_text('hello', encoding='utf-8')
    manager.run_plugin('git_integration', 'commit_all', path=repo_dir, message='init')

    # Repository should be clean after commit
    status = manager.run_plugin('git_integration', 'get_status', path=repo_dir)
    assert status == ''