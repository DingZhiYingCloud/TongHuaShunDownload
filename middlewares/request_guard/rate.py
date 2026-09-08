"""请求频控器（内存滑动窗口）

说明：
- 纯内存实现，重启即清零；超限后由中间件调用 ban_until 进入临时封禁（到期自动解除）。
- 封禁状态在内存中，重启/多进程不共享；日志 reason 会标注 rate_limit 供追溯。
"""
import threading
import time


class RateLimiter:
    """单 IP 滑动窗口限流 + 临时封禁"""

    def __init__(self):
        self._lock = threading.Lock()
        self._hits = {}    # ip -> [最近请求时间戳列表]
        self._banned = {}  # ip -> 解封时间戳

    def is_banned(self, ip, now=None):
        """ip 是否仍在临时封禁中"""
        now = now or time.time()
        until = self._banned.get(ip)
        if until is None:
            return False
        if until <= now:
            with self._lock:
                self._banned.pop(ip, None)
            return False
        return True

    def ban_until(self, ip, ban_minutes, now=None):
        """将 ip 加入临时封禁 ban_minutes 分钟"""
        now = now or time.time()
        with self._lock:
            self._banned[ip] = now + ban_minutes * 60
            self._hits.pop(ip, None)

    def unban(self, ip):
        """手动解除临时封禁"""
        with self._lock:
            self._banned.pop(ip, None)
            self._hits.pop(ip, None)

    def check_and_hit(self, ip, per_minute, now=None):
        """记录一次访问并判断本分钟是否已超限（不自动封禁）。

        :return: True=超限（调用方应 ban_until）
        """
        now = now or time.time()
        with self._lock:
            window = self._hits.setdefault(ip, [])
            # 清理超出 1 分钟窗口的旧记录
            while window and window[0] <= now - 60:
                window.pop(0)
            window.append(now)
            return len(window) > per_minute

    def hit_count(self, ip, now=None):
        """查询 ip 最近一分钟内的请求次数"""
        now = now or time.time()
        with self._lock:
            window = self._hits.get(ip, [])
            return sum(1 for t in window if t > now - 60)

    def banned_count(self):
        with self._lock:
            return len(self._banned)

    def banned_snapshot(self):
        """返回 {(ip, 剩余秒数)} 列表，供后台展示"""
        now = time.time()
        with self._lock:
            return [(ip, max(0, int(until - now))) for ip, until in self._banned.items() if until > now]


# 进程内共享的频控器单例（中间件与后台视图共用，保证状态一致）
limiter = RateLimiter()
