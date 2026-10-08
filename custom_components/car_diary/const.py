"""Constants for the Car Diary integration."""
from datetime import timedelta

DOMAIN = "car_diary"

API_URL = "https://api.car-diary.net"
# The web app sends its own version; the API has not been seen to check it.
CLIENT_VERSION = "32.2"

CONF_TOKEN = "token"
CONF_USER_ID = "user_id"

UPDATE_INTERVAL = timedelta(minutes=30)

# The document kinds Car Diary keeps an expiry date for ("taxes" in its API).
TAX_TYPES = (
    "vignette",
    "annual_insurance",
    "additional_insurance",
    "technical_review",
    "car_tax",
)
