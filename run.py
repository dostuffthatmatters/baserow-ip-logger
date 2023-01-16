import json
import os
import subprocess
from typing import Optional
from pydantic import BaseModel
import requests

CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")


class Config(BaseModel):
    node_identifier: str
    db_token: str
    db_table_id: str
    get_local_ip_command: str
    get_public_ip_command: str


def run_shell_command(command: str, working_directory: Optional[str] = None) -> str:
    p = subprocess.run(
        command,
        shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=working_directory,
    )
    stdout = p.stdout.decode("utf-8", errors="replace")
    stderr = p.stderr.decode("utf-8", errors="replace")

    assert p.returncode == 0, (
        f"command '{command}' failed with exit code "
        + f"{p.returncode}: stderr = '{stderr}'"
    )
    return stdout.strip()


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


def create_row(config: Config) -> list[int]:
    response = requests.post(
        f"https://api.baserow.io/api/database/rows/table/{config.db_table_id}/?user_field_names=true",
        headers={
            "Authorization": f"Token {config.db_token}",
            "Content-Type": "application/json",
        },
        json={
            "node-identifier": config.node_identifier,
            "local-ip-address": run_shell_command(config.get_local_ip_command),
            "public-ip-address": run_shell_command(config.get_public_ip_command),
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
