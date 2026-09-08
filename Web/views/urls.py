# 项目URL配置
from django.urls import path, include

from Web.views import request

urlpatterns = [
    path('', request.index, name='home'),
    path('index/', request.index, name='index'),
]