Add the following to the crontab:

```cron
PATH="..."

*/2 * * * * /home/pi/Documents/baserow-node-ip-management/.venv/bin/python /home/pi/Documents/baserow-node-ip-management/run.py > /home/pi/Documents/baserow-node-ip-management/cron.log
```

Push update on:

1. Change of network state
2. Reboot
