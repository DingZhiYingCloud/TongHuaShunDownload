"""全局模板上下文处理器: 向所有模板注入页面底部所需的服务端数据"""
from .friend_links import fetch_friend_links


def friend_links(request):
    """注入友情链接列表(friend_links), 页面 include 片段后服务端直接渲染, 搜索引擎可见"""
    return {'friend_links': fetch_friend_links()}
