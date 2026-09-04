import glob
import os
import pathlib
import shutil
import tempfile
from typing import Union
from urllib.parse import quote

from fastapi import BackgroundTasks, Depends, Path, Query, Request, UploadFile
from fastapi.params import File
from fastapi.responses import FileResponse, Response, StreamingResponse
from loguru import logger

from app.config import config
from app.controllers import base
from app.controllers.manager.base_manager import TaskQueueFullError
from app.controllers.manager.memory_manager import InMemoryTaskManager
from app.controllers.manager.redis_manager import RedisTaskManager
from app.controllers.v1.base import new_router
from app.models.exception import HttpException
from app.models.schema import (
    AudioRequest,
    BgmRetrieveResponse,
    BgmUploadResponse,
    SubtitleRequest,
    TaskDeletionResponse,
    TaskQueryRequest,
    TaskQueryResponse,
    TaskResponse,
    TaskVideoRequest,
    VideoMaterialUploadResponse,
    VideoMaterialRetrieveResponse
)
from app.services import state as sm
from app.services import task as tm
from app.utils import file_security, utils

# 认证依赖项
# router = new_router(dependencies=[Depends(base.verify_token)])
router = new_router()

# 分块拷贝上传内容的块大小。
_UPLOAD_CHUNK_SIZE = 1024 * 1024

_enable_redis = config.app.get("enable_redis", False)
_redis_host = config.app.get("redis_host", "localhost")
_redis_port = config.app.get("redis_port", 6379)
_redis_db = config.app.get("redis_db", 0)
_redis_password = config.app.get("redis_password", None)
_max_concurrent_tasks = config.app.get("max_concurrent_tasks", 5)
_max_queued_tasks = config.app.get("max_queued_tasks", 100)

def _build_redis_url(host: str, port, db, password) -> str:
    # The password must be percent-encoded: a literal "@", ":" or "/" inside it
    # splits the authority section and redis-py then parses a wrong host/port.
    # An unset password must be omitted entirely, otherwise an f-string turns
    # None into the literal password "None" and AUTH fails against a
    # password-less server.
    credentials = f":{quote(str(password), safe='')}@" if password else ""
    return f"redis://{credentials}{host}:{port}/{db}"


redis_url = _build_redis_url(_redis_host, _redis_port, _redis_db, _redis_password)
# 根据配置选择合适的任务管理器
if _enable_redis:
    task_manager = RedisTaskManager(
        max_concurrent_tasks=_max_concurrent_tasks,
        redis_url=redis_url,
        max_queued_tasks=_max_queued_tasks,
    )
else:
    task_manager = InMemoryTaskManager(
        max_concurrent_tasks=_max_concurrent_tasks,
        max_queued_tasks=_max_queued_tasks,
    )


def _save_upload_atomically(upload: UploadFile, save_path: str) -> None:
    """
    将上传文件落盘。

    1. 用 shutil.copyfileobj 分块拷贝，而不是 file.read() 一次性读进内存。
       UploadFile 超过阈值后本身就落在临时文件上，整包读取会让一个大素材
       直接变成同等大小的内存峰值。
    2. 先写临时文件再 os.replace 原子替换。直接以 "wb+" 打开目标路径会先
       把已有的同名文件截断，一旦上传中断，原来那份可用的素材就没了。
    """
    save_dir = os.path.dirname(save_path) or "."
    fd, tmp_path = tempfile.mkstemp(prefix=".upload-", dir=save_dir)
    try:
        upload.file.seek(0)
        with os.fdopen(fd, "wb") as buffer:
            shutil.copyfileobj(upload.file, buffer, _UPLOAD_CHUNK_SIZE)
        os.replace(tmp_path, save_path)
    except BaseException:
        try:
            os.remove(tmp_path)
        except OSError:
            pass
        raise


def _sanitize_upload_filename(filename: str, request_id: str) -> str:
    # 浏览器或客户端有时会附带目录信息，甚至可能夹带 ../ 这类穿越片段。
    # 这里只保留纯文件名，避免上传接口把文件写到目标目录之外。
    normalized_name = (filename or "").replace("\\", "/").split("/")[-1].strip()
    if not normalized_name or normalized_name in {".", ".."}:
        raise HttpException(
            task_id=request_id,
            status_code=400,
            message=f"{request_id}: invalid filename",
        )
    return normalized_name


