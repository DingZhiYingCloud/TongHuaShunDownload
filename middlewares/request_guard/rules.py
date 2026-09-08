"""规则匹配引擎：判断单条 BlockRule 是否命中当前请求"""
import re

from django.utils import timezone

from .utils import ip_in_network

# 预编译正则缓存，避免每条请求重复 compile
_REGEX_CACHE = {}


def _compiled(pattern):
    rx = _REGEX_CACHE.get(pattern)
    if rx is None:
        try:
            rx = re.compile(pattern, re.IGNORECASE)
        except re.error:
            rx = None
        _REGEX_CACHE[pattern] = rx
    return rx


def rule_matches(rule, ip, ua, referer, path):
    """判断规则是否命中。

    匹配对象(kind)与取值源对应：ip / ua / referer / path
    :return: True=命中
    """
    kind = rule.kind
    value = (rule.value or '').strip()
    if not value:
        return False

    # 取值源（UA/来源/路径不区分大小写比对）
    if kind == 'ip':
        source = ip or ''
    elif kind == 'ua':
        source = (ua or '').lower()
        value = value.lower()
    elif kind == 'referer':
        source = (referer or '').lower()
        value = value.lower()
    elif kind == 'path':
        source = path or ''
    else:
        return False

    match_type = rule.match_type

    # IP 特殊：支持 CIDR 段匹配
    if kind == 'ip' and match_type == 'cidr':
        return ip_in_network(ip, value)
    if match_type == 'equal':
        return source == value
    if match_type == 'startswith':
        return source.startswith(value)
    if match_type == 'regex':
        rx = _compiled(value)
        return bool(rx and rx.search(source))
    # 默认 contains
    return value in source


def is_rule_active(rule, now=None):
    """规则当前是否有效（启用且未过期）。"""
    if not rule.enabled:
        return False
    if not rule.expires_at:
        return True
    now = now or timezone.now()
    expires = rule.expires_at
    if timezone.is_naive(expires):
        expires = timezone.make_aware(expires)
    return expires > now
