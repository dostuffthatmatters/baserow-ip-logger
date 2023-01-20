import json
import os
import re
import sys
import subprocess
import time
from typing import Optional
from pydantic import BaseModel
import requests

CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
STATE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "state.json")


class Config(BaseModel):
    node_identifier: str
    db_token: str
    db_table_id: str
    db_node_identifier_field_id: str
    seconds_between_updates: float


class State(BaseModel):
    node_identifier: str
    local_ip: str
    public_ip: str
    last_update_time: float


def run_shell_command(command: str, working_directory: Optional[str] = None) -> str:
    p = subprocess.run(
        command,
        shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=working_directory,
        env=os.environ.copy(),
    )
    stdout = p.stdout.decode("utf-8", errors="replace")
    stderr = p.stderr.decode("utf-8", errors="replace")

    error_message = (
        f"command '{command}' failed with exit code "
        + f"{p.returncode}: stderr = '{stderr}'"
    )
    if p.returncode != 0:
        print(error_message)
    assert p.returncode == 0, error_message
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
        print(f"interface_names = {interface_names}")
        local_interface_ips: list[str] = []
        for interface_name in interface_names:
            if not any([s in interface_name for s in ["en", "eth", "wlan"]]):
                print(f"skipping interface '{interface_name}'")
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


def get_public_ip() -> str:
    response = requests.get("http://checkip.dyndns.com/")
    ip_address_matches = re.compile(r"\d+\.\d+\.\d+\.\d+").findall(response.text)
    assert len(ip_address_matches) == 1
    return ip_address_matches[0]


def create_row(config: Config, new_local_ip: str, new_public_ip: str) -> list[int]:
    response = requests.post(
        f"https://api.baserow.io/api/database/rows/table/{config.db_table_id}/?user_field_names=true",
        headers={
            "Authorization": f"Token {config.db_token}",
            "Content-Type": "application/json",
        },
        json={
            "node-identifier": config.node_identifier,
            "local-ip-address": new_local_ip,
            "public-ip-address": new_public_ip,
        },
    )
    assert response.status_code == 200, f"response failed: {response.json()}"


if __name__ == "__main__":
    # load config from "config.json"
    with open(CONFIG_PATH) as f:
        config = Config(**json.load(f))

    # load old entry
    old_node_identifier: Optional[str] = None
    old_local_ip: Optional[str] = None
    old_public_ip: Optional[str] = None
    last_update_time = 0
    if os.path.isfile(STATE_PATH):
        with open(STATE_PATH) as f:
            state = State(**json.load(f))
            old_node_identifier = state.node_identifier
            old_local_ip = state.local_ip
            old_public_ip = state.public_ip
            last_update_time = state.last_update_time

    # determine new entry
    new_node_identifier = config.node_identifier
    new_local_ip = get_local_ip()
    new_public_ip = get_public_ip()
    now = time.time()

    # abort when nothing has changed -> no network requests
    if all(
        [
            old_node_identifier == new_node_identifier,
            old_local_ip == new_local_ip,
            old_public_ip == new_public_ip,
        ]
    ):
        print("nothing has changed")
        if now < (last_update_time + config.seconds_between_updates):
            print("exiting due to recent update")
            exit(0)
        else:
            print("renewing old entry")

    # get list of outdated entries
    existing_row_ids = get_existing_row_ids(config)
    print(f"old row ids: {existing_row_ids}")

    # add new entry
    create_row(config, new_local_ip, new_public_ip)

    # remove existing rows after successful update
    delete_row_ids(config, existing_row_ids)

    # save new entry
    with open(STATE_PATH, "w") as f:
        json.dump(
            State(
                node_identifier=new_node_identifier,
                local_ip=new_local_ip,
                public_ip=new_public_ip,
                last_update_time=now
            ).dict(),
            f,
            indent=4,
        )
