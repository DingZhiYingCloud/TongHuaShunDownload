# 项目URL配置
from django.shortcuts import render
from django.http import HttpResponse
from django.core.cache import cache
from django.conf import settings
import requests


# 同花顺远航版落地页动态文案(版本号/更新日志/详情链接)来源接口
VERSION_API_URL = 'https://ai.10jqka.com.cn/java-extended-api/voyageversion/getDefaultVersionInfo?reset=true'
VERSION_CACHE_KEY = 'ths_xb_version_info'
# 缓存时长(秒): 由 .env 的 CACHE_TTL_HOURS 控制, 默认 2 小时
VERSION_CACHE_TTL = int(settings.CACHE_TTL_HOURS * 3600)


def _fetch_version_info():
    """获取版本号/更新日志/详情链接(文件缓存), 失败返回空 dict"""
    cached = cache.get(VERSION_CACHE_KEY)
    if cached is not None:
        return cached
    try:
        resp = requests.get(VERSION_API_URL, timeout=8, headers={'User-Agent': 'Mozilla/5.0'})
        data = (resp.json() or {}).get('data') or {}
        info = {
            'version': 'Ver ' + str(data.get('version') or ''),
            'readme': str(data.get('description') or '').strip(),
            'detail_link': str(data.get('introductionLink') or ''),
        }
    except Exception:
        info = {}
    if info:
        cache.set(VERSION_CACHE_KEY, info, VERSION_CACHE_TTL)
    return info


def index(request):
    """首页: 同花顺远航版落地页克隆版; 版本/更新日志后端注入, 抓取失败时降级为空数据, 保证页面可访问"""
    try:
        data = _fetch_version_info()
    except Exception:
        data = {}
    return render(request, 'index.html', data)


def error_404(request, exception=None):
    """404 错误页：访问不存在的路径或文件时返回（DEBUG=False 时生效）"""
    return render(request, '404.html', status=404)


def error_500(request, exception=None):
    """500 错误页：服务器内部错误时返回（DEBUG=False 时生效）"""
    return render(request, '500.html', status=500)


# ============ Sitemap（站点地图） ============
# 站点内容由爬虫实时获取，因此 sitemap 分为两部分：
#   1. 静态固定 URL：单（与 index.html 硬编码xxxx保持一致，改动需同步）
#   2. 动态 URL：调用爬虫抓取首页，提取xxxx生成详情页链接（爬虫失败时自动降级为仅静态 URL）
# 生成结果缓存 6 小时，避免每次请求 sitemap 都触发源站爬虫。
SITEMAP_STATIC_URLS = [
]
SITEMAP_CACHE_KEY = 'sitemap_urls'
SITEMAP_CACHE_TTL = 60 * 60 * 6  # 6 小时


def sitemap(request):
    """sitemap.xml：静态 URL + 爬虫实时xxxx详情 URL，缓存 6 小时"""

    return HttpResponse('\n', content_type='application/xml')
