from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("vendor", "0002_remove_vendorprice_price_cents_vendorprice_price"),
    ]

    operations = [
        migrations.CreateModel(
            name="GoogleOAuthCredential",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("user_email", models.CharField(db_index=True, max_length=255)),
                ("google_user_id", models.CharField(blank=True, default="", max_length=255)),
                ("access_token", models.TextField()),
                ("refresh_token", models.TextField(blank=True, default="")),
                ("token_uri", models.CharField(default="https://oauth2.googleapis.com/token", max_length=255)),
                ("client_id", models.CharField(max_length=255)),
                ("client_secret", models.CharField(max_length=255)),
                ("scopes", models.TextField()),
                ("expiry", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "unique_together": {("user_email", "client_id")},
            },
        ),
    ] 