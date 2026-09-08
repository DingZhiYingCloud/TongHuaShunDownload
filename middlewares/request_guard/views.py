"""request_guard 管理后台视图

页面: 登录 / 概览 / 请求日志 / 日志详情 / 规则管理
接口: 新增规则 / 启停规则 / 删除规则 / 快速封禁IP / 解除频控封禁
鉴权: 会话(session)标记 + config.json 明文密码比对
"""
import datetime
from urllib.parse import urlencode

from django.db.models import Count
from django.http import HttpResponseBadRequest, HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST, require_http_methods

from .config import get_config
from .models import BlockRule, RequestLog
from .rate import limiter
from .rules import is_rule_active

# 后台会话标记
IDENTITY_LABELS = {
    'spider': '蜘蛛',
    'human_ref': '来源访问',
    'direct': '直连',
    'unknown': '未知',
}
ACTION_LABELS = {
    'pass': '放行',
    'block': '拦截403',
    'disguise': '伪装页',
    'redirect': '302跳转',
    'log': '仅记录',
}
PAGE_SIZE = 20


def _auth_ok(request):
    """是否已通过后台密码验证"""
    cfg = get_config()
    return bool(request.session.get(cfg['admin']['session_key']))


def _require_login(view):
    """登录校验装饰器：未登录跳转到登录页"""
    from functools import wraps

    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if not _auth_ok(request):
            return redirect('rg_login')
        return view(request, *args, **kwargs)
    return wrapper


def _start_of_today():
    """本地时区(Asia/Shanghai)的今日零点(aware)"""
    now = timezone.localtime()
    return now.replace(hour=0, minute=0, second=0, microsecond=0)


def _decorate_rows(rows):
    """为日志对象附加 identity_label / action_label，供模板直接展示。"""
    for row in rows:
        row.identity_label = IDENTITY_LABELS.get(row.identity, row.identity)
        row.action_label = ACTION_LABELS.get(row.action, row.action)
    return rows


# ------------------------------------------------------------------ #
# 登录 / 登出
# ------------------------------------------------------------------ #
@require_http_methods(['GET', 'POST'])
def login(request):
    cfg = get_config()
    if _auth_ok(request):
        return redirect('rg_index')
    error = ''
    if request.method == 'POST':
        password = (request.POST.get('password') or '').strip()
        if password and password == cfg['admin']['password']:
            request.session[cfg['admin']['session_key']] = True
            next_url = request.POST.get('next') or ''
            return redirect(next_url if next_url.startswith('/') and not next_url.startswith('//') else 'rg_index')
        error = '密码不正确，请重试'
    return render(request, 'request_guard/login.html', {'error': error, 'page_title': '登录'})


@require_POST
def logout(request):
    for key in list(request.session.keys()):
        if key.startswith('rg_'):
            del request.session[key]
    return redirect('rg_login')


# ------------------------------------------------------------------ #
# 概览
# ------------------------------------------------------------------ #
@_require_login
def index(request):
    today = _start_of_today()
    qs = RequestLog.objects.filter(ts__gte=today)

    top_ips = list(
        qs.values('ip').annotate(total=Count('id')).order_by('-total')[:8]
    )
    top_spiders = list(
        qs.filter(identity='spider').values('spider').annotate(total=Count('id')).order_by('-total')[:8]
    )
    recent = list(RequestLog.objects.all()[:10])
    _decorate_rows(recent)

    ctx = {
        'page_title': '概览',
        'cfg': get_config(),
        'today_total': qs.count(),
        'today_blocked': qs.exclude(action__in=('pass', 'log')).count(),
        'today_spider': qs.filter(identity='spider').count(),
        'rules_total': BlockRule.objects.filter(enabled=True).count(),
        'freq_bans': limiter.banned_snapshot(),
        'top_ips': top_ips,
        'top_spiders': top_spiders,
        'recent': recent,
    }
    return render(request, 'request_guard/index.html', ctx)


# ------------------------------------------------------------------ #
# 请求日志
# ------------------------------------------------------------------ #
@_require_login
def logs(request):
    qs = RequestLog.objects.all()
    # 筛选条件
    ip = (request.GET.get('ip') or '').strip()
    identity = (request.GET.get('identity') or '').strip()
    action = (request.GET.get('action') or '').strip()
    handled = request.GET.get('handled')  # on=只看被处置
    if ip:
        qs = qs.filter(ip__icontains=ip)
    if identity:
        qs = qs.filter(identity=identity)
    if action:
        qs = qs.filter(action=action)
    if handled == 'on':
        qs = qs.exclude(action__in=('pass', 'log'))

    # 分页
    page = max(1, int(request.GET.get('page') or 1))
    total = qs.count()
    total_pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
    page = min(page, total_pages)
    items = list(qs[(page - 1) * PAGE_SIZE: page * PAGE_SIZE])
    _decorate_rows(items)

    # 保留筛选参数构造分页链接
    def page_url(p):
        params = {'page': p}
        for name, val in (('ip', ip), ('identity', identity), ('action', action)):
            if val:
                params[name] = val
        if handled == 'on':
            params['handled'] = 'on'
        return '?' + urlencode(params)

    # 页码窗口（当前页前后各 5 页），模板直接用 (页码, 链接) 元组
    window = list(range(max(1, page - 5), min(total_pages, page + 5) + 1))
    page_links = [(p, page_url(p)) for p in window]

    ctx = {
        'page_title': '请求日志',
        'items': items,
        'page': page,
        'total': total,
        'total_pages': total_pages,
        'page_links': page_links,
        'prev_url': page_url(page - 1) if page > 1 else '',
        'next_url': page_url(page + 1) if page < total_pages else '',
        'filters': {'ip': ip, 'identity': identity, 'action': action, 'handled': handled},
    }
    return render(request, 'request_guard/logs.html', ctx)


