from dotenv import load_dotenv
from langchain_postgres import PGVector
from langchain_community.embeddings import DashScopeEmbeddings

from app.core.config import SYNC_DATABASE_URL
load_dotenv()
embeddings = DashScopeEmbeddings(
    model="text-embedding-v4"
)

def get_vector_store(user_id: str = None):
    
    return PGVector(
        embeddings=embeddings, 
        collection_name=user_id, 
        connection=SYNC_DATABASE_URL,
        use_jsonb=True,
    )

