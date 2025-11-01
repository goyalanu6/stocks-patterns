# Local development configuration
# Copy this file to config.py and fill in your credentials
# For deployment, these values can be set as environment variables:
# - DHAN_ACCESS_TOKEN: Your initial access token
# - DHAN_CLIENT_ID: Your client ID
# - DHAN_API_URL: API endpoint for historical data
# - DHAN_TOKEN_RENEWAL_URL: API endpoint for token renewal

import os

# Credentials (prefer environment variables if available)
INITIAL_ACCESS_TOKEN = os.getenv("DHAN_ACCESS_TOKEN", "your_access_token_here")
DHAN_CLIENT_ID = os.getenv("DHAN_CLIENT_ID", "your_client_id_here")

# API URLs
API_URL = os.getenv("DHAN_API_URL", "https://api.dhan.co/v2/charts/historical")
TOKEN_RENEWAL_URL = os.getenv("DHAN_TOKEN_RENEWAL_URL", "https://api.dhan.co/v2/RenewToken")

# Exchange settings
EXCHANGE_SEGMENT = os.getenv("DHAN_EXCHANGE_SEGMENT", "NSE_EQ")
INSTRUMENT = os.getenv("DHAN_INSTRUMENT", "EQUITY")

# Token renewal settings
TOKEN_RENEWAL_BUFFER_MINUTES = int(os.getenv("DHAN_TOKEN_RENEWAL_BUFFER", "5"))this file to config.py and fill in your Dhan credentials
ACCESS_TOKEN = "your_access_token_here"
DHAN_CLIENT_ID = "your_client_id_here"  # Your Dhan client ID for token renewal

# API configuration
API_URL = "https://api.dhan.co/v2/charts/historical"
TOKEN_RENEWAL_URL = "https://api.dhan.co/v2/RenewToken"
EXCHANGE_SEGMENT = "NSE_EQ"
INSTRUMENT = "EQUITY"