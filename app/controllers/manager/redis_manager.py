import json
from typing import Dict

import redis

from app.controllers.manager.base_manager import TaskManager
from app.models.schema import VideoParams
from app.services import task as tm

FUNC_MAP = {
    "start": tm.start,
    # 'start_test': tm.start_test
}


class RedisTaskManager(TaskManager):
    def __init__(
        self,
        max_concurrent_tasks: int,
        redis_url: str,
        max_queued_tasks: int = 100,
    ):
        self.redis_client = redis.Redis.from_url(redis_url)
        super().__init__(max_concurrent_tasks, max_queued_tasks=max_queued_tasks)

    def create_queue(self):
        return "task_queue"

    def enqueue(self, task: Dict):
        # dict.copy() 是浅拷贝，直接改 ["kwargs"]["params"] 会同时改掉调用方
        # 传进来的那个 task：调用方手里的 VideoParams 会被替换成 dict。
        # 这里单独复制一层 kwargs，让序列化真正只作用于要入队的副本。
        task_with_serializable_params = dict(task)
        serializable_kwargs = dict(task["kwargs"])

        params = serializable_kwargs.get("params")
        if isinstance(params, VideoParams):
            # Pydantic v2：.dict() 已废弃，V3 会移除；与 controllers 里的
            # body.model_dump() 保持一致。
            serializable_kwargs["params"] = params.model_dump()

        task_with_serializable_params["kwargs"] = serializable_kwargs
        # 将函数对象转换为其名称
        task_with_serializable_params["func"] = task["func"].__name__
        self.redis_client.rpush(self.queue, json.dumps(task_with_serializable_params))

    def dequeue(self):
        task_json = self.redis_client.lpop(self.queue)
        if task_json:
            task_info = json.loads(task_json)
            # 将函数名称转换回函数对象
            task_info["func"] = FUNC_MAP[task_info["func"]]

            if "params" in task_info["kwargs"] and isinstance(
                task_info["kwargs"]["params"], dict
            ):
                task_info["kwargs"]["params"] = VideoParams(
                    **task_info["kwargs"]["params"]
                )

            return task_info
        return None

    def is_queue_empty(self):
        return self.redis_client.llen(self.queue) == 0

    def queue_size(self):
        return self.redis_client.llen(self.queue)
