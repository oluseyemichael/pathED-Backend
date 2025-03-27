from celery import shared_task
from .models import Module

@shared_task
def fetch_module_content(module_id):
    try:
        module = Module.objects.get(id=module_id)
        module.save()  # Triggers video/blog fetching
    except Exception as e:
        logger.error(f"Failed to process module {module_id}: {str(e)}")