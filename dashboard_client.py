# dashboard_client.py

import asyncio
import os
import shutil
import subprocess
import time
from typing import Any

import aiohttp

from astrbot.api import logger
from astrbot.core.star.context import Context
from astrbot.core.star.star import StarMetadata

from .utils import format_docker_stats_output, get_restart_container_commands


class DashboardClient:
    """
    面板 HTTP 客户端
    - 复用 aiohttp.ClientSession
    - 自动缓存 & 续期
    """

    # token 有效期阈值（秒）
    TOKEN_VALID_THRESHOLD = 23 * 3600

    def __init__(self, context: Context):
        self.context = context
        self.stars: list[StarMetadata] = context.get_all_stars()
        self.star_manager = self.context._star_manager

        dbc = context.get_config().get("dashboard", {})
        self.host = dbc.get("host", "127.0.0.1")
        self.port = int(os.environ.get("DASHBOARD_PORT", dbc.get("port", 6185)))
        if self.host == "0.0.0.0":
            self.host = "127.0.0.1"

        # 接口地址
        self.login_url = f"http://{self.host}:{self.port}/api/auth/login"
        self.restart_url = f"http://{self.host}:{self.port}/api/stat/restart-core"

        # 缓存用
        self._session: aiohttp.ClientSession | None = None
        self._token: str | None = None
        self._token_ts: float | None = None

    # -------------------- 生命周期 --------------------
    async def initialize(self):
        self._session = aiohttp.ClientSession()

    async def terminate(self):
        if self._session and not self._session.closed:
            await self._session.close()

    # -------------------- 公共接口 --------------------
    async def restart(self) -> None:
        """同时重启 napcat 与 astrbot 容器。"""
        await self.restart_docker_containers()

    async def restart_docker_containers(self) -> None:
        """
        同时重启 napcat 与 astrbot 容器。

        业务意图：
        - 用户明确要求使用 docker restart napcat astrbot；
        - 不再调用面板 restart-core 接口，避免 AstrBot 额外再重启一次；
        - Docker 命令失败时抛出异常，让命令入口可以明确提示失败原因。
        """
        commands = get_restart_container_commands()
        await self._run_docker_command(commands[0])

    async def get_docker_stats(self) -> str:
        """获取 Docker 容器瞬时资源占用，用于重启完成后的回执消息。"""
        output = await self._run_docker_command(["docker", "stats", "--no-stream"])
        return format_docker_stats_output(output)

    # -------------------- 内部工具 --------------------
    async def _run_docker_command(self, command: list[str]) -> str:
        """
        在线程池中执行 Docker 命令，避免阻塞 AstrBot 的异步事件循环。

        边界条件说明：
        - docker 不在 PATH 时给出明确错误；
        - 合并 stderr，便于把 Docker 失败原因回传给调用方。
        """
        if shutil.which(command[0]) is None:
            raise RuntimeError("未找到 docker 命令，请确认 Docker 已安装并在 PATH 中")

        def run_command() -> str:
            result = subprocess.run(
                command,
                capture_output=True,
                check=False,
                encoding="utf-8",
                errors="replace",
                text=True,
            )
            if result.returncode != 0:
                message = (result.stderr or result.stdout).strip()
                raise RuntimeError(f"Docker 命令执行失败：{message or command}")
            return result.stdout

        return await asyncio.to_thread(run_command)

    async def _request(
        self,
        method: str,
        url: str,
        *,
        json: dict[str, Any] | None = None,
        **kwargs,
    ) -> dict[str, Any]:
        """统一网络请求：自动带鉴权、自动续期、自动抛异常"""
        if self._session is None:
            raise RuntimeError("请先用 DashboardClient.initialize() 初始化会话")

        token = await self._ensure_token()
        headers = {"Authorization": f"Bearer {token}"}

        async with self._session.request(
            method, url, headers=headers, json=json, **kwargs
        ) as resp:
            if resp.status == 401:
                # 401 说明 token 失效，强制刷新再试一次
                logger.info("Token 失效，尝试重新登录")
                token = await self._login()
                headers["Authorization"] = f"Bearer {token}"
                async with self._session.request(
                    method, url, headers=headers, json=json, **kwargs
                ) as resp2:
                    resp = resp2

            if resp.status != 200:
                raise RuntimeError(f"请求失败 [{resp.status}]: {await resp.text()}")

            body = await resp.json()
            if body.get("status") != "ok":
                raise RuntimeError(f"业务错误: {body.get('msg')}")
            return body.get("data")

    async def _ensure_token(self) -> str:
        """返回可用 token，必要时自动登录"""
        now = time.time()
        if (
            self._token is None
            or self._token_ts is None
            or now - self._token_ts > self.TOKEN_VALID_THRESHOLD
        ):
            self._token = await self._login()
            self._token_ts = now
        return self._token

    async def _login(self) -> str:
        """执行登录并返回新 token"""
        dbc = self.context.get_config()["dashboard"]
        payload = {"username": dbc["username"], "password": dbc["password"]}
        if self._session is None:
            raise RuntimeError("请先用 DashboardClient.initialize() 初始化会话")
        async with self._session.post(self.login_url, json=payload) as resp:
            if resp.status != 200:
                raise RuntimeError(f"登录失败 [{resp.status}]: {await resp.text()}")

            data = await resp.json()
            token = data.get("data", {}).get("token")
            if not token:
                raise RuntimeError(f"登录响应异常: {data}")
            logger.info("登录成功，Token 已更新")
            return token
