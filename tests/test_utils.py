from types import SimpleNamespace

import utils


def test_format_docker_stats_output_with_content():
    raw_output = """
CONTAINER ID   NAME      CPU %     MEM USAGE / LIMIT   MEM %
abc123         napcat    1.23%     10MiB / 1GiB        0.98%
def456         astrbot   3.21%     120MiB / 2GiB       5.86%
"""
    expected = (
        "CONTAINER ID   NAME      CPU %     MEM USAGE / LIMIT   MEM %\n"
        "abc123         napcat    1.23%     10MiB / 1GiB        0.98%\n"
        "def456         astrbot   3.21%     120MiB / 2GiB       5.86%"
    )
    assert utils.format_docker_stats_output(raw_output) == expected


def test_format_docker_stats_output_when_empty():
    assert utils.format_docker_stats_output(" \n\t") == "未获取到 Docker 资源数据"


def test_get_restart_container_commands():
    assert utils.get_restart_container_commands() == [
        ["docker", "restart", "napcat", "astrbot"],
    ]


def test_get_system_resource_info(monkeypatch):
    monkeypatch.setattr(utils.psutil, "cpu_percent", lambda interval: 12.3)
    monkeypatch.setattr(
        utils.psutil,
        "virtual_memory",
        lambda: SimpleNamespace(total=8 * 1024**3, available=5 * 1024**3),
    )
    monkeypatch.setattr(
        utils.psutil,
        "disk_usage",
        lambda _path: SimpleNamespace(total=256 * 1024**3, used=120 * 1024**3),
    )

    assert (
        utils.get_system_resource_info()
        == "CPU：12.3%\n内存：3.0GB/8.0GB(37.5%)\n磁盘：120.0GB/256.0GB(46.9%)"
    )
