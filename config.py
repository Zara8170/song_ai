import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# --- OpenAI API Key ---
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# --- Elasticsearch Connection ---
ELASTICSEARCH_HOSTS = os.getenv("ELASTICSEARCH_HOSTS")
ELASTICSEARCH_INDEX = os.getenv("ELASTICSEARCH_INDEX")

# --- Database Connection (for reference, not used by agent) ---
DB_URI = f"mysql+pymysql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}@{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}"
