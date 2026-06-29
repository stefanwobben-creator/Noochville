#!/bin/bash
# Haal actuele data van de server
echo "=== Download van server ==="
scp root@138.201.154.162:/opt/noochville/data/governance_records.json data/governance_records.json
scp root@138.201.154.162:/opt/noochville/data/assignments.json data/assignments.json
scp root@138.201.154.162:/opt/noochville/data/personas.json data/personas.json
scp root@138.201.154.162:/opt/noochville/data/people.json data/people.json
scp root@138.201.154.162:/opt/noochville/data/projects.json data/projects.json
echo "=== Klaar. Lokale data is nu in sync met server ==="
