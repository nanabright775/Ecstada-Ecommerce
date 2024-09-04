# Generated by Django 4.2 on 2024-09-03 19:49

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0008_item_related_image_1_item_related_image_2_and_more'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='payment',
            name='stripe_charge_id',
        ),
        migrations.AddField(
            model_name='payment',
            name='momo_transaction_id',
            field=models.CharField(blank=True, max_length=50, null=True),
        ),
    ]
