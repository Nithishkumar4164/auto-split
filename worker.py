"""RQ worker entry point for AutoSplit."""
from redis import Redis
from rq import Worker, Queue

from config import Config

redis_conn = Redis.from_url(Config.REDIS_URL)
q = Queue(connection=redis_conn)

if __name__ == '__main__':
    Worker([q], connection=redis_conn).work()
