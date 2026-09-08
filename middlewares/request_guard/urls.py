"""request_guard 后台路由（挂在 config.json 的 admin.path 前缀下）"""
from django.urls import path

from . import views

urlpatterns = [
    path('', views.index, name='rg_index'),
    path('login/', views.login, name='rg_login'),
    path('logout/', views.logout, name='rg_logout'),
    path('logs/', views.logs, name='rg_logs'),
    path('logs/<int:log_id>/', views.log_detail, name='rg_log_detail'),
    path('rules/', views.rules, name='rg_rules'),
    path('rules/add/', views.rule_add, name='rg_rule_add'),
    path('rules/<int:rule_id>/toggle/', views.rule_toggle, name='rg_rule_toggle'),
    path('rules/<int:rule_id>/delete/', views.rule_delete, name='rg_rule_delete'),
    path('block-ip/', views.quick_block_ip, name='rg_block_ip'),
    path('unban/', views.unban_ip, name='rg_unban'),
]
