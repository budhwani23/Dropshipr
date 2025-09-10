from django.db import models
from django.utils import timezone

# Create your models here.
class Vendor(models.Model):
    code = models.CharField(max_length=255, unique=True)
    name = models.CharField(max_length=255)

    def __str__(self):
        return self.name
    
    
class VendorPrice(models.Model):
    """
    Latest scraped price+stock per product.
    Replaces the Postgres UNIQUE index on scrapes(product_id).
    """
    product = models.OneToOneField('products.Product', on_delete=models.CASCADE, related_name="latest_price")
    price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    stock = models.IntegerField(null=True, blank=True)
    error_code = models.CharField(max_length=50, blank=True)
    scraped_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"Latest price for {self.product_id}"


class GoogleOAuthCredential(models.Model):
    user_email = models.CharField(max_length=255, db_index=True)
    google_user_id = models.CharField(max_length=255, blank=True, default="")
    access_token = models.TextField()
    refresh_token = models.TextField(blank=True, default="")
    token_uri = models.CharField(max_length=255, default="https://oauth2.googleapis.com/token")
    client_id = models.CharField(max_length=255)
    client_secret = models.CharField(max_length=255)
    scopes = models.TextField()
    expiry = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("user_email", "client_id")

    def __str__(self) -> str:
        return f"GoogleOAuthCredential<{self.user_email}>"

