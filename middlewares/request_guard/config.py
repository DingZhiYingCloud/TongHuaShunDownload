"""request_guard 配置加载模块

设计约定：
- 所有行为均由中间件目录下的 config.json 控制（高灵活配置）。
- 启动时读取一次并缓存到内存，运行期修改需重启进程生效（仅启动读取）。
- config.json 缺字段时自动并入下方 DEFAULTS，保证健壮性。
"""
import json
import os
from pathlib import Path

# 包目录下的默认配置文件路径
CONFIG_PATH = Path(__file__).resolve().parent / 'config.json'

# 允许通过环境变量覆盖配置文件路径（便于多站点各自指定一份 config.json）
ENV_CONFIG_PATH = os.getenv('REQUEST_GUARD_CONFIG', None)

# 默认配置：config.json 缺失字段时以此兜底
DEFAULTS = {
    'enabled': True,
    'admin': {
        'path': 'request-guard',   # 后台访问路径前缀（不含首尾斜杠）
        'password': '123456',      # 后台登录密码（明文）
        'session_key': 'rg_admin_ok',
    },
    'trusted_headers': ['HTTP_X_FORWARDED_FOR', 'HTTP_X_REAL_IP', 'HTTP_CF_CONNECTING_IP'],
    'log': {
        'enabled': True,
        'exclude_paths': ['/static/', '/media/', '/favicon.ico', '/robots.txt', '/sitemap.xml'],
        'keep_days': 7,            # 自动清理：保留最近 N 天
        'max_rows': 500000,        # 自动清理：表总行数上限（双保险）
        'exclude_ips': [],         # 完全放行且不记录这些 IP（如自家运维 IP）
    },
    'rate_limit': {
        'enabled': False,          # 请求频控总开关（默认关闭，防止误伤）
        'per_ip_per_minute': 180,  # 单 IP 每分钟最大请求数
        'ban_minutes': 10,         # 超限后临时封禁时长（分钟）
    },
    'identity': {
        # 三形态差异化动作：spider=搜索引擎蜘蛛 / human_ref=带来源真人 / direct=无来源直连 / unknown=无法识别
        # 可选动作: pass(放行) | block(403) | disguise(显示伪装页)
        'spider': 'pass',
        'human_ref': 'pass',
        'direct': 'pass',
        'unknown': 'pass',
        'disguise_template': 'request_guard/cloak_default.html',  # 伪装页模板路径
    },
    'spider_keywords': {},         # 蜘蛛识别词库（文件里内置，运行时以文件为准）
    'rules': [],                   # 静态规则（与数据库规则合并，db 规则可在后台维护）
}

_CONFIG = None


def _deep_merge(base, override):
    """将 override 深合并进 base，返回合并后的字典（不修改入参）。"""
    out = dict(base)
    for key, val in (override or {}).items():
        if isinstance(val, dict) and isinstance(out.get(key), dict):
            out[key] = _deep_merge(out[key], val)
        else:
            out[key] = val
    return out


def load_config():
    """读取 config.json 并与 DEFAULTS 合并，返回最终配置字典。"""
    path = Path(ENV_CONFIG_PATH) if ENV_CONFIG_PATH else CONFIG_PATH
    file_cfg = {}
    if path.exists():
        try:
            file_cfg = json.loads(path.read_text(encoding='utf-8'))
        except Exception:
            file_cfg = {}
    return _deep_merge(DEFAULTS, file_cfg)


def get_config():
    """获取全局配置（进程内只读取一次）。"""
    global _CONFIG
    if _CONFIG is None:
        _CONFIG = load_config()
    return _CONFIG


def get_admin_path():
    """后台访问路径前缀，如 request-guard → /request-guard/"""
    cfg = get_config()
    return '/' + str(cfg.get('admin', {}).get('path', 'request-guard')).strip('/') + '/'
