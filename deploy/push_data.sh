#!/bin/bash
# Push actuele data naar server
echo "=== Upload naar server ==="
scp data/governance_records.json root@138.201.154.162:/opt/noochville/data/
scp data/assignments.json root@138.201.154.162:/opt/noochville/data/
scp data/personas.json root@138.201.154.162:/opt/noochville/data/
scp data/people.json root@138.201.154.162:/opt/noochville/data/
ssh root@138.201.154.162 "chown -R nooch:nooch /opt/noochville/data/ && systemctl restart noochville-cockpit2"
echo "=== Klaar ==="
