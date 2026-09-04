import secrets
from uuid import uuid4

from fastapi import Request

from app.config import config
from app.models.exception import HttpException


def get_task_id(request: Request):
    task_id = request.headers.get("x-task-id")
    if not task_id:
        task_id = uuid4()
    return str(task_id)


def get_api_key(request: Request):
    api_key = request.headers.get("x-api-key")
    return api_key


def verify_token(request: Request):
    expected_token = config.app.get("api_key", "")
    token = get_api_key(request)
    # 1. api_key 未配置时必须一律拒绝。之前空字符串会和缺省值相等，
    #    于是带一个空的 x-api-key 头就能通过，而不带头的请求反而被拒，
    #    很容易让人误以为鉴权已经生效。
    # 2. 使用常量时间比较，避免通过响应时间逐字节推断出 api_key。
    if (
        not expected_token
        or not token
        or not secrets.compare_digest(str(token), str(expected_token))
    ):
        request_id = get_task_id(request)
        request_url = request.url
        user_agent = request.headers.get("user-agent")
        raise HttpException(
            task_id=request_id,
            status_code=401,
            message=f"invalid token: {request_url}, {user_agent}",
        )
