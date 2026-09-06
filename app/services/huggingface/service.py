from pathlib import Path
from typing import Optional

import httpx
from huggingface_hub import HfApi

from app.services.huggingface.tasks import Task, TaskStatus, task_manager

CHUNK_SIZE = 1024 * 1024  # 1MB


def format_size(bytes_size: int | None) -> str:
    if bytes_size is None or bytes_size == 0:
        return "N/A"
    mb = bytes_size / (1024 * 1024)
    if mb >= 1024:
        return f"{mb / 1024:.2f} GB"
    return f"{mb:.2f} MB"


def get_repo_size(api: HfApi, repo_id: str) -> int:
    try:
        info = api.model_info(repo_id, files_metadata=True)
        total = 0
        for sibling in info.siblings:
            if sibling.size is not None:
                total += sibling.size
        return total
    except Exception:
        return 0


def list_models(
    api: HfApi,
    filter: Optional[str] = None,
    pipeline_tag: Optional[str] = None,
    sort: str = "downloads",
    limit: int = 20,
    author: Optional[str] = None,
    num_parameters: Optional[str] = None,
    no_size: bool = False,
) -> list[dict]:
    kwargs = {}
    if filter:
        if "," in filter:
            kwargs["filter"] = [t.strip() for t in filter.split(",")]
        else:
            kwargs["filter"] = filter
    if pipeline_tag:
        kwargs["pipeline_tag"] = pipeline_tag
    if author:
        kwargs["author"] = author
    if num_parameters:
        kwargs["num_parameters"] = num_parameters
    kwargs["sort"] = sort
    kwargs["limit"] = limit

    modelos = list(api.list_models(**kwargs))

    results = []
    for m in modelos:
        model_id = m.id if m.id else "N/A"
        disk_size = "N/A" if no_size else format_size(get_repo_size(api, m.id))

        results.append({
            "model_id": model_id,
            "disk_size": disk_size,
            "downloads": m.downloads,
            "likes": m.likes,
        })

    return results


def _download_file(task: Task, url: str, dest: Path, filename: str):
    with httpx.stream("GET", url, follow_redirects=True) as response:
        response.raise_for_status()
        with open(dest / filename, "wb") as f:
            for chunk in response.iter_bytes(CHUNK_SIZE):
                if task.is_cancelled():
                    return
                f.write(chunk)
                task.meta["bytes_downloaded"] = task.meta.get("bytes_downloaded", 0) + len(chunk)
                total = task.meta.get("total_size", 1)
                task.progress = round(task.meta["bytes_downloaded"] / total, 4) if total > 0 else 0


def _download_task(task: Task, model_id: str, dest: str, api: HfApi):
    task.progress = 0.0
    dest_path = Path(dest)

    repo_info = api.model_info(model_id, files_metadata=True)
    siblings = [s for s in repo_info.siblings if s.rfilename is not None]

    total_size = sum(s.size for s in siblings if s.size is not None)
    task.meta["total_size"] = total_size
    task.meta["bytes_downloaded"] = 0
    task.meta["current_file"] = ""

    for sibling in siblings:
        if task.is_cancelled():
            return

        filename = sibling.rfilename
        task.meta["current_file"] = filename

        file_path = dest_path / filename
        file_path.parent.mkdir(parents=True, exist_ok=True)

        if file_path.exists() and file_path.stat().st_size == (sibling.size or 0):
            task.meta["bytes_downloaded"] = task.meta.get("bytes_downloaded", 0) + (sibling.size or 0)
            total = task.meta.get("total_size", 1)
            task.progress = round(task.meta["bytes_downloaded"] / total, 4) if total > 0 else 0
            continue

        url = f"https://huggingface.co/{model_id}/resolve/main/{filename}"
        _download_file(task, url, dest_path, filename)

    if not task.is_cancelled():
        task.progress = 1.0
    return dest


def start_download(model_id: str, dest: Optional[str] = None, api: Optional[HfApi] = None) -> dict:
    if dest is None:
        dest = str(Path("./data/hf_downloads") / model_id.replace("/", "_"))
    else:
        dest = str(Path(dest).resolve())

    Path(dest).mkdir(parents=True, exist_ok=True)

    if api is None:
        api = HfApi()

    task_id = task_manager.create(_download_task, model_id, dest, api)

    task = task_manager.get(task_id)
    task.meta = {"model_id": model_id, "dest": dest}

    return {
        "task_id": task_id,
        "model_id": model_id,
        "status": TaskStatus.PENDING,
        "progress": 0.0,
        "dest": dest,
    }


def _task_to_dict(task: Task) -> dict:
    return {
        "task_id": task.id,
        "model_id": task.meta.get("model_id", ""),
        "status": task.status,
        "progress": task.progress,
        "dest": task.meta.get("dest", ""),
        "current_file": task.meta.get("current_file", ""),
        "bytes_downloaded": task.meta.get("bytes_downloaded"),
        "total_bytes": task.meta.get("total_size"),
        "result": task.result,
        "error": task.error,
    }


def get_download_status(task_id: str) -> Optional[dict]:
    task = task_manager.get(task_id)
    if task is None:
        return None
    return _task_to_dict(task)


def cancel_download(task_id: str) -> Optional[dict]:
    task = task_manager.get(task_id)
    if task is None:
        return None

    if task.status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED):
        return _task_to_dict(task)

    task.cancel()
    return _task_to_dict(task)
