from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0007_upload_completed_at_upload_error_message_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='product',
            name='marketplace_final_price',
            field=models.DecimalField(blank=True, decimal_places=2, help_text='Latest calculated marketplace price per store+vendor rules', max_digits=10, null=True),
        ),
        migrations.AddField(
            model_name='product',
            name='marketplace_final_inventory',
            field=models.IntegerField(blank=True, help_text='Latest calculated marketplace inventory per store+vendor rules', null=True),
        ),
    ] 