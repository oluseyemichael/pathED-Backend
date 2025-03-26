from dotenv import load_dotenv
import os
import requests

load_dotenv()
SERPAPI_KEY = os.getenv("SERPAPI_KEY")

def get_blog_posts(topic, timeout=5):
    try:
        # Adjust query for learning-focused results
        params = {
            "engine": "google",
            "q": f"{topic} tutorial",
            "hl": "en",
            "num": 3,  # Get a few results to filter for relevance
            "api_key": SERPAPI_KEY
        }
        response = requests.get("https://serpapi.com/search", params=params, timeout=timeout)
        response.raise_for_status()  # Raises HTTPError for bad responses

        search_results = response.json()
        # Filter for the best learning resource
        if 'organic_results' in search_results and search_results['organic_results']:
            for result in search_results['organic_results']:
                # Search for pages that mention structured learning (course or tutorial terms)
                if any(term in result['title'].lower() for term in ["tutorial", "course", "learn"]):
                    return {
                        "title": result["title"],
                        "url": result["link"]
                    }
            # Fallback to the first link if no specific learning term is found
            best_result = search_results['organic_results'][0]
            return {
                "title": best_result["title"],
                "url": best_result["link"]
            }
        else:
            print("No learning resources found.")
            return None
    except requests.exceptions.HTTPError as err:
        print(f"HTTP error occurred: {err}")
    except Exception as e:
        print(f"An error occurred: {e}")
    return None

# # Test the function with a sample topic
# if __name__ == "__main__":
#     topic = "learn javascript"
#     result = get_blog_posts(topic)
#     if result:
#         print(f"Top learning resource for '{topic}': {result['title']} - {result['url']}")
#     else:
#         print(f"No suitable learning resource found for topic '{topic}'.")
