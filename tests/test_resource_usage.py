import json
from pathlib import Path

import pytest

from utils import build_resource_usage_message


def test_build_resource_usage_message_includes_docker_stats():
    system_info = "CPU：12.3%\n内存：3.0GB/8.0GB(37.5%)\n磁盘：120.0GB/256.0GB(46.9%)"
    docker_stats = (
        "CONTAINER ID   NAME      CPU %     MEM USAGE / LIMIT   MEM %\n"
        "abc123         astrbot   3.21%     120MiB / 2GiB       5.86%\n"
        "def456         napcat    1.23%     10MiB / 1GiB        0.98%"
    )

    assert build_resource_usage_message(system_info, docker_stats) == (
        "系统资源占用：\n"
        "CPU：12.3%\n"
        "内存：3.0GB/8.0GB(37.5%)\n"
        "磁盘：120.0GB/256.0GB(46.9%)\n\n"
        "Docker 容器资源占用：\n"
        "CONTAINER ID   NAME      CPU %     MEM USAGE / LIMIT   MEM %\n"
        "abc123         astrbot   3.21%     120MiB / 2GiB       5.86%\n"
        "def456         napcat    1.23%     10MiB / 1GiB        0.98%"
    )


def test_build_resource_usage_message_keeps_system_info_when_docker_fails():
    system_info = "CPU：12.3%"

    assert build_resource_usage_message(system_info, docker_error="SSH 连接失败") == (
        "系统资源占用：\nCPU：12.3%\n\n"
        "Docker 容器资源占用：获取失败（SSH 连接失败）"
    )


@pytest.mark.parametrize("removed_key", ["restart_method"])
def test_config_schema_only_keeps_ssh_restart_mode(removed_key):
    schema_path = Path(__file__).resolve().parents[1] / "_conf_schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))

    assert removed_key not in schema
