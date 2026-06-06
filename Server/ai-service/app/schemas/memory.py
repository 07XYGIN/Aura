from pydantic import BaseModel


class Memory(BaseModel):
    save: bool
    title: str
    content: str
