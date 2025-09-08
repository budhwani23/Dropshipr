import json
import threading
import queue
from django.db import transaction, close_old_connections
from products.models import Upload
from products.api import _process_upload_in_background

_upload_queue: "queue.Queue[int]" = queue.Queue()
_worker_started = False
_worker_lock = threading.Lock()


def enqueue_upload(upload_id: int) -> None:
    start_worker()
    _upload_queue.put(upload_id)


def start_worker() -> None:
    global _worker_started
    with _worker_lock:
        if _worker_started:
            return
        t = threading.Thread(target=_worker_loop, daemon=True)
        t.start()
        _worker_started = True


def _worker_loop() -> None:
    close_old_connections()
    while True:
        upload_id = _upload_queue.get()
        try:
            # Mark as processing atomically
            with transaction.atomic():
                upload = Upload.objects.select_for_update().get(id=upload_id)
                try:
                    info = json.loads(upload.note) if upload.note else {}
                except Exception:
                    info = {}
                info["status"] = "processing"
                upload.status = "processing"
                upload.note = json.dumps(info)
                upload.save(update_fields=["status", "note"])
            # Process
            _process_upload_in_background(upload_id)
        finally:
            _upload_queue.task_done() 