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

def cache_guess(chatId, gameId, messageId):
    r = redis.Redis(connection_pool=redis_pool)
    cache_key = args_to_key(chatId, gameId, messageId)
    if r.get(cache_key):
        return
    r.setex(cache_key, 3600 * 48, messageId)

def get_cached_guesses(chatId, gameId):
    r = redis.Redis(connection_pool=redis_pool)
    return [ r.get(key).decode('utf-8') for key in r.keys(f'{chatId}_{gameId}_*') ]
