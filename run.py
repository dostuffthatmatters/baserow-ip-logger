import datetime
import json
import os
import re
import sys
import subprocess
from typing import Optional
from pydantic import BaseModel
import requests

CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
STATE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "state.json")


class Config(BaseModel):
    db_token: str
    db_table_id: str
    db_node_identifier_field_id: str


class State(BaseModel):
    local_ip: str
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


def get_existing_row_ids(config: Config, hostname: str) -> list[int]:
    response = requests.get(
        f"https://api.baserow.io/api/database/rows/table/"
        + f"{config.db_table_id}/?user_field_names=true&filter__"
        + f"{config.db_node_identifier_field_id}__equal={hostname}",
        headers={"Authorization": f"Token {config.db_token}"},
    )
    assert response.status_code == 200, f"response failed: {response.json()}"
    return [r["id"] for r in response.json()["results"]]


def delete_row_ids(config: Config, row_ids: list[int]) -> None:
    if len(row_ids) == 0:
        return

    response = requests.post(
        f"https://api.baserow.io/api/database/rows/table/{config.db_table_id}/batch-delete/",
        headers={
            "Authorization": f"Token {config.db_token}",
            "Content-Type": "application/json",
        },
        json={"items": row_ids},
    )
    assert response.status_code == 204, f"response failed: {response.json()}"


def get_interface_names() -> list[str]:
    if sys.platform == "darwin":
        return run_shell_command("ipconfig getiflist").split(" ")
    elif sys.platform == "linux":
        return (
            run_shell_command("ls /sys/class/net")
            .replace("\n", " ")
            .replace("\t", " ")
            .split(" ")
        )
    else:
        raise Exception("not working on windows")


def get_interface_ip(interface_name: str) -> Optional[str]:
    if sys.platform == "darwin":
        try:
            return run_shell_command(f"ipconfig getifaddr {interface_name}")
        except:
            return None
    elif sys.platform == "linux":
        try:
            local_interface_config = run_shell_command(f"ifconfig {interface_name}")
            ip_matches = re.compile(r"inet\s+\d+\.\d+\.\d+\.\d+").findall(
                local_interface_config
            )
            assert len(ip_matches) == 1
            return ip_matches[0].replace("inet ", "")
        except:
            return None
    else:
        raise Exception("not working on windows")


def get_local_ip() -> str:
    interface_names = get_interface_names()
    interface_ips = [get_interface_ip(n) for n in interface_names]
    ip_strings = [
        f"{n}: {i}" for n, i in zip(interface_names, interface_ips) if i is not None
    ]
    if len(ip_strings) == 0:
        return "no network"
    else:
        return "; ".join(ip_strings)


def get_hostname() -> str:
    raw_hostname = run_shell_command("hostname")
    if "." in raw_hostname:
        return raw_hostname.split(".")[0]
    else:
        return raw_hostname


def get_seconds_since_boot() -> float:
    if sys.platform == "darwin":
        last_reboot_string = (
            run_shell_command("last reboot | head -n 1")
            .replace("\t", " ")
            .replace("  ", " ")
            .strip()
            .split(" ")[-4:]
        )
        last_reboot_string = last_reboot_string[:8]
        now = datetime.datetime.now()
        last_reboot_time = datetime.datetime.strptime(
            f"{now.year} {last_reboot_string[0]} {last_reboot_string[1]} {last_reboot_string[2].zfill(2)} {last_reboot_string[3]}",
            "%Y %a %b %d %H:%M",
        )
        seconds_since_reboot = (now - last_reboot_time).total_seconds()
        if seconds_since_reboot < 0:
            seconds_since_reboot += 365.25 * 24 * 3600
        return seconds_since_reboot
    elif sys.platform == "linux":
        return float(run_shell_command("awk '{print $1}' /proc/uptime"))
    else:
        raise Exception("not working on windows")


def create_row(config: Config, new_local_ip: str, hostname: str) -> None:
    response = requests.post(
        f"https://api.baserow.io/api/database/rows/table/{config.db_table_id}/?user_field_names=true",
        headers={
            "Authorization": f"Token {config.db_token}",
            "Content-Type": "application/json",
        },
        json={
            "node-identifier": hostname,
            "local-ip-address": new_local_ip,
            "public-ip-address": "-",
        },
    )
    assert response.status_code == 200, f"response failed: {response.json()}"


if __name__ == "__main__":
    print(f"running at {datetime.datetime.now()}")

    # load config from "config.json"
    with open(CONFIG_PATH) as f:
        config = Config(**json.load(f))

    # load old entry
    old_local_ip: Optional[str] = None
    last_update_time: float = 0
    if os.path.isfile(STATE_PATH):
        with open(STATE_PATH) as f:
            state = State(**json.load(f))
            old_local_ip = state.local_ip
            last_update_time = state.last_update_time

    # detect changes or reboots
    now = datetime.datetime.now()
    seconds_since_reboot = get_seconds_since_boot()

    new_local_ip = get_local_ip()
    ip_has_changed = old_local_ip != new_local_ip
    reboot_happened = (now.timestamp() - last_update_time) > seconds_since_reboot
    print(f"new_local_ip = {new_local_ip}")
    print(f"ip_has_changed = {ip_has_changed}")
    print(f"reboot_happened = {reboot_happened}")

    if (not ip_has_changed) and (not reboot_happened):
        print("nothing to update, exiting")
        exit(0)

    hostname = get_hostname()

    # get list of outdated entries
    existing_row_ids = get_existing_row_ids(config, hostname)
    print(f"old row ids: {existing_row_ids}")

    # add new entry
    create_row(config, new_local_ip, hostname)

    # remove existing rows after successful update
    delete_row_ids(config, existing_row_ids)

    # save new entry
    with open(STATE_PATH, "w") as f:
        json.dump(
            State(
                local_ip=new_local_ip,
                last_update_time=now.timestamp(),
            ).dict(),
            f,
            indent=4,
        )