def _resolve_path_within_directory(base_dir: str, unsafe_path: str, request_id: str) -> str:
    try:
        return file_security.resolve_path_within_directory(base_dir, unsafe_path)
    except ValueError as exc:
        logger.warning(
            f"reject unsafe file path, request_id: {request_id}, path: {unsafe_path}, "
            f"error: {str(exc)}"
        )
        raise HttpException(
            task_id=request_id,
            status_code=404 if str(exc) == "file does not exist" else 403,
            message=f"{request_id}: invalid file path",
        )

def _task_file_to_uri(file: str, endpoint: str, task_dir: str, request_id: str) -> str:
    if not isinstance(file, str):
        return file

    if file.startswith(("http://", "https://")):
        return file

    try:
        resolved_path = file_security.resolve_path_within_directory(task_dir, file)
    except ValueError as exc:
        # 任务状态理论上只应保存任务目录内的产物路径。这里不再继续拼接 URL，
        # 避免把异常路径包装成可访问链接；同时保留原值，便于排查历史脏数据。
        logger.warning(
            f"skip unsafe task output path, request_id: {request_id}, path: {file}, "
            f"error: {str(exc)}"
        )
        return file

    relative_path = os.path.relpath(resolved_path, task_dir).replace("\\", "/")
    uri_path = f"tasks/{relative_path}"
    if endpoint:
        return f"{endpoint.rstrip('/')}/{uri_path}"
    return f"/{uri_path}"


@router.post("/videos", response_model=TaskResponse, summary="Generate a short video")
def create_video(
    background_tasks: BackgroundTasks, request: Request, body: TaskVideoRequest
):
    return create_task(request, body, stop_at="video")


@router.post("/subtitle", response_model=TaskResponse, summary="Generate subtitle only")
def create_subtitle(
    background_tasks: BackgroundTasks, request: Request, body: SubtitleRequest
):
    return create_task(request, body, stop_at="subtitle")


@router.post("/audio", response_model=TaskResponse, summary="Generate audio only")
def create_audio(
    background_tasks: BackgroundTasks, request: Request, body: AudioRequest
):
    return create_task(request, body, stop_at="audio")


def create_task(
    request: Request,
    body: Union[TaskVideoRequest, SubtitleRequest, AudioRequest],
    stop_at: str,
):
    task_id = utils.get_uuid()
    request_id = base.get_task_id(request)
    try:
        task = {
            "task_id": task_id,
            "request_id": request_id,
            "params": body.model_dump(),
        }
        sm.state.update_task(task_id)
        task_manager.add_task(tm.start, task_id=task_id, params=body, stop_at=stop_at)
        logger.success(f"Task created: {utils.to_json(task)}")
        return utils.get_response(200, task)
    except TaskQueueFullError as e:
        sm.state.delete_task(task_id)
        logger.warning(
            f"reject task because queue is full, request_id: {request_id}, task_id: {task_id}"
        )
        raise HttpException(
            task_id=task_id, status_code=429, message=f"{request_id}: {str(e)}"
        )
    except ValueError as e:
        raise HttpException(
            task_id=task_id, status_code=400, message=f"{request_id}: {str(e)}"
        )

@router.get("/tasks", response_model=TaskQueryResponse, summary="Get all tasks")
def get_all_tasks(request: Request, page: int = Query(1, ge=1), page_size: int = Query(10, ge=1)):
    tasks, total = sm.state.get_all_tasks(page, page_size)

    response = {
        "tasks": tasks,
        "total": total,
        "page": page,
        "page_size": page_size,
    }
    return utils.get_response(200, response)



@router.get(
    "/tasks/{task_id}", response_model=TaskQueryResponse, summary="Query task status"
)
def get_task(
    request: Request,
    task_id: str = Path(..., description="Task ID"),
    query: TaskQueryRequest = Depends(),
):
    request_id = base.get_task_id(request)
    endpoint = config.app.get("endpoint", "").rstrip("/")
    task = sm.state.get_task(task_id)
    if task:
        task_dir = utils.task_dir()
        response_task = dict(task)

        if "videos" in task:
            response_task["videos"] = [
                _task_file_to_uri(v, endpoint, task_dir, request_id)
                for v in task["videos"]
            ]
        if "combined_videos" in task:
            response_task["combined_videos"] = [
                _task_file_to_uri(v, endpoint, task_dir, request_id)
                for v in task["combined_videos"]
            ]
        return utils.get_response(200, response_task)

    raise HttpException(
        task_id=task_id, status_code=404, message=f"{request_id}: task not found"
    )


