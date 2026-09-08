"""request_guard 请求守卫主中间件

处理流程（按优先级）：
    1. 解析真实 IP / UA / 来源 / 路径
    2. 识别身份形态：spider / human_ref / direct / unknown
    3. 命中数据库处置规则(BlockRule) → 执行动作
    4. 请求频控(可选，config 开启)
    5. 身份差异化策略(config identity 配置，默认全部 pass)
    6. 动作执行：pass / block(403) / disguise(伪装页) / redirect(302)
    7. 写请求日志（自动按天+条数上限清理）

豁免规则：
- 后台自身路径(admin path)完全跳过（不记录、不拦截）
- 静态/媒体等路径默认只记录异常处置，不记录普通日志（config log.exclude_paths）
- log.exclude_ips 中的 IP 完全放行且不记录
"""
import logging
import time
from datetime import timedelta

from django.db.models import F
from django.http import HttpResponse, HttpResponseForbidden, HttpResponseRedirect
from django.template.loader import render_to_string
from django.utils import timezone

from . import identify
from .config import get_admin_path, get_config
from .models import BlockRule, RequestLog
from .rate import limiter
from .rules import is_rule_active, rule_matches
from .utils import get_client_ip, truncate

logger = logging.getLogger('request_guard')

# 手动清理间隔（秒）
_CLEANUP_INTERVAL = 3600


class RequestGuardMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        self.cfg = get_config()
        self.admin_path = get_admin_path()
        self._last_cleanup = 0.0

    def __call__(self, request):
        cfg = self.cfg

        # 1) 未启用或后台自身路径：完全放行
        if not cfg.get('enabled') or request.path.startswith(self.admin_path):
            return self.get_response(request)

        # 2) 提取请求基础信息
        ip = get_client_ip(request, cfg)
        ua = request.META.get('HTTP_USER_AGENT', '') or ''
        referer = request.META.get('HTTP_REFERER', '') or ''
        path = request.get_full_path() or '/'
        # 路径(不含查询串)与查询串分开存，便于规则匹配 path
        clean_path = request.path or '/'
        query = request.META.get('QUERY_STRING', '') or ''

        # 免记录白名单 IP：完全放行
        if ip in cfg.get('log', {}).get('exclude_ips', []):
            return self.get_response(request)

        # 3) 身份识别
        identity, spider = identify.classify(ua, referer, cfg.get('spider_keywords', {}))

        # 4) 依次判定处置动作
        action, reason = self._match_rules(cfg, ip, ua, referer, clean_path)
        if action is None:
            action, reason = self._check_rate_limit(cfg, ip)
        if action is None:
            action, reason = self._identity_policy(cfg, identity)
        action = action or 'pass'

        # 5) 执行动作
        t0 = time.perf_counter()
        response = None
        if action == 'block':
            response = HttpResponseForbidden('403 Forbidden', status=403)
        elif action == 'disguise':
            response = self._make_disguise(cfg)
        elif action == 'redirect':
            url = self._pick_redirect_url(reason)
            response = HttpResponseRedirect(url or '/')
        else:
            # pass / log：正常进入业务视图
            response = self.get_response(request)
        duration_ms = int((time.perf_counter() - t0) * 1000)

        # 6) 写日志（拦截/处置类动作即使路径被排除也记录）
        self._maybe_log(cfg, request, ip, ua, referer, clean_path, query,
                        identity, spider, action, reason, response, duration_ms)
        return response

    # ------------------------------------------------------------------ #
    # 判定
    # ------------------------------------------------------------------ #
    def _match_rules(self, cfg, ip, ua, referer, path):
        """命中启用规则时返回 (action, reason)，否则 (None, '')。"""
        try:
            rules = BlockRule.objects.filter(enabled=True)
        except Exception:
            # 数据库未迁移等情况：按无规则放行，避免影响全站
            logger.warning('读取 BlockRule 失败，本次按无规则放行')
            return None, ''
        for rule in rules:
            if not is_rule_active(rule):
                continue
            if rule_matches(rule, ip, ua, referer, path):
                # 命中计数
                BlockRule.objects.filter(pk=rule.pk).update(hit_count=F('hit_count') + 1)
                note = f'rule#{rule.pk}:{rule.note or rule.get_kind_display()}'
                return rule.action, note
        return None, ''

    def _check_rate_limit(self, cfg, ip):
        """频控判定：开启且超限则临时封禁。"""
        rate_cfg = cfg.get('rate_limit', {})
        if rate_cfg.get('enabled'):
            if limiter.is_banned(ip):
                return 'block', 'rate_limit: 临时封禁中'
            per_minute = int(rate_cfg.get('per_ip_per_minute', 180))
            if limiter.check_and_hit(ip, per_minute):
                ban_minutes = int(rate_cfg.get('ban_minutes', 10))
                limiter.ban_until(ip, ban_minutes)
                return 'block', f'rate_limit: 超{per_minute}/分钟'
        return None, ''

    def _identity_policy(self, cfg, identity):
        """身份差异化策略（spider/human_ref/direct/unknown 的动作）。"""
        policy = cfg.get('identity', {}).get(identity, 'pass')
        if policy in ('block', 'disguise'):
            return policy, f'identity:{identity}'
        return None, ''

    # ------------------------------------------------------------------ #
    # 动作
    # ------------------------------------------------------------------ #
    def _make_disguise(self, cfg):
        """渲染伪装页；模板缺失时回退 403，保证不抛 500。"""
        template = cfg.get('identity', {}).get('disguise_template', '')
        try:
            html = render_to_string(template, {})
            return HttpResponse(html, status=200)
        except Exception:
            logger.exception('伪装页模板渲染失败: %s', template)
            return HttpResponseForbidden('403 Forbidden', status=403)

    def _pick_redirect_url(self, reason):
        """规则 redirect 动作的跳转地址。

        因 reason 形如 'rule#{pk}:xxx'，从规则表按 pk 兜底查询跳转地址。
        """
        try:
            pk = int(reason.split('#')[1].split(':')[0])
            rule = BlockRule.objects.filter(pk=pk).only('redirect_url').first()
            if rule and rule.redirect_url:
                return rule.redirect_url
        except Exception:
            pass
        return '/'

    # ------------------------------------------------------------------ #
    # 日志
    # ------------------------------------------------------------------ #
    def _maybe_log(self, cfg, request, ip, ua, referer, path, query,
                   identity, spider, action, reason, response, duration_ms):
        log_cfg = cfg.get('log', {})
        if not log_cfg.get('enabled'):
            return
        # 处置类动作(拦截/伪装/跳转)必然记录；普通请求按 exclude_paths 排除
        if action in ('pass', 'log') and self._is_excluded_path(log_cfg, path):
            return
        try:
            RequestLog.objects.create(
                ip=truncate(ip, 64),
                ua=truncate(ua, 4000),
                referer=truncate(referer, 2000),
                method=request.method,
                path=truncate(path, 2000),
                query=truncate(query, 1000),
                status=response.status_code if response else 0,
                duration_ms=duration_ms,
                identity=identity,
                spider=spider,
                action=action,
                reason=truncate(reason, 64),
            )
            self._maybe_cleanup(log_cfg)
        except Exception:
            logger.exception('写请求日志失败')

    def _is_excluded_path(self, log_cfg, path):
        for ex in log_cfg.get('exclude_paths', []):
            ex = str(ex)
            if ex.endswith('/') and path.startswith(ex):
                return True
            if path == ex:
                return True
        return False

    def _maybe_cleanup(self, log_cfg):
        """每小时清理一次：按天数 + 条数上限双保险。"""
        now = time.time()
        if now - self._last_cleanup < _CLEANUP_INTERVAL:
            return
        self._last_cleanup = now
        try:
            keep_days = int(log_cfg.get('keep_days', 7))
            if keep_days > 0:
                cutoff = timezone.now() - timedelta(days=keep_days)
                RequestLog.objects.filter(ts__lt=cutoff).delete()
            max_rows = int(log_cfg.get('max_rows', 0))
            if max_rows > 0:
                # 找到需要保留的最新一条 id，删除比它旧的记录
                keep_id = RequestLog.objects.order_by('-id').values_list('id', flat=True)[max_rows - 1:max_rows]
                keep_id = list(keep_id)
                if keep_id:
                    RequestLog.objects.filter(id__lt=keep_id[0]).delete()
        except Exception:
            logger.exception('日志自动清理失败')
