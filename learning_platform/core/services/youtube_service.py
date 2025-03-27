from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import logging
from decouple import config
import isodate
from datetime import datetime, timedelta
import re
from difflib import SequenceMatcher
from django.core.cache import cache

# Configure logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

YOUTUBE_API_KEY = config('YOUTUBE_API_KEY')

def calculate_text_similarity(a, b):
    """
    Calculate similarity between two strings using SequenceMatcher.
    """
    a_clean = re.sub(r'[^\w\s]', '', a.lower())
    b_clean = re.sub(r'[^\w\s]', '', b.lower())
    return SequenceMatcher(None, a_clean, b_clean).ratio()

def get_youtube_videos(topic, max_results=10, similarity_threshold=0.6, timeout=10):
    """
    Search YouTube videos with strict language and relevance filtering.
    """
    cache_key = f"youtube_{topic}"
    cached = cache.get(cache_key)
    if cached:
        return cached
    current_year = datetime.now().year
    published_after = f"{current_year - 2}-01-01T00:00:00Z"  # Limit to last 2 years

    try:
        youtube = build('youtube', 'v3', developerKey=YOUTUBE_API_KEY)
        # youtube = build('youtube', 'v3', developerKey=YOUTUBE_API_KEY, cache_discovery=False, requestBuilder=lambda *args, **kwargs: build.HttpRequest(*args, timeout=timeout, **kwargs))
        all_videos = []

        # Define primary language and region filters
        relevance_language = 'en'  # English language content
        primary_region = 'US'      # United States region

        request = youtube.search().list(
            q= f"{topic} tutorial",
            part='snippet',
            maxResults=15,
            order='viewCount',
            videoDuration='medium',  # Videos longer than 20 minutes
            type='video',
            publishedAfter=published_after,
            relevanceLanguage=relevance_language,
            regionCode=primary_region
        )

        response = request.execute()
        
        for item in response.get('items', []):
            try:
                video_id = item['id']['videoId']

                # Fetch video details
                video_details = youtube.videos().list(
                    part='contentDetails,snippet,statistics',
                    id=video_id
                ).execute()

                details = video_details['items'][0]

                duration_str = details['contentDetails']['duration']
                duration = isodate.parse_duration(duration_str) if duration_str else None

                if not duration:
                    continue

                # Extract video details
                title = details['snippet']['title']
                description = details['snippet']['description']
                channel_title = details['snippet']['channelTitle']
                published_at = details['snippet']['publishedAt']
                views = int(details['statistics'].get('viewCount', 0))

                # Calculate similarity
                title_similarity = calculate_text_similarity(topic, title)
                desc_similarity = calculate_text_similarity(topic, description)

                if title_similarity < similarity_threshold and desc_similarity < similarity_threshold:
                    continue

                video_info = {
                    'title': title,
                    'description': description,
                    'videoId': video_id,
                    'url': f"https://www.youtube.com/watch?v={video_id}",
                    'duration': duration,
                    'views': views,
                    'channel_title': channel_title,
                    'published_at': published_at,
                    'title_similarity': title_similarity,
                    'desc_similarity': desc_similarity
                }
                all_videos.append(video_info)
            except Exception as e:
                logger.warning(f"Error processing video: {e}")

        # Return top results sorted by views and relevance
        sorted_videos = sorted(all_videos, key=lambda x: (x['views'], x['title_similarity']), reverse=True)
        return sorted_videos[:max_results]

    except HttpError as e:
        logger.error(f"YouTube API error: {e}")
        return []
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return []

# Example usage
if __name__ == "__main__":
    topic = "Object Oriented Programming"
    videos = get_youtube_videos(topic)
    for video in videos:
        print(f"Title: {video['title']}, URL: {video['url']}, Views: {video['views']}")
