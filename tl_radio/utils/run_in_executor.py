from functools import partial, wraps

from .. import THREAD_POOL, LOOP


async def run_in_executor(func, *args, **kwargs):
    return await LOOP.run_in_executor(executor=THREAD_POOL, func=partial(func, *args, **kwargs))


def make_async(func):
    @wraps(func)
    async def wrapped(*args, **kwargs):
        return await run_in_executor(func, *args, **kwargs)

    return wrapped
