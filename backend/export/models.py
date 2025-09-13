from django.db import models
from django.utils import timezone


class ExportArtifact(models.Model):
    KIND_PRICE = 'price'
    KIND_INVENTORY = 'inventory'
    KIND_CHOICES = [
        (KIND_PRICE, 'price'),
        (KIND_INVENTORY, 'inventory'),
    ]

    STATUS_QUEUED = 'queued'
    STATUS_GENERATING = 'generating'
    STATUS_READY = 'ready'
    STATUS_FAILED = 'failed'
    STATUS_CHOICES = [
        (STATUS_QUEUED, 'queued'),
        (STATUS_GENERATING, 'generating'),
        (STATUS_READY, 'ready'),
        (STATUS_FAILED, 'failed'),
    ]

    store = models.ForeignKey('marketplace.Store', on_delete=models.CASCADE, related_name='export_artifacts')
    marketplace_code = models.CharField(max_length=50)
    kind = models.CharField(max_length=20, choices=KIND_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_QUEUED)
    file_path = models.TextField(blank=True)
    file_name = models.CharField(max_length=255, blank=True)
    size_bytes = models.BigIntegerField(null=True, blank=True)
    checksum = models.CharField(max_length=64, blank=True)
    error = models.TextField(blank=True)
    generated_at = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=['store', 'kind', '-generated_at']),
        ]
        ordering = ['-generated_at']

    def __str__(self):
        return f"Export {self.kind} for store={self.store_id} at {self.generated_at}" 