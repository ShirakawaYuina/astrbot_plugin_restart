from pathlib import Path

import psutil


def cron_to_human(cron: str) -> str:
    """
    将 5 段 cron（分 时 日 月 周）转换为中文易读描述
    """
    parts = cron.strip().split()
    if len(parts) != 5:
        raise ValueError("Cron 表达式必须是 5 段（分 时 日 月 周）")

    minute, hour, day, month, week = parts

    def parse_field(val, unit, names=None):
        if val == "*":
            return f"每{unit}"
        if val.startswith("*/"):
            return f"每{val[2:]}{unit}"
        if "," in val:
            items = val.split(",")
            return "、".join(
                names.get(i, f"{i}{unit}") if names else f"{i}{unit}" for i in items
            )
        if "-" in val:
            start, end = val.split("-")
            if names:
                return f"{names[start]}至{names[end]}"
            return f"{start}到{end}{unit}"
        return names.get(val, f"{val}{unit}") if names else f"{val}{unit}"

    week_names = {
        "0": "周日",
        "1": "周一",
        "2": "周二",
        "3": "周三",
        "4": "周四",
        "5": "周五",
        "6": "周六",
    }

    desc = []

    # 周
    if week != "*":
        desc.append(parse_field(week, "", week_names))

    # 月
    if month != "*":
        desc.append(parse_field(month, "月"))

    # 日
    if day != "*":
        desc.append(parse_field(day, "日"))
    elif week == "*":
        desc.append("每天")

    # 时间
    if hour == "*" and minute == "*":
        desc.append("每分钟")
    else:
        time_desc = []
        if hour != "*":
            time_desc.append(parse_field(hour, "点"))
        if minute != "*":
            time_desc.append(parse_field(minute, "分"))
        desc.append(" ".join(time_desc))

    return " ".join(desc)


def get_memory_info(decimal_places=1):
    """
    获取当前设备内存情况，支持自定义小数位数

    Args:
        decimal_places (int): 小数位数，默认为1位

    Returns:
        str: 已用内存/总内存(百分比) 格式，如 "8.5GB/16.0GB(53.2%)"
    """
    # 获取内存信息
    memory = psutil.virtual_memory()

    # 计算已用内存 (总内存 - 可用内存)
    total_memory = memory.total
    used_memory = total_memory - memory.available

    # 转换为GB单位
    total_gb = total_memory / (1024**3)
    used_gb = used_memory / (1024**3)

    # 计算使用百分比
    usage_percent = (used_memory / total_memory) * 100

    # 格式化输出，使用指定的小数位数
    format_str = f"{{:.{decimal_places}f}}GB/{{:.{decimal_places}f}}GB({{:.1f}}%)"
    return format_str.format(used_gb, total_gb, usage_percent)


def format_docker_stats_output(raw_output: str) -> str:
    """
    规范化 docker stats 命令输出，便于直接在聊天消息中展示。

    业务意图：
    - 只保留最有价值的容器资源列，减少聊天输出噪音；
    - 对每一列进行左对齐，保证聊天端的等宽展示可读；
    - 去除首尾空白行，减少消息噪音；
    - 在 docker 无返回内容时提供明确兜底文案。
    """
    lines = [line.rstrip() for line in raw_output.splitlines() if line.strip()]
    if not lines:
        return "未获取到 Docker 资源数据"

    headers = ["NAME", "CPU %", "MEM USAGE / LIMIT", "MEM %"]

    def split_columns(line: str) -> list[str]:
        return [part for part in line.split("  ") if part.strip()]

    parsed_rows: list[dict[str, str]] = []
    header_index_map: dict[str, int] | None = None

    for raw_line in lines:
        columns = split_columns(raw_line)
        if not columns:
            continue
        if header_index_map is None:
            normalized_headers = [column.strip() for column in columns]
            header_index_map = {
                header: idx
                for idx, header in enumerate(normalized_headers)
                if header in headers
            }
            continue

        row = {}
        for header in headers:
            idx = header_index_map.get(header)
            row[header] = (
                columns[idx].strip() if idx is not None and idx < len(columns) else ""
            )
        if any(row.values()):
            parsed_rows.append(row)

    if header_index_map is None or not parsed_rows:
        return "未获取到 Docker 资源数据"

    widths = {
        header: max(len(header), *(len(row[header]) for row in parsed_rows))
        for header in headers
    }

    def format_row(row: dict[str, str]) -> str:
        return "  ".join(row[header].ljust(widths[header]) for header in headers)

    output_lines = [
        "  ".join(header.ljust(widths[header]) for header in headers),
    ]
    output_lines.extend(format_row(row) for row in parsed_rows)
    return "\n".join(output_lines)


def build_resource_usage_message(
    system_info: str,
    docker_stats: str | None = None,
    docker_error: str | None = None,
) -> str:
    """
    组合“资源占用”命令的完整回显。

    业务意图：
    - 系统资源始终优先展示，避免 Docker/SSH 异常掩盖本机状态；
    - Docker 容器资源单独成段，直接展示 docker stats --no-stream 的表格输出；
    - Docker 获取失败时保留失败原因，方便定位 SSH、权限或 Docker 守护进程问题。
    """
    message = f"系统资源占用：\n{system_info}"
    if docker_error:
        return f"{message}\n\nDocker 容器资源占用：获取失败（{docker_error}）"
    return f"{message}\n\nDocker 容器资源占用：\n{docker_stats or '未获取到 Docker 资源数据'}"


def _format_gib(used_bytes: int, total_bytes: int, decimal_places: int = 1) -> str:
    """统一的字节转 GB 格式化，保证各资源字段显示一致。"""
    used_gb = used_bytes / (1024**3)
    total_gb = total_bytes / (1024**3)
    usage_percent = (used_bytes / total_bytes) * 100 if total_bytes else 0
    format_str = f"{{:.{decimal_places}f}}GB/{{:.{decimal_places}f}}GB({{:.1f}}%)"
    return format_str.format(used_gb, total_gb, usage_percent)


def get_system_resource_info(decimal_places: int = 1) -> str:
    """
    获取系统 CPU、内存、磁盘占用，供“资源占用”命令直接回显。

    边界条件说明：
    - 磁盘统计使用当前工作目录所在盘符，兼容 Windows 与 Linux；
    - CPU 采样使用短间隔，避免瞬时值为 0 的可读性问题。
    """
    cpu_usage = psutil.cpu_percent(interval=0.2)

    memory = psutil.virtual_memory()
    memory_used = memory.total - memory.available
    memory_text = _format_gib(memory_used, memory.total, decimal_places)

    current_path = Path.cwd()
    disk_root = current_path.anchor or str(current_path)
    disk = psutil.disk_usage(disk_root)
    disk_text = _format_gib(disk.used, disk.total, decimal_places)

    return f"CPU：{cpu_usage:.1f}%\n内存：{memory_text}\n磁盘：{disk_text}"
