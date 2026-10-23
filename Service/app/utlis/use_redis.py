import redis
from typing import Literal,Optional
REDIS_POOL = redis.ConnectionPool(
    host='localhost',
    port=6379,
    db=0,
    max_connections=10,
    decode_responses=True,
    socket_timeout=5,
    socket_connect_timeout=5
)

def get_redis_client():
    """获取Redis客户端"""
    return redis.Redis(connection_pool=REDIS_POOL)

def redis_set(key: str, value: str, timeout: Optional[int] = None) -> bool | str | bytes | None:
    """
    设置键值对
    :param key: 键名
    :param value: 值
    :param timeout: 过期时间（秒）
    :return: 成功返回True，失败返回False
    """
    client = get_redis_client()
    return client.set(key, value, ex=timeout)


def redis_get(key: str) -> Optional[str]:
    """
    获取键值
    :param key: 键名
    :return: 值，不存在返回None
    """
    client = get_redis_client()
    return client.get(key)


def redis_delete(key: str) -> bool:
    """
    删除键
    :param key: 键名
    :return: 删除成功返回True，不存在返回False
    """
    client = get_redis_client()
    return bool(client.delete(key))


def redis_exists(key: str) -> bool:
    """
    检查键是否存在
    :param key: 键名
    :return: 存在返回True
    """
    client = get_redis_client()
    return bool(client.exists(key))

def redis_expire(key: str, timeout: int) -> bool:
    """
    设置过期时间
    :param key: 键名
    :param timeout: 过期时间（秒）
    :return: 成功返回True
    """
    client = get_redis_client()
    return client.expire(key, timeout)
