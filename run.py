from pydantic import BaseModel
import requests


class Config(BaseModel):
    node_identifier: str
    db_token: str
    db_table_id: str


def get_existing_row_ids(config: Config) -> list[int]:
    requests.get(
        f"https://api.baserow.io/api/database/rows/table/"
        + f"{config.table_id}/?user_field_names=true&filter__"
        + f"node-identifier__equal={config.node_identifier}",
        headers={"Authorization": f"Token {config.baserow_db_token}"},
    )


def delete_row_ids(config: Config, row_ids: list[int]) -> list[int]:
    requests.post(
        f"https://api.baserow.io/api/database/rows/table/{config.table_id}/batch-delete/",
        headers={
            "Authorization": f"Token {config.baserow_db_token}",
            "Content-Type": "application/json",
        },
        json={"items": row_ids},
    )


def create_row(config: Config, local_ip: str, public_ip: str) -> list[int]:
    requests.post(
        f"https://api.baserow.io/api/database/rows/table/{config.table_id}?user_field_names=true",
        headers={
            "Authorization": f"Token {config.baserow_db_token}",
            "Content-Type": "application/json",
        },
        json={
            "node-identifier": config.node_identifier,
            "local-ip-address": local_ip,
            "public-ip-address": public_ip,
        },
    )
