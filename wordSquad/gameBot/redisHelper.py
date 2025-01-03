import redis
import os

def get_redis():
    return redis.Redis(host=os.environ.get("REDIS_HOST", default='127.0.0.1'), db=0, socket_timeout=3)

def args_to_key(*args, **kwargs):
    params = [arg.__name__ if callable(arg) else str(arg) for arg in args] + [str(kwarg) for kwarg in kwargs.values()]
    return "_".join(params)

def redis_cached(func):
    def wrapper(*args, **kwargs):
        r = get_redis()
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
    r = get_redis()
    cache_key = args_to_key(chatId, gameId, messageId)
    if r.get(cache_key):
        return
    r.setex(cache_key, 3600 * 48, messageId)

def get_cached_guesses(chatId, gameId):
    r = get_redis()
    keys = r.keys(f'{chatId}_{gameId}_*')
    guesses = []
    for key in keys:
        guesses.append(r.get(key).decode('utf-8'))
        r.delete(key)
    return guesses

def redis_locked(func):
    def wrapper(*args, **kwargs):
        r = get_redis()
        lock_key = args_to_key('lock', *args, **kwargs)
        with r.lock(lock_key):
            print(f"locked to {lock_key}")
            return func(*args, **kwargs)
    return wrapper

def lock(key):
    r = get_redis()
    return r.lock(key)
