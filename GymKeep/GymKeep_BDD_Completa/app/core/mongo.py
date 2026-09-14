from pymongo import MongoClient

from app.core.config import settings

mongo_client = MongoClient(
    settings.mongo_url,
    serverSelectionTimeoutMS=5000,
)

mongo_db = mongo_client[settings.mongo_db]


def get_mongo_db():
    """Retorna la base Mongo utilizada para eventos y telemetría de IA."""
    return mongo_db
