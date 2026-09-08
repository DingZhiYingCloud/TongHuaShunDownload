"""外链替换中间件: 每次访问把页面中指向外站(非本站)的 <a> 链接随机替换为小影 API 友情链接

设计约定:
- 数据源: 复用 Web/friend_links.py 的 fetch_friend_links()(列表缓存 1 小时, 不重复请求小影 API)
- 开关: .env 的 FRIEND_LINK_REPLACE(on/off), 每次请求实时读取文件, 修改后立即生效无需重启
- 处理范围: 仅 200 且 Content-Type 含 text/html 的响应; 不影响 json/静态/错误页等
- 替换规则:
  1. 仅处理 <a> 标签; 相对链接/锚点(#)不处理
  2. href 指向本站域名(按请求 Host 自动识别)的不处理
  3. 每条外链独立随机挑一条友情链接; href/title/纯文本锚文本同步替换(含子标签的链接只换 href+title)
- 安全: url/name 均经 html.escape 后写入属性/文本, 防属性注入
"""
import random
import re

from django.conf import settings
from django.utils.html import escape
from dotenv import dotenv_values

from .friend_links import fetch_friend_links

# 完整 <a>...</a> 标签
_A_TAG_RE = re.compile(r'<a\b[^>]*>.*?</a>', re.IGNORECASE | re.DOTALL)
# 打开标签 <a ...> 部分
_A_OPEN_RE = re.compile(r'<a\b[^>]*>', re.IGNORECASE)
# 属性提取
_HREF_RE = re.compile(r'\bhref\s*=\s*(["\'])(.*?)\1', re.IGNORECASE)
_TITLE_RE = re.compile(r'\btitle\s*=\s*(["\'])(.*?)\1', re.IGNORECASE)

_ON_VALUES = ('on', 'true', '1', 'yes')


def _is_enabled():
    """开关: 每次请求实时读取 .env(不缓存), 改文件立即生效"""
    try:
        val = (dotenv_values(settings.BASE_DIR / '.env') or {}).get('FRIEND_LINK_REPLACE', 'off')
    except Exception:
        val = 'off'
    return str(val).strip().lower() in _ON_VALUES


def _is_external(href):
    """是否 http(s)/协议相对(//)的绝对外链"""
    h = href.strip().lower()
    return h.startswith('http://') or h.startswith('https://') or h.startswith('//')


def _link_host(href):
    """提取 href 的主机名(小写), 失败返回空串"""
    h = href.strip()
    if h.startswith('//'):
        netloc = h[2:]
    else:
        m = re.match(r'^https?://([^/?#]+)', h, re.IGNORECASE)
        if not m:
            return ''
        netloc = m.group(1)
    if '@' in netloc:  # 去掉 userinfo
        netloc = netloc.rsplit('@', 1)[1]
    return netloc.split(':')[0].split('?')[0].lower()


def _replace_links_in_html(html, links, own_host):
    """把 html 中所有指向外站的 <a> 链接随机替换为友情链接"""
    if not html or not links:
        return html

    def _process(match):
        a_full = match.group(0)
        open_m = _A_OPEN_RE.search(a_full)
        if not open_m:
            return a_full
        open_tag = open_m.group(0)

        href_m = _HREF_RE.search(open_tag)
        if not href_m:
            return a_full
        raw_href = href_m.group(2)
        if not _is_external(raw_href):
            return a_full  # 相对链接/锚点
        if _link_host(raw_href) == own_host:
            return a_full  # 本站链接

        link = random.choice(links)
        url, name = link['url'], link['name']

        # 1) 替换 href 属性(Django escape 已转义引号, 安全用于双引号属性)
        href_attr = 'href="' + escape(url) + '"'
        new_open = open_tag[:href_m.start()] + href_attr + open_tag[href_m.end():]

        # 2) title 已有则替换, 无则插入(名称转义防注入)
        title_attr = 'title="' + escape(name) + '"'
        title_m = _TITLE_RE.search(new_open)
        if title_m:
            new_open = new_open[:title_m.start()] + title_attr + new_open[title_m.end():]
        else:
            new_open = new_open[:-1] + ' ' + title_attr + new_open[-1:]

        # 3) 纯文本锚文本替换为网站名(含子标签的链接仅换 href+title)
        body = a_full[len(open_tag):-len('</a>')]
        if body.strip() and '<' not in body:
            body = escape(name)
        return new_open + body + '</a>'

    return _A_TAG_RE.sub(_process, html)


class FriendLinkReplaceMiddleware:
    """把每个 HTML 响应里的外部链接替换为友情链接(服务端输出, SEO 直接可见)"""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if not _is_enabled():
            return response
        if response.status_code != 200:
            return response
        content_type = (response.get('Content-Type') or '').lower()
        if 'text/html' not in content_type:
            return response

        links = fetch_friend_links()
        if not links:
            return response
        try:
            html = response.content.decode('utf-8', errors='replace')
        except Exception:
            return response
        own_host = request.get_host().split(':')[0].lower()
        new_html = _replace_links_in_html(html, links, own_host)
        if new_html == html:
            return response

        response.content = new_html.encode('utf-8')
        if response.has_header('Content-Length'):
            del response['Content-Length']
        return response
