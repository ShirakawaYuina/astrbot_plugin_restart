import asyncio
import json
import shlex
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:
    import asyncssh
except ImportError:  # pragma: no cover - 运行环境未安装依赖时，导入仍应可用。
    asyncssh = None  # type: ignore[assignment]

from astrbot.core.utils.astrbot_path import get_astrbot_config_path


@dataclass(frozen=True)
class SshRestartConfig:
    """SSH 重启配置，集中表达一次远程 Docker 重启所需的最小参数。"""

    host: str
    username: str
    password: str = ""
    port: int = 22
    private_key: str = ""
    timeout: int = 10
    containers: list[str] = field(default_factory=lambda: ["astrbot", "napcat"])
    use_sudo: bool = False
    known_hosts_path: str = ""


def _read_json_config(config_name: str) -> dict[str, Any]:
    """读取 AstrBot 配置目录下的插件配置，文件缺失或解析失败时返回空配置。"""
    config_path = Path(get_astrbot_config_path()) / config_name
    if not config_path.is_file():
        return {}
    try:
        return json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        # 配置文件损坏不应让导入阶段失败，后续必填校验会给出更明确的业务错误。
        return {}


def _config_get(config: Any, key: str, default: Any = None) -> Any:
    """兼容 AstrBotConfig 与普通 dict，便于测试和运行时共用配置读取逻辑。"""
    if hasattr(config, "get"):
        return config.get(key, default)
    return default


def _first_not_empty(*values: Any, default: Any = "") -> Any:
    """按优先级返回第一个非空值，用于插件配置覆盖 SSH 插件配置。"""
    for value in values:
        if value not in (None, ""):
            return value
    return default


def _normalize_container_names(raw_containers: Any) -> list[str]:
    """规范化容器名列表，避免空值或非字符串内容进入远程命令。"""
    if isinstance(raw_containers, str):
        containers = raw_containers.replace(",", " ").split()
    elif isinstance(raw_containers, list):
        containers = [str(item).strip() for item in raw_containers]
    else:
        containers = ["astrbot", "napcat"]

    containers = [name for name in containers if name]
    if not containers:
        raise RuntimeError("Docker 容器列表不能为空")
    return containers


def load_ssh_restart_config(config: Any) -> SshRestartConfig:
    """
    加载 SSH 重启配置。

    业务意图：
    - 优先读取重启插件自己的 SSH 字段，便于后续独立配置；
    - 未填写时复用 astrbot_plugin_ssh 的配置，减少用户重复录入主机信息；
    - 命令相关配置仍由重启插件控制，避免 SSH 插件白名单影响重启流程。
    """
    ssh_plugin_config = _read_json_config("astrbot_plugin_ssh_config.json")

    host = _first_not_empty(
        _config_get(config, "ssh_host"),
        ssh_plugin_config.get("host"),
    )
    username = _first_not_empty(
        _config_get(config, "ssh_username"),
        ssh_plugin_config.get("username"),
        default="root",
    )
    password = _first_not_empty(
        _config_get(config, "ssh_password"),
        ssh_plugin_config.get("password"),
    )
    private_key = _first_not_empty(
        _config_get(config, "ssh_private_key"),
        ssh_plugin_config.get("private_key"),
    )
    known_hosts_path = _first_not_empty(
        _config_get(config, "ssh_known_hosts_path"),
        ssh_plugin_config.get("known_hosts_path"),
    )

    if not host:
        raise RuntimeError(
            "SSH 主机地址未配置，请填写 ssh_host 或 astrbot_plugin_ssh 的 host"
        )
    if not username:
        raise RuntimeError(
            "SSH 用户名未配置，请填写 ssh_username 或 astrbot_plugin_ssh 的 username"
        )
    if not password and not private_key:
        raise RuntimeError("SSH 密码或私钥未配置，请至少填写一种认证方式")

    port = int(
        _first_not_empty(
            _config_get(config, "ssh_port"),
            ssh_plugin_config.get("port"),
            default=22,
        )
    )
    timeout = int(
        _first_not_empty(
            _config_get(config, "ssh_timeout"),
            ssh_plugin_config.get("timeout"),
            default=10,
        )
    )

    return SshRestartConfig(
        host=str(host),
        port=port,
        username=str(username),
        password=str(password),
        private_key=str(private_key),
        timeout=timeout,
        containers=_normalize_container_names(
            _config_get(config, "docker_containers", ["astrbot", "napcat"])
        ),
        use_sudo=bool(_config_get(config, "ssh_use_sudo", False)),
        known_hosts_path=str(known_hosts_path),
    )


def _build_shell_command(command_parts: list[str], *, use_sudo: bool = False) -> str:
    """构造可安全传给远程 shell 的命令字符串。"""
    if use_sudo:
        command_parts = ["sudo", *command_parts]
    return " ".join(shlex.quote(part) for part in command_parts)


def build_docker_restart_command(config: SshRestartConfig) -> str:
    """构造远程 Docker 重启命令，并对容器名做 shell 转义。"""
    command_parts = ["docker", "restart", *config.containers]
    return _build_shell_command(command_parts, use_sudo=config.use_sudo)


async def execute_ssh_command(
    config: SshRestartConfig, command_parts: list[str]
) -> str:
    """通过 SSH 执行任意一条白名单内运维命令，返回 stdout。"""
    if config.use_sudo:
        command_parts = ["sudo", *command_parts]
    return await _execute_remote_shell_command(
        config,
        " ".join(shlex.quote(part) for part in command_parts),
    )


async def execute_ssh_docker_restart(config: SshRestartConfig) -> str:
    """
    通过 SSH 在宿主机执行 Docker 重启命令。

    边界条件说明：
    - 私钥优先于密码，避免同时传入两种认证方式造成服务端拒绝；
    - known_hosts 为空时沿用 asyncssh 默认策略，不在重启插件中维护额外主机指纹文件；
    - stderr 与 stdout 合并为错误信息，方便聊天端直接看到 Docker/SSH 的失败原因。
    """
    return await _execute_remote_shell_command(
        config, build_docker_restart_command(config)
    )


async def _execute_remote_shell_command(config: SshRestartConfig, command: str) -> str:
    """执行已经完成 shell 转义的远程命令。"""
    if asyncssh is None:
        raise RuntimeError("缺少 asyncssh 依赖，请先安装 requirements.txt 中列出的依赖")

    client_keys = None
    if config.private_key:
        client_keys = [asyncssh.import_private_key(config.private_key)]

    connect_kwargs: dict[str, Any] = {
        "port": config.port,
        "username": config.username,
        "login_timeout": config.timeout,
        "known_hosts": config.known_hosts_path or None,
    }
    if client_keys:
        connect_kwargs["client_keys"] = client_keys
    else:
        connect_kwargs["password"] = config.password

    try:
        async with asyncssh.connect(config.host, **connect_kwargs) as connection:
            result = await asyncio.wait_for(
                connection.run(command, check=False),
                timeout=config.timeout,
            )
    except asyncio.TimeoutError as exc:
        raise RuntimeError(f"SSH 执行超时：{config.timeout} 秒") from exc
    except (OSError, asyncssh.Error) as exc:
        raise RuntimeError(f"SSH 连接或认证失败：{exc}") from exc

    if result.exit_status != 0:
        message = (result.stderr or result.stdout).strip()
        raise RuntimeError(f"远程命令执行失败：{message or result.exit_status}")
    return result.stdout.strip()