@router.delete(
    "/tasks/{task_id}",
    response_model=TaskDeletionResponse,
    summary="Delete a generated short video task",
)
def delete_video(request: Request, task_id: str = Path(..., description="Task ID")):
    request_id = base.get_task_id(request)
    task = sm.state.get_task(task_id)
    if task:
        tasks_dir = utils.task_dir()
        current_task_dir = os.path.join(tasks_dir, task_id)
        if os.path.exists(current_task_dir):
            shutil.rmtree(current_task_dir)

        sm.state.delete_task(task_id)
        logger.success(f"video deleted: {utils.to_json(task)}")
        return utils.get_response(200)

    raise HttpException(
        task_id=task_id, status_code=404, message=f"{request_id}: task not found"
    )


@router.get(
    "/musics", response_model=BgmRetrieveResponse, summary="Retrieve local BGM files"
)
def get_bgm_list(request: Request):
    suffix = "*.mp3"
    song_dir = utils.song_dir()
    files = glob.glob(os.path.join(song_dir, suffix))
    bgm_list = []
    for file in files:
        filename = os.path.basename(file)
        bgm_list.append(
            {
                "name": filename,
                "size": os.path.getsize(file),
                # 只返回文件名，避免把服务器绝对路径暴露给调用方。
                # 服务端后续会把该文件名解析回 songs 白名单目录。
                "file": filename,
            }
        )
    response = {"files": bgm_list}
    return utils.get_response(200, response)


@router.post(
    "/musics",
    response_model=BgmUploadResponse,
    summary="Upload the BGM file to the songs directory",
)
def upload_bgm_file(request: Request, file: UploadFile = File(...)):
    request_id = base.get_task_id(request)
    safe_filename = _sanitize_upload_filename(file.filename, request_id)
    # 必须校验真正的扩展名。endswith("mp3") 会放行 "mp3"、"song.wavmp3"
    # 这类没有 .mp3 后缀的文件名，它们能上传成功，却永远不会出现在
    # GET /musics 的 *.mp3 列表里，最终只是留下一个用不了的死文件。
    if utils.parse_extension(safe_filename) == "mp3":
        song_dir = utils.song_dir()
        save_path = os.path.join(song_dir, safe_filename)
        # save file (overwrites any existing file with the same name)
        _save_upload_atomically(file, save_path)
        response = {"file": safe_filename}
        return utils.get_response(200, response)

    raise HttpException(
        "", status_code=400, message=f"{request_id}: Only *.mp3 files can be uploaded"
    )

@router.get(
    "/video_materials", response_model=VideoMaterialRetrieveResponse, summary="Retrieve local video materials"
)
def get_video_materials_list(request: Request):
    allowed_suffixes = ("mp4", "mov", "avi", "flv", "mkv", "jpg", "jpeg", "png")
    local_videos_dir = utils.storage_dir("local_videos", create=True)
    files = []
    for suffix in allowed_suffixes:
        files.extend(glob.glob(os.path.join(local_videos_dir, f"*.{suffix}")))
    # 文件系统枚举顺序不稳定，直接返回会导致“顺序拼接”在不同机器或不同
    # 时刻表现不一致。这里统一按文件名排序，至少保证服务端返回顺序可预测。
    files.sort(key=lambda file_path: os.path.basename(file_path).lower())
    video_materials_list = []
    for file in files:
        filename = os.path.basename(file)
        video_materials_list.append(
            {
                "name": filename,
                "size": os.path.getsize(file),
                # 与 BGM 一样，只返回文件名；创建任务时再在 local_videos
                # 白名单目录内解析，避免 API 泄露宿主机绝对路径。
                "file": filename,
            }
        )
    response = {"files": video_materials_list}
    return utils.get_response(200, response)


@router.post(
    "/video_materials",
    response_model=VideoMaterialUploadResponse,
    summary="Upload the video material file to the local videos directory",
)
def upload_video_material_file(request: Request, file: UploadFile = File(...)):
    request_id = base.get_task_id(request)
    safe_filename = _sanitize_upload_filename(file.filename, request_id)
    # check file ext
    allowed_suffixes = ("mp4", "mov", "avi", "flv", "mkv", "jpg", "jpeg", "png")
    # parse_extension 已经统一转小写，兼容 .MOV 这类大写后缀；同时要求存在
    # 真正的扩展名，避免 "mp4"、"clip.badmov" 这类文件被接收后无法被
    # GET /video_materials 的 *.<suffix> 枚举到。
    if utils.parse_extension(safe_filename) in allowed_suffixes:
        local_videos_dir = utils.storage_dir("local_videos", create=True)
        save_path = os.path.join(local_videos_dir, safe_filename)
        # save file (overwrites any existing file with the same name)
        _save_upload_atomically(file, save_path)
        response = {"file": safe_filename}
        return utils.get_response(200, response)

    raise HttpException(
        "", status_code=400, message=f"{request_id}: Only files with extensions {', '.join(allowed_suffixes)} can be uploaded"
    )

