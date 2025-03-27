from celery import shared_task
from .models import Module

import logging
from .services.youtube_service import get_youtube_videos

# Configure logger
logger = logging.getLogger(__name__)

@shared_task
def fetch_module_content(module_id):
    try:
        module = Module.objects.get(id=module_id)
        module.save()  # Triggers video/blog fetching
    except Exception as e:
        logger.error(f"Failed to process module {module_id}: {str(e)}")
        
def fetch_video_links(module_id):
    try:
        module = Module.objects.get(id=module_id)
        # Simplified YouTube search
        videos = get_youtube_videos(module.topic.split(';')[0])  # Use first concept
        if videos:
            module.video_link = videos[0]['url']
            module.save()
    except Exception as e:
        logger.error(f"Video fetch failed for Module {module_id}: {str(e)}")
        