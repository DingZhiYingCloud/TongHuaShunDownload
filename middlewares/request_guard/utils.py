"""请求工具函数：真实 IP 提取 / UA / 来源 等"""
import ipaddress
import re


def get_client_ip(request, cfg):
    """获取客户端真实 IP。

    按 config.json 的 trusted_headers 顺序信任代理头（CDN/反代场景），
    无代理头时退回 REMOTE_ADDR。X-Forwarded-For 取最左侧第一个。
    """
    for header in cfg.get('trusted_headers', []):
        value = request.META.get(header)
        if value:
            first = str(value).split(',')[0].strip()
            if first:
                return first
    return request.META.get('REMOTE_ADDR', '') or ''


def get_request_headers(request, max_len=4096):
    """拼接请求中全部 HTTP 头为 'Name: value' 文本（供详情/调试）。"""
    parts = []
    for key, value in request.META.items():
        if key.startswith('HTTP_') and key != 'HTTP_COOKIE':
            name = key[5:].replace('_', '-').title()
            parts.append(f'{name}: {value}')
        elif key in ('CONTENT_TYPE', 'CONTENT_LENGTH'):
            parts.append(f'{key.replace("_", "-").title()}: {value}')
    text = '\n'.join(parts)
    return text[:max_len]


def truncate(text, limit):
    """将文本截断到 limit 字符（超出加省略号）。"""
    text = text or ''
    return text if len(text) <= limit else text[:limit] + '…'


_CIDR_RE = re.compile(r'^[0-9a-fA-F:./]+$')


def ip_in_network(ip, network):
    """判断 ip 是否属于 network(CIDR 或单 IP)。失败返回 False（不抛异常）。"""
    if not ip or not network:
        return False
    try:
        if '/' in network:
            return ipaddress.ip_address(ip) in ipaddress.ip_network(network, strict=False)
        return ip == network.strip()
    except ValueError:
        return False
