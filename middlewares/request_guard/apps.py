from django.apps import AppConfig


class RequestGuardConfig(AppConfig):
    """request_guard 应用配置：注册后即可自动发现 models/templates/static"""

    name = 'middlewares.request_guard'
    verbose_name = '请求守卫'
    default_auto_field = 'django.db.models.BigAutoField'
