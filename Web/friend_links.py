"""小影 API 友情链接加载模块

用途: 在页面底部服务端渲染友情链接, 保证搜索引擎直接可见(绝不通过前端 API 请求)。

数据源: {XIAOYING_API_BASE}/api/seo/friend_links?status=true  (base 见 .env 的 XIAOYING_API_BASE)
缓存: 结果文件缓存 1 小时(降低小影 API 压力); 抓取/解析失败时返回空列表, 页面保持可访问。
"""
import requests
from django.conf import settings
from django.core.cache import cache

FRIEND_LINKS_CACHE_KEY = 'xiaoying_friend_links'
FRIEND_LINKS_CACHE_TTL = 60 * 60  # 1 小时


def _safe_url(url):
    """仅接受 http/https 链接, 且不含可注入 HTML 属性的字符(防属性注入)"""
    url = (url or '').strip()
    if not (url.startswith('http://') or url.startswith('https://')):
        return ''
    if any(c in url for c in ('"', "'", '<', '>')):
        return ''
    return url


def _parse_links(payload):
    """从接口返回中提取合法友情链接, 返回 [{name, url}, ...]"""
    links = []
    items = ((payload or {}).get('data') or {}).get('items') or []
    for item in items:
        name = str(item.get('name') or '').strip()
        url = _safe_url(str(item.get('url') or ''))
        if not name or not url or not item.get('status'):
            continue
        links.append({'name': name, 'url': url})
    return links


def fetch_friend_links():
    """获取友情链接(带 1 小时缓存), 失败或未配置 base 时返回 []"""
    cached = cache.get(FRIEND_LINKS_CACHE_KEY)
    if cached is not None:
        return cached
    links = []
    base = str(getattr(settings, 'XIAOYING_API_BASE', '') or '').strip()
    if base:
        try:
            resp = requests.get(
                base.rstrip('/') + '/api/seo/friend_links',
                params={'status': 'true'},
                headers={'User-Agent': 'Mozilla/5.0'},
                timeout=8,
            )
            links = _parse_links(resp.json())
        except Exception:
            links = []
    if links:
        cache.set(FRIEND_LINKS_CACHE_KEY, links, FRIEND_LINKS_CACHE_TTL)
    return links
