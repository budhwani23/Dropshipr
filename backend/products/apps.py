from django.apps import AppConfig


class ProductsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'products'

    def ready(self):
        try:
            from products.queue_worker import start_worker, enqueue_upload
            from products.models import Upload
            start_worker()
            for u in Upload.objects.filter(status='queued').order_by('id').only('id'):
                enqueue_upload(u.id)
        except Exception:
            # Avoid crashing app startup on migrations or import side-effects
            pass
