# Baserow Node IP Management

This tool automatically logs the local IP into a https://baserow.io/ table. We need it because we don't have publicly routed IPs on most of our devices and didn't find a way to discover local devices in our big university network yet.

❗️ **More docs coming soon (maybe)**

Add the following to the crontab:

```cron
PATH="..."

*/2 * * * * .../baserow-node-ip-management/.venv/bin/python .../baserow-node-ip-management/run.py > .../baserow-node-ip-management/cron.log
```

It only pushes updates on: Change of network state or reboot.