@_require_login
def log_detail(request, log_id):
    log = get_object_or_404(RequestLog, pk=log_id)
    _decorate_rows([log])
    return render(request, 'request_guard/log_detail.html', {
        'page_title': '日志详情',
        'log': log,
    })


# ------------------------------------------------------------------ #
# 规则管理
# ------------------------------------------------------------------ #
@_require_login
def rules(request):
    all_rules = list(BlockRule.objects.all())
    active_ids = {r.pk for r in all_rules if is_rule_active(r)}
    return render(request, 'request_guard/rules.html', {
        'page_title': '规则管理',
        'rules': all_rules,
        'active_ids': active_ids,
        'kind_choices': BlockRule.KIND_CHOICES,
        'match_choices': BlockRule.MATCH_CHOICES,
        'action_choices': BlockRule.ACTION_CHOICES,
    })


def _parse_expires(value):
    """解析 datetime-local 输入为 aware 时间；留空返回 None。"""
    value = (value or '').strip()
    if not value:
        return None
    try:
        naive = datetime.datetime.strptime(value, '%Y-%m-%dT%H:%M')
        return timezone.make_aware(naive)
    except (ValueError, OverflowError):
        raise ValueError('过期时间格式应为 YYYY-MM-DDTHH:MM')


def _rule_form_error(request):
    """解析规则新增表单，返回 (rule, error)。"""
    kind = (request.POST.get('kind') or '').strip()
    match_type = (request.POST.get('match_type') or 'contains').strip()
    value = (request.POST.get('value') or '').strip()
    action = (request.POST.get('action') or 'block').strip()
    redirect_url = (request.POST.get('redirect_url') or '').strip()
    note = (request.POST.get('note') or '').strip()
    enabled = request.POST.get('enabled') == '1'

    valid_kinds = {c[0] for c in BlockRule.KIND_CHOICES}
    valid_actions = {c[0] for c in BlockRule.ACTION_CHOICES}
    if kind not in valid_kinds:
        return None, '匹配对象不合法'
    if action not in valid_actions:
        return None, '动作不合法'
    if not value:
        return None, '匹配值不能为空'
    if action == 'redirect' and not redirect_url:
        return None, '302跳转动作必须填写跳转地址'

    expires_at = None
    try:
        expires_at = _parse_expires(request.POST.get('expires_at'))
    except ValueError as exc:
        return None, str(exc)

    return BlockRule(kind=kind, match_type=match_type, value=value, action=action,
                     redirect_url=redirect_url, note=note, enabled=enabled,
                     expires_at=expires_at), None


@require_POST
def rule_add(request):
    rule, error = _rule_form_error(request)
    if error:
        return HttpResponseBadRequest(error)
    rule.save()
    return redirect('rg_rules')


@require_POST
def rule_toggle(request, rule_id):
    rule = get_object_or_404(BlockRule, pk=rule_id)
    rule.enabled = not rule.enabled
    rule.save(update_fields=['enabled'])
    return redirect('rg_rules')


@require_POST
def rule_delete(request, rule_id):
    rule = get_object_or_404(BlockRule, pk=rule_id)
    rule.delete()
    return redirect('rg_rules')


@require_POST
def quick_block_ip(request):
    """从日志页快速封禁某个 IP（永久 403）"""
    ip = (request.POST.get('ip') or '').strip()
    if not ip:
        return HttpResponseBadRequest('缺少 IP')
    # 若已存在相同规则则不重复添加
    existed = BlockRule.objects.filter(kind='ip', match_type='equal', value=ip, action='block').exists()
    if not existed:
        BlockRule.objects.create(kind='ip', match_type='equal', value=ip,
                                 action='block', note='日志页快速封禁')
    back = request.POST.get('back') or ''
    if back and back.startswith('/') and not back.startswith('//'):
        return HttpResponseRedirect(back)
    return redirect('rg_rules')


@require_POST
def unban_ip(request):
    """解除频控在内存中的临时封禁"""
    ip = (request.POST.get('ip') or '').strip()
    if ip:
        limiter.unban(ip)
    return redirect('rg_index')
