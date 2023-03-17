import redis
import os

redis_pool = redis.ConnectionPool(host=os.environ.get("REDIS_HOST", default='127.0.0.1'), port=6379, db=0)

def args_to_key(*args, **kwargs):
    params = [arg.__name__ if callable(arg) else str(arg) for arg in args] + [str(kwarg) for kwarg in kwargs.values()]
    return "_".join(params)


def redis_cached(func):
    def wrapper(*args, **kwargs):
        r = redis.Redis(connection_pool=redis_pool)
        cache_key = args_to_key(func, *args, **kwargs)
        cached = r.get(cache_key)
        if cached:
            return cached.decode('utf-8')
        result = func(*args, **kwargs)
        if 'ttl' in kwargs:
            ttl_seconds = kwargs['ttl']
        else:
            ttl_seconds = 3600
        r.setex(cache_key, ttl_seconds, result)
        return result
    return wrapper
