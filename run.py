import json
import os
import re
import sys
import subprocess
from typing import Optional
from pydantic import BaseModel
import requests

CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")


class Config(BaseModel):
    node_identifier: str
    db_token: str
    db_table_id: str
    db_node_identifier_field_id: str


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
        + f"{config.db_node_identifier_field_id}__equal={config.node_identifier}",
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


def get_pulic_ip() -> str:
    response = requests.get("http://checkip.dyndns.com/")
    ip_address_matches = re.compile(r"\d+\.\d+\.\d+\.\d+").findall(response.text)
    assert len(ip_address_matches) == 1
    return ip_address_matches[0]


def get_local_ip() -> str:
    if sys.platform == "darwin":
        interface_names = run_shell_command("ipconfig getiflist").split(" ")
        local_interface_ips: list[str] = []
        for interface_name in interface_names:
            try:
                local_interface_ip = run_shell_command(
                    f"ipconfig getifaddr {interface_name}"
                )
                local_interface_ips.append(f"{interface_name}: {local_interface_ip}")
            except:
                pass
        return "; ".join(local_interface_ips)
    elif sys.platform == "linux":
        interface_names = (
            run_shell_command("ls /sys/class/net")
            .replace("\n", " ")
            .replace("\t", " ")
            .split(" ")
        )
        local_interface_ips: list[str] = []
        for interface_name in interface_names:
            if ("en" not in interface_name) and ("wlan" not in interface_name):
                continue
            try:
                local_interface_config = run_shell_command(f"ifconfig {interface_name}")
                ip_matches = re.compile(r"inet\s+\d+\.\d+\.\d+\.\d+").findall(
                    local_interface_config
                )
                assert len(ip_matches) == 1
                local_interface_ips.append(
                    f"{interface_name}: {ip_matches[0].replace('inet ', '')}"
                )
            except:
                pass
        return "; ".join(local_interface_ips)
    else:
        return "unknown"


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
            "public-ip-address": get_pulic_ip(),
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
