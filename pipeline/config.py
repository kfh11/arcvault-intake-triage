import os
from dotenv import load_dotenv

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
MODEL = "gpt-4o-mini"
TEMPERATURE = 0
SEED = 42
CONFIDENCE_THRESHOLD = 0.70

CATEGORY_TO_QUEUE: dict[str, str] = {
    "Bug Report": "Engineering",
    "Feature Request": "Product",
    "Billing Issue": "Billing",
    "Technical Question": "IT/Security",
    "Incident/Outage": "Engineering-Urgent",
}

ESCALATION_KEYWORDS: list[str] = [
    "outage",
    "down for all users",
    "all users affected",
    "system down",
    "critical failure",
    "data breach",
    "security incident",
    "multiple users affected",
]
