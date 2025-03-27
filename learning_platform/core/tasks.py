from celery import shared_task
from .models import Module

@shared_task
def process_module_content(module_id):
    module = Module.objects.get(id=module_id)
    module.save()  # Triggers video/blog generation