"""访问者身份识别（纯本地规则，无外部依赖）

输出两种维度：
- identity 形态: spider(搜索引擎蜘蛛) / human_ref(带来源真人) / direct(无来源直连) / unknown(无法识别)
- spider 蜘蛛名: 命中词库时的具体蜘蛛名(如 baidu/google/bing...)，非蜘蛛为空串
"""
import re

# 蜘蛛 UA 判断用到的通用小写特征（词库已在 config.json 中按蜘蛛分组）
# 这里仅兜底处理 UA 为空的边界情况
_EMPTY_UA_CHARS = re.compile(r'^\s*$')


def classify(ua, referer, spider_keywords):
    """识别访问者身份。

    :param ua: 原始 User-Agent
    :param referer: 原始 Referer（可能为空）
    :param spider_keywords: config.json 中的 spider_keywords 字典 {蜘蛛名: [关键词,...]}
    :return: (identity, spider)
    """
    ua_lower = (ua or '').strip().lower()

    # 1) 蜘蛛识别：先按具体词库匹配，再按通用词兜底
    if ua_lower:
        groups = spider_keywords or {}
        for name, keys in groups.items():
            if not keys:
                continue
            for key in keys:
                key = str(key).lower()
                if key and key in ua_lower:
                    return 'spider', name

    # 2) 非蜘蛛：按是否携带来源区分直连与来源访问
    if not referer or not referer.strip():
        return 'direct', ''

    return 'human_ref', ''


def is_spider_ua(ua, spider_keywords):
    """快速判断该 UA 是否为蜘蛛（供页面/统计复用）。"""
    return classify(ua, None, spider_keywords)[0] == 'spider'
