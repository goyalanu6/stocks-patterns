import os
from dotenv import load_dotenv
from pathlib import Path
import streamlit as st

# Load environment variables from .env file if it exists
env_path = Path(__file__).parent / '.env'
load_dotenv(dotenv_path=env_path)

# Credentials (prefer environment variables)
# INITIAL_ACCESS_TOKEN = os.getenv("DHAN_ACCESS_TOKEN")
# DHAN_CLIENT_ID = os.getenv("DHAN_CLIENT_ID")
INITIAL_ACCESS_TOKEN = st.secrets["DHAN_ACCESS_TOKEN"]
DHAN_CLIENT_ID = st.secrets["DHAN_CLIENT_ID"]

if not INITIAL_ACCESS_TOKEN or not DHAN_CLIENT_ID:
    raise ValueError(
        "Missing required environment variables. Please set DHAN_ACCESS_TOKEN and DHAN_CLIENT_ID "
        "either in your .env file or as environment variables."
    )

# API URLs
# API_URL = os.getenv("DHAN_API_URL", "https://api.dhan.co/v2/charts/historical")
# TOKEN_RENEWAL_URL = os.getenv("DHAN_TOKEN_RENEWAL_URL", "https://api.dhan.co/v2/RenewToken")

API_URL = "https://api.dhan.co/v2/charts/historical"
TOKEN_RENEWAL_URL = "https://api.dhan.co/v2/RenewToken"

# Exchange settings
# EXCHANGE_SEGMENT = os.getenv("DHAN_EXCHANGE_SEGMENT", "NSE_EQ")
# INSTRUMENT = os.getenv("DHAN_INSTRUMENT", "EQUITY")

EXCHANGE_SEGMENT = "NSE_EQ"
INSTRUMENT = "EQUITY"

# Token renewal settings
# TOKEN_RENEWAL_BUFFER_MINUTES = int(os.getenv("DHAN_TOKEN_RENEWAL_BUFFER", "5"))
TOKEN_RENEWAL_BUFFER_MINUTES = 5