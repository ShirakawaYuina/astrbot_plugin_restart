from types import SimpleNamespace

import pytest

from ssh_restart import (
    SshRestartConfig,
    build_docker_restart_command,
    load_ssh_restart_config,
)


def test_build_docker_restart_command_uses_configured_container_order():
    config = SshRestartConfig(
        host="example.com",
        username="root",
        password="secret",
        containers=["astrbot", "napcat"],
    )

    assert build_docker_restart_command(config) == "docker restart astrbot napcat"


def test_build_docker_restart_command_can_use_sudo():
    config = SshRestartConfig(
        host="example.com",
        username="root",
        password="secret",
        containers=["astrbot", "napcat"],
        use_sudo=True,
    )

    assert build_docker_restart_command(config) == "sudo docker restart astrbot napcat"


def test_load_ssh_restart_config_reads_plugin_config_first(tmp_path, monkeypatch):
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    monkeypatch.setattr("ssh_restart.get_astrbot_config_path", lambda: str(config_dir))

    config = load_ssh_restart_config(
        SimpleNamespace(
            get=lambda key, default=None: {
                "restart_method": "ssh",
                "ssh_host": "restart.example.com",
                "ssh_port": 2222,
                "ssh_username": "deploy",
                "ssh_password": "secret",
                "ssh_private_key": "",
                "ssh_timeout": 7,
                "ssh_use_sudo": True,
                "docker_containers": ["astrbot", "napcat"],
            }.get(key, default)
        )
    )

    assert config == SshRestartConfig(
        host="restart.example.com",
        port=2222,
        username="deploy",
        password="secret",
        timeout=7,
        containers=["astrbot", "napcat"],
        use_sudo=True,
    )


def test_load_ssh_restart_config_falls_back_to_ssh_plugin_config(tmp_path, monkeypatch):
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "astrbot_plugin_ssh_config.json").write_text(
        """{
  "host": "ssh-plugin.example.com",
  "port": 22,
  "username": "root",
  "password": "secret",
  "private_key": "",
  "timeout": 10
}""",
        encoding="utf-8",
    )
    monkeypatch.setattr("ssh_restart.get_astrbot_config_path", lambda: str(config_dir))

    config = load_ssh_restart_config(
        SimpleNamespace(
            get=lambda key, default=None: {
                "restart_method": "ssh",
                "docker_containers": ["astrbot", "napcat"],
            }.get(key, default)
        )
    )

    assert config == SshRestartConfig(
        host="ssh-plugin.example.com",
        username="root",
        password="secret",
        timeout=10,
        containers=["astrbot", "napcat"],
    )


def test_load_ssh_restart_config_rejects_missing_host(tmp_path, monkeypatch):
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    monkeypatch.setattr("ssh_restart.get_astrbot_config_path", lambda: str(config_dir))

    with pytest.raises(RuntimeError, match="SSH 主机地址未配置"):
        load_ssh_restart_config(
            SimpleNamespace(
                get=lambda key, default=None: {
                    "restart_method": "ssh",
                    "docker_containers": ["astrbot", "napcat"],
                }.get(key, default)
            )
        )