RANGE_UNSATISFIABLE = object()
_RANGE_UNIT_PREFIX = "bytes="


def parse_range_header(range_header: str, file_size: int):
    """
    解析 HTTP Range 请求头，返回闭区间 (start, end)。

    按 RFC 7233 处理三种结果：
    * None —— 没有 Range、语法无法识别或不支持的形式（例如多段 range）。
      这类请求必须被忽略并返回完整内容，而不是报错。
    * RANGE_UNSATISFIABLE —— 语法合法但起点超出文件长度，应返回 416。
    * (start, end) —— 可服务的区间，end 一定收敛在文件末尾之内。
    """
    if not range_header:
        return None

    value = range_header.strip()
    if not value.lower().startswith(_RANGE_UNIT_PREFIX):
        return None

    spec = value[len(_RANGE_UNIT_PREFIX) :].strip()
    # 多段 range 需要 multipart/byteranges 响应，这里不支持；按忽略处理，
    # 返回完整内容依然是合法响应。
    if "," in spec or "-" not in spec:
        return None

    start_text, _, end_text = spec.partition("-")
    start_text, end_text = start_text.strip(), end_text.strip()

    try:
        if not start_text:
            # 后缀形式 "bytes=-N"：请求最后 N 个字节。
            suffix_length = int(end_text)
            if suffix_length <= 0:
                return None
            start = max(file_size - suffix_length, 0)
            end = file_size - 1
        else:
            start = int(start_text)
            end = int(end_text) if end_text else file_size - 1
    except ValueError:
        return None

    if start < 0:
        return None
    # 顺序很重要：开放式 "bytes=5000-" 会把 end 补成文件末尾，如果先判断
    # end < start，就会把"起点越界"误判成语法错误并返回完整内容，而不是 416。
    if start >= file_size:
        return RANGE_UNSATISFIABLE
    if end < start:
        return None

    # end 必须收敛到文件末尾，否则 Content-Length 会大于真正发送的字节数，
    # 客户端会一直等待永远不会到达的数据。
    return start, min(end, file_size - 1)


@router.get("/stream/{file_path:path}")
async def stream_video(request: Request, file_path: str):
    request_id = base.get_task_id(request)
    tasks_dir = utils.task_dir()
    video_path = _resolve_path_within_directory(tasks_dir, file_path, request_id)
    video_size = os.path.getsize(video_path)
    parsed_range = parse_range_header(request.headers.get("Range"), video_size)

    if parsed_range is RANGE_UNSATISFIABLE:
        return Response(
            status_code=416,
            headers={
                "Content-Range": f"bytes */{video_size}",
                "Accept-Ranges": "bytes",
            },
        )

    if parsed_range is None:
        start = 0
        end = max(video_size - 1, 0)
        length = video_size
        status_code = 200
    else:
        start, end = parsed_range
        length = end - start + 1
        status_code = 206

    def file_iterator(offset: int, bytes_to_read: int):
        if bytes_to_read <= 0:
            return
        with open(video_path, "rb") as f:
            f.seek(offset, os.SEEK_SET)
            remaining = bytes_to_read
            while remaining > 0:
                data = f.read(min(64 * 1024, remaining))
                if not data:
                    break
                remaining -= len(data)
                yield data

    response = StreamingResponse(
        file_iterator(start, length), media_type="video/mp4"
    )
    response.headers["Accept-Ranges"] = "bytes"
    response.headers["Content-Length"] = str(length)
    if status_code == 206:
        response.headers["Content-Range"] = f"bytes {start}-{end}/{video_size}"
    response.status_code = status_code

    return response


@router.get("/download/{file_path:path}")
async def download_video(request: Request, file_path: str):
    """
    download video
    :param request: Request request
    :param file_path: video file path, eg: /cd1727ed-3473-42a2-a7da-4faafafec72b/final-1.mp4
    :return: video file
    """
    request_id = base.get_task_id(request)
    tasks_dir = utils.task_dir()
    video_path = _resolve_path_within_directory(tasks_dir, file_path, request_id)
    file_path = pathlib.Path(video_path)
    filename = file_path.stem
    extension = file_path.suffix
    headers = {"Content-Disposition": f"attachment; filename={filename}{extension}"}
    return FileResponse(
        path=video_path,
        headers=headers,
        filename=f"{filename}{extension}",
        media_type=f"video/{extension[1:]}",
    )
