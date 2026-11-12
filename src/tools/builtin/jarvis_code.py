import logging
import requests  # Added requests dependency

# Setup logging for this specific module
logger = logging.getLogger(__name__)

class JellyfinPlugin:
    """
    Structure for a Jellyfin integration plugin.
    This class handles authentication, data fetching, and event management.
    """

    def __init__(self, api_key: str, server_url: str):
        """
        Initializes the Jellyfin plugin context.

        :param api_key: Jellyfin API key for authentication.
        :param server_url: Full URL of the Jellyfin server (e.g., http://localhost:8096).
        """
        if not api_key or not server_url:
            raise ValueError("API key and server URL are required.")

        self.api_key = api_key
        self.server_url = server_url.rstrip('/')  # Ensure no trailing slash
        self.session = requests.Session()
        self.session.headers.update({
            "X-Emby-Token": self.api_key,
            "Content-Type": "application/json"
        })

    def update_server_url(self, new_server_url: str):
        """
        Updates the Jellyfin server URL and performs connection retry.

        :param new_server_url: The new URL of the Jellyfin server.
        """
        logger.info(f"Updating Jellyfin server URL to {new_server_url}")
        self.server_url = new_server_url.rstrip('/')
        self.connect()

    def connect(self) -> bool:
        """
        Connects to the Jellyfin server to validate configuration.

        :return: True if connection is successful, False otherwise.
        """
        try:
            logger.info(f"Attempting to connect to Jellyfin server at {self.server_url}")
            url = f"{self.server_url}/System/Info"
            response = self.session.get(url)
            response.raise_for_status()
            logger.info("Successfully connected to Jellyfin.")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to Jellyfin: {e}")
            return False

    def fetch_recent_media(self, media_type: str = "Movie", limit: int = 10):
        """
        Fetches recently added items from Jellyfin.

        :param media_type: The type of media to fetch (e.g., Movie, Series).
        :param limit: Maximum number of items to return.
        :return: List of media item dictionaries.
        """
        url = f"{self.server_url}/Items/Latest"
        params = {
            "IncludeItemTypes": media_type,
            "Limit": limit
        }
        
        try:
            logger.debug(f"Fetching recent {media_type}s with limit {limit}")
            response = self.session.get(url, params=params)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Error fetching recent media: {e}")
            return []

    def on_playback_start(self, item_id: str, user_id: str):
        """
        Event handler for when playback starts. Useful for Scrobbling, etc.

        :param item_id: The ID of the item being played.
        :param user_id: The ID of the user playing the item.
        """
        logger.info(f"User {user_id} started playback of item {item_id}")
        # Implement logic for playback tracking (e.g. /Notifications/Playing)

# Usage Example (Normally done by main application)
if __name__ == "__main__":
    # Basic logging setup for testing
    logging.basicConfig(level=logging.INFO)
    
    # Instance would be created via configuration management
    # Placeholder values for server URL and API key.
    plugin = JellyfinPlugin(api_key="12a345bc6789de0fghij12k34lmno56p", server_url="YOUR_JELLYFIN_SERVER_URL")
    
    if plugin.connect():
        recent_media = plugin.fetch_recent_media(limit=5)
        logger.info(f"Found {len(recent_media)} recent media items.")