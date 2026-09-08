"""request_guard 数据模型（Django ORM + SQLite）"""
from django.db import models


class RequestLog(models.Model):
    """每一条请求的详细信息"""

    class Meta:
        verbose_name = '请求日志'
        verbose_name_plural = verbose_name
        ordering = ['-ts']
        indexes = [
            models.Index(fields=['-ts']),
            models.Index(fields=['ip', '-ts']),
        ]

    # 基础请求信息
    ts = models.DateTimeField('时间', auto_now_add=True, db_index=True)
    ip = models.CharField('IP', max_length=64, db_index=True)
    ua = models.TextField('User-Agent', blank=True, default='')
    referer = models.TextField('来源 Referer', blank=True, default='')
    method = models.CharField('Method', max_length=12, blank=True, default='')
    path = models.TextField('路径', blank=True, default='')
    query = models.TextField('查询串', blank=True, default='')

    # 请求结果
    status = models.PositiveSmallIntegerField('状态码', default=200)
    duration_ms = models.PositiveIntegerField('耗时(ms)', default=0)

    # 识别与处置结果
    identity = models.CharField('身份形态', max_length=16, default='unknown', db_index=True)
    # identity 取值: spider / human_ref / direct / unknown
    spider = models.CharField('蜘蛛名', max_length=32, blank=True, default='')
    action = models.CharField('处置动作', max_length=16, default='pass', db_index=True)
    # action 取值: pass / block / disguise / redirect
    reason = models.CharField('处置原因', max_length=64, blank=True, default='')

    def __str__(self):
        return f'{self.ts:%Y-%m-%d %H:%M:%S} {self.ip} {self.method} {self.path[:50]}'


class BlockRule(models.Model):
    """封禁/处置规则：IP / UA / 来源 / 路径"""

    KIND_CHOICES = [
        ('ip', 'IP'),
        ('ua', 'User-Agent'),
        ('referer', '来源域名'),
        ('path', '路径'),
    ]
    MATCH_CHOICES = [
        ('contains', '包含'),
        ('equal', '完全等于'),
        ('startswith', '开头匹配'),
        ('cidr', 'IP段(CIDR)'),
        ('regex', '正则表达式'),
    ]
    ACTION_CHOICES = [
        ('block', '403 拦截'),
        ('disguise', '伪装页'),
        ('redirect', '302 跳转'),
        ('log', '仅记录不拦截'),
    ]

    class Meta:
        verbose_name = '处置规则'
        verbose_name_plural = verbose_name
        ordering = ['-id']

    kind = models.CharField('匹配对象', max_length=16, choices=KIND_CHOICES)
    match_type = models.CharField('匹配方式', max_length=16, choices=MATCH_CHOICES, default='contains')
    value = models.TextField('匹配值')
    action = models.CharField('动作', max_length=16, choices=ACTION_CHOICES, default='block')
    redirect_url = models.CharField('跳转地址(redirect)', max_length=500, blank=True, default='')
    note = models.CharField('备注', max_length=120, blank=True, default='')
    enabled = models.BooleanField('启用', default=True)
    expires_at = models.DateTimeField('过期时间(留空=永久)', null=True, blank=True)
    hit_count = models.PositiveIntegerField('命中次数', default=0)
    created_at = models.DateTimeField('创建时间', auto_now_add=True)

    def __str__(self):
        return f'[{self.get_kind_display()}] {self.value[:50]} → {self.get_action_display()}'
