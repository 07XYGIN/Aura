from pydantic import BaseModel

class Memery(BaseModel):
    save: bool
    title: str
    content: str