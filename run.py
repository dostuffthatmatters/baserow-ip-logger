from pydantic import BaseModel
import requests


class Config(BaseModel):
    node_identifier: str
    db_token: str
    db_table_id: str
