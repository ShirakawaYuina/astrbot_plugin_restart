from typing import Any

from astrbot.core.star.context import Context

from .ssh_restart import (
    SshRestartConfig,
    execute_ssh_command,
    execute_ssh_docker_restart,
    load_ssh_restart_config,
)
from .utils import format_docker_stats_output


class DashboardClient:
    """SSH 重启客户端，负责在宿主机执行 Docker 运维命令。"""

    def __init__(self, context: Context, plugin_config: Any | None = None):
        self.context = context
        self.plugin_config = plugin_config

    # -------------------- 生命周期 --------------------
    async def initialize(self):
        """保持生命周期接口，便于插件入口无需关心客户端内部实现。"""

    async def terminate(self):
        """当前 SSH 客户端按需建立短连接，无需额外释放常驻资源。"""

    # -------------------- 公共接口 --------------------
    async def restart(self) -> None:
        """
        通过 SSH 在宿主机重启 Docker 容器。

        业务意图：
        - AstrBot 最终运行在 Docker 容器内，容器内不一定存在 Docker CLI；
        - 宿主机才拥有完整 Docker 控制权，因此统一通过 SSH 执行 docker restart；
        - 删除 dashboard/docker_cli 多模式分支，避免运行时路径不一致。
        """
        if self.plugin_config is None:
            raise RuntimeError("SSH 重启缺少插件配置")
        ssh_config = load_ssh_restart_config(self.plugin_config)
        await execute_ssh_docker_restart(ssh_config)

    async def get_docker_stats(self) -> str:
        """通过 SSH 获取 Docker 容器瞬时资源占用。"""
        if self.plugin_config is None:
            raise RuntimeError("SSH 命令执行缺少插件配置")
        ssh_config = load_ssh_restart_config(self.plugin_config)
        output = await self._run_ssh_command(
            ssh_config, ["docker", "stats", "--no-stream"]
        )
        return format_docker_stats_output(output)

    # -------------------- 内部工具 --------------------
    async def _run_ssh_command(
        self, ssh_config: SshRestartConfig, command: list[str]
    ) -> str:
        """通过 SSH 运行远程命令，供重启和资源统计复用。"""
        if self.plugin_config is None:
            raise RuntimeError("SSH 命令执行缺少插件配置")
        return await execute_ssh_command(ssh_config, command)
