from ninja.router import Router
from ninja.errors import HttpError
from django.http import FileResponse, HttpResponse
from django.shortcuts import get_object_or_404
from django.db.models import Max
import os

from marketplace.models import Store
from .models import ExportArtifact
from .services import generate_mydeal_export

router = Router()


@router.post("/mydeal/{store_id}/generate")
def generate(request, store_id: int, kind: str):
    if kind not in (ExportArtifact.KIND_PRICE, ExportArtifact.KIND_INVENTORY):
        raise HttpError(400, "Invalid kind. Use 'price' or 'inventory'")
    store = get_object_or_404(Store, id=store_id)
    try:
        artifact = generate_mydeal_export(store.id, kind)
        return {"artifact_id": artifact.id, "status": artifact.status, "file_name": artifact.file_name}
    except Exception as e:
        raise HttpError(500, str(e))


@router.get("/mydeal/{store_id}/latest")
def latest(request, store_id: int, kind: str):
    if kind not in (ExportArtifact.KIND_PRICE, ExportArtifact.KIND_INVENTORY):
        raise HttpError(400, "Invalid kind. Use 'price' or 'inventory'")
    store = get_object_or_404(Store, id=store_id)
    artifact = (ExportArtifact.objects
                .filter(store=store, kind=kind, status=ExportArtifact.STATUS_READY)
                .order_by('-generated_at').first())
    if not artifact:
        return {"found": False}
    return {
        "found": True,
        "artifact_id": artifact.id,
        "file_name": artifact.file_name,
        "generated_at": artifact.generated_at,
        "size_bytes": artifact.size_bytes,
    }


@router.get("/mydeal/{store_id}/latest/download")
def latest_download(request, store_id: int, kind: str):
    if kind not in (ExportArtifact.KIND_PRICE, ExportArtifact.KIND_INVENTORY):
        raise HttpError(400, "Invalid kind. Use 'price' or 'inventory'")
    store = get_object_or_404(Store, id=store_id)
    artifact = (ExportArtifact.objects
                .filter(store=store, kind=kind, status=ExportArtifact.STATUS_READY)
                .order_by('-generated_at').first())
    if not artifact or not artifact.file_path or not os.path.exists(artifact.file_path):
        raise HttpError(404, "No export found")
    response = FileResponse(open(artifact.file_path, 'rb'), as_attachment=True, filename=artifact.file_name)
    return response 