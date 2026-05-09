
<div align="center">

![:name](https://count.getloli.com/@astrbot_plugin_restart?name=astrbot_plugin_restart&theme=minecraft&padding=6&offset=0&align=top&scale=1&pixelated=1&darkmode=auto)

# astrbot_plugin_restart

_✨ [astrbot](https://github.com/AstrBotDevs/AstrBot) 重启插件 ✨_  

[![License](https://img.shields.io/badge/License-MIT-green.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![AstrBot](https://img.shields.io/badge/AstrBot-3.4%2B-orange.svg)](https://github.com/Soulter/AstrBot)
[![GitHub](https://img.shields.io/badge/作者-Zhalslar-blue)](https://github.com/Zhalslar)

</div>

## 🤝 介绍

用命令重启、定时自动重启 AstrBot

## 📦 安装

- 可以直接在astrbot的插件市场搜索astrbot_plugin_restart，点击安装，耐心等待安装完成即可
- 若是安装失败，可以尝试直接克隆源码：

```bash
# 克隆仓库到插件目录
cd /AstrBot/data/plugins
git clone https://github.com/Zhalslar/astrbot_plugin_restart

# 控制台重启AstrBot
```

## ⌨️ 使用说明

### 重启方式

插件固定使用 SSH 方式：通过 SSH 登录宿主机，并执行：

```bash
docker restart astrbot napcat
```

如果已安装并配置 `astrbot_plugin_ssh`，本插件会在自身 SSH 配置留空时复用它的 `host`、`port`、`username`、`password`、`private_key`、`timeout` 与 `known_hosts_path`。宿主机 Docker 需要 sudo 权限时，请开启 `ssh_use_sudo`，实际命令会变为：

```bash
sudo docker restart astrbot napcat
```

该方式适合 AstrBot 运行在 Docker 容器内的场景，避免容器内缺少 Docker CLI 或 Docker socket 导致重启失败。

### 命令表

|     命令      |                    说明                    |
|:-------------:|:-----------------------------------------------:|
| 重启   | 通过 SSH 在宿主机重启 AstrBot/napcat 容器  |
| 定时重启 开/关   | 开启或关闭按 Cron 表达式定时重启  |
| 资源占用   | 查看当前系统 CPU、内存、磁盘占用，并通过 SSH 获取 Docker 容器资源占用  |
| 重载 <插件名\|序号\|all>   | 重载指定插件或全部插件  |

### 示例图

## 👥 贡献指南

- 🌟 Star 这个项目！（点右上角的星星，感谢支持！）
- 🐛 提交 Issue 报告问题
- 💡 提出新功能建议
- 🔧 提交 Pull Request 改进代码

## 📌 注意事项

- 想第一时间得到反馈的可以来作者的插件反馈群（QQ群）：460973561（不点star不给进）
