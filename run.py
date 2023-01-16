import json
import os
import sys
from pydantic import BaseModel
import requests

CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")


class Config(BaseModel):
    node_identifier: str
    db_token: str
    db_table_id: str


def get_existing_row_ids(config: Config) -> list[int]:
    response = requests.get(
        f"https://api.baserow.io/api/database/rows/table/"
        + f"{config.db_table_id}/?user_field_names=true&filter__"
        + f"node-identifier__equal={config.node_identifier}",
        headers={"Authorization": f"Token {config.db_token}"},
    )
    assert response.status_code == 200, f"response failed: {response.json()}"
    return [r["id"] for r in response.json()["results"]]


def delete_row_ids(config: Config, row_ids: list[int]) -> list[int]:
    response = requests.post(
        f"https://api.baserow.io/api/database/rows/table/{config.db_table_id}/batch-delete/",
        headers={
            "Authorization": f"Token {config.db_token}",
            "Content-Type": "application/json",
        },
        json={"items": row_ids},
    )
    assert response.status_code == 204, f"response failed: {response.json()}"


def get_local_ip() -> str:
    return "something_local"


def get_public_ip() -> str:
    return "something_public"


def create_row(config: Config) -> list[int]:
    response = requests.post(
        f"https://api.baserow.io/api/database/rows/table/{config.db_table_id}/?user_field_names=true",
        headers={
            "Authorization": f"Token {config.db_token}",
            "Content-Type": "application/json",
        },
        json={
            "node-identifier": config.node_identifier,
            "local-ip-address": get_local_ip(),
            "public-ip-address": get_public_ip(),
        },
    )
    assert response.status_code == 200, f"response failed: {response.json()}"


if __name__ == "__main__":
    # load config from "config.json"
    with open(CONFIG_PATH) as f:
        config = Config(**json.load(f))

    # get list of outdated entries
    existing_row_ids = get_existing_row_ids(config)

    # add new entry
    create_row(config)

    # remove existing rows after successful update
    delete_row_ids(config, existing_row_ids)
