from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from typing import Optional
from huggingface_hub import HfApi

from app.auth.api_keys import verify_api_key
from app.auth.rate_limit import limiter
from app.services.huggingface.tasks import TaskStatus
from app.services.huggingface.service import (
    list_models,
    start_download,
    get_download_status,
    cancel_download,
)

router = APIRouter(prefix="/huggingface", tags=["HuggingFace"])

_hf_api = HfApi()


# ======================
# Models
# ======================
class HuggingFaceModelInfo(BaseModel):
    model_id: str
    disk_size: str
    downloads: Optional[int] = None
    likes: Optional[int] = None


class ListHuggingFaceResponse(BaseModel):
    success: bool
    total: int
    models: list[HuggingFaceModelInfo]


class DownloadRequest(BaseModel):
    model_id: str = Field(..., description="ID del modelo en HuggingFace (ej: 'bert-base-uncased')")
    dest: Optional[str] = Field(None, description="Ruta destino. Por defecto: ./data/hf_downloads/<model_id>")


class DownloadTaskResponse(BaseModel):
    task_id: str
    model_id: str
    status: TaskStatus
    progress: float
    dest: str
    current_file: Optional[str] = None
    bytes_downloaded: Optional[int] = None
    total_bytes: Optional[int] = None
    result: Optional[str] = None
    error: Optional[str] = None


# ======================
# Endpoints
# ======================
@router.get("/list", response_model=ListHuggingFaceResponse)
@limiter.limit("5/minute")
async def list_huggingface_models(
    request: Request,
    filter: Optional[str] = None,
    pipeline_tag: Optional[str] = None,
    sort: str = "downloads",
    limit: int = 20,
    author: Optional[str] = None,
    num_parameters: Optional[str] = None,
    no_size: bool = False,
    api_key: str = Depends(verify_api_key),
):
    """
    Lista modelos de HuggingFace con filtros opcionales.
    """
    try:
        models = list_models(
            api=_hf_api,
            filter=filter,
            pipeline_tag=pipeline_tag,
            sort=sort,
            limit=limit,
            author=author,
            num_parameters=num_parameters,
            no_size=no_size,
        )

        return ListHuggingFaceResponse(
            success=True,
            total=len(models),
            models=[HuggingFaceModelInfo(**m) for m in models],
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error listando modelos HuggingFace: {str(e)}")


@router.post("/download", response_model=DownloadTaskResponse)
@limiter.limit("2/minute")
async def create_download(
    request: Request,
    data: DownloadRequest,
    api_key: str = Depends(verify_api_key),
):
    """
    Crea una tarea de descarga de un modelo de HuggingFace.
    Retorna un task_id para consultar el progreso.
    """
    try:
        task = start_download(model_id=data.model_id, dest=data.dest, api=_hf_api)
        return DownloadTaskResponse(**task)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creando descarga: {str(e)}")


@router.get("/download/{task_id}", response_model=DownloadTaskResponse)
@limiter.limit("30/minute")
async def get_download_progress(
    request: Request,
    task_id: str,
    api_key: str = Depends(verify_api_key),
):
    """
    Consulta el estado de una tarea de descarga.
    """
    task = get_download_status(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return DownloadTaskResponse(**task)


@router.delete("/download/{task_id}", response_model=DownloadTaskResponse)
@limiter.limit("10/minute")
async def cancel_download_task(
    request: Request,
    task_id: str,
    api_key: str = Depends(verify_api_key),
):
    """
    Cancela una tarea de descarga en progreso.
    """
    task = cancel_download(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return DownloadTaskResponse(**task)
