# Influx Quickstart

Local runbook for this repo:

- install InfluxDB 3 locally with Ansible
- start the local server
- create the local auth token
- replay `data/prod/*.json` into InfluxDB
- query the replayed data
- open the Explorer UI

For remote manager or full swarm flows, use [HOW_TO_RUN.md](HOW_TO_RUN.md).

## 1. Install Influx Locally

```bash
ansible-playbook -i ansible_swarm_setup/inventory.local.ini ansible_swarm_setup/install_influxdb.yml
```

This installs the local binary only. It does not start the server.

## 2. Start the Local Server

```bash
mkdir -p ~/.influxdb/logs
nohup ~/.influxdb/influxdb3 serve --node-id localhost --http-bind 0.0.0.0:8181 --object-store file --data-dir ~/.influxdb/data > ~/.influxdb/logs/influxdb3.log 2>&1 &
```

Useful checks:

```bash
~/.influxdb/influxdb3 --version
lsof -nP -iTCP:8181 -sTCP:LISTEN
tail -f ~/.influxdb/logs/influxdb3.log
```

A successful start ends with a log line that includes `address=0.0.0.0:8181`.

## 3. Create and Export the Token

Run this once for a fresh local instance:

```bash
~/.influxdb/influxdb3 create token --admin --host http://127.0.0.1:8181
```

Export the returned token into your shell:

```bash
export INFLUXDB3_AUTH_TOKEN=<your_token>
```

Verify the token works:

```bash
~/.influxdb/influxdb3 show databases --host http://127.0.0.1:8181 --token "$INFLUXDB3_AUTH_TOKEN"
```

## 4. Replay `data/prod` into InfluxDB

The replay script writes into database `prod_replay` and table `prod_sensor_events` unless you override the defaults.

Run a short smoke test first:

```bash
python scripts/influx_json_replay.py --host http://127.0.0.1:8181 --database prod_replay --events-per-second 10 --max-events 10
```

Run the long-lived replay with an interactive events-per-second prompt:

```bash
python scripts/influx_json_replay.py --host http://127.0.0.1:8181 --database prod_replay
```

Run the long-lived replay at a fixed rate:

```bash
python scripts/influx_json_replay.py --host http://127.0.0.1:8181 --database prod_replay --events-per-second 500
```

Stop the replay with `Ctrl+C`.

## 5. Query the Replayed Data

Set the database once for the current shell:

```bash
export INFLUXDB3_DATABASE_NAME=prod_replay
```

List databases:

```bash
~/.influxdb/influxdb3 show databases --host http://127.0.0.1:8181 --token "$INFLUXDB3_AUTH_TOKEN"
```

List tables:

```bash
~/.influxdb/influxdb3 query --host http://127.0.0.1:8181 --token "$INFLUXDB3_AUTH_TOKEN" --database "$INFLUXDB3_DATABASE_NAME" "SHOW TABLES"
```

List columns in the replay table:

```bash
~/.influxdb/influxdb3 query --host http://127.0.0.1:8181 --token "$INFLUXDB3_AUTH_TOKEN" --database "$INFLUXDB3_DATABASE_NAME" "SHOW COLUMNS IN prod_sensor_events"
```

Fetch the latest 10 rows:

```bash
~/.influxdb/influxdb3 query --host http://127.0.0.1:8181 --token "$INFLUXDB3_AUTH_TOKEN" --database "$INFLUXDB3_DATABASE_NAME" "SELECT * FROM prod_sensor_events ORDER BY time DESC LIMIT 10"
```

Count rows:

```bash
~/.influxdb/influxdb3 query --host http://127.0.0.1:8181 --token "$INFLUXDB3_AUTH_TOKEN" --database "$INFLUXDB3_DATABASE_NAME" "SELECT COUNT(normal_value_raw) AS row_count FROM prod_sensor_events"
```

Check recent writes:

```bash
~/.influxdb/influxdb3 query --host http://127.0.0.1:8181 --token "$INFLUXDB3_AUTH_TOKEN" --database "$INFLUXDB3_DATABASE_NAME" "SELECT time, location_name, device_name, sensor_name, normal_value_raw FROM prod_sensor_events WHERE time >= now() - INTERVAL '5 minutes' ORDER BY time DESC LIMIT 20"
```

## 6. Open the Explorer UI

If the container already exists:

```bash
docker start influxdb3-explorer
```

If you want a clean local UI container:

```bash
docker rm -f influxdb3-explorer
docker run --detach \
  --name influxdb3-explorer \
  --publish 8888:80 \
  influxdata/influxdb3-ui:1.6.2 \
  --mode=admin
```

Open:

```text
http://localhost:8888
```

Use these connection settings:

- Server URL: `http://host.docker.internal:8181`
- Token: `INFLUXDB3_AUTH_TOKEN`
- Database: `prod_replay`

Do not use `http://localhost:8181` inside Explorer for this setup. Explorer runs in Docker, while InfluxDB is running natively on your machine.

## 7. If Explorer Shows `500 /api/server-config`

That usually means Explorer is trying to reach the wrong host or it is holding stale saved configuration.

Use this fix:

```bash
docker rm -f influxdb3-explorer
docker run --detach \
  --name influxdb3-explorer \
  --publish 8888:80 \
  influxdata/influxdb3-ui:1.6.2 \
  --mode=admin
```

Then reconnect with:

- Server URL: `http://host.docker.internal:8181`
- Token: `INFLUXDB3_AUTH_TOKEN`
- Database: `prod_replay`

## 8. Optional: Recover a Lost Token

Stop the local server:

```bash
pkill -f 'influxdb3 serve'
```

Restart with the recovery endpoint enabled:

```bash
mkdir -p ~/.influxdb/logs
nohup ~/.influxdb/influxdb3 serve --node-id localhost --http-bind 0.0.0.0:8181 --admin-token-recovery-http-bind 127.0.0.1:8182 --object-store file --data-dir ~/.influxdb/data > ~/.influxdb/logs/influxdb3.log 2>&1 &
```

Regenerate the admin token:

```bash
~/.influxdb/influxdb3 create token --admin --regenerate --host http://127.0.0.1:8182
```

Export the new token:

```bash
export INFLUXDB3_AUTH_TOKEN=<new_token>
```

## 9. Optional: Stop the Local Server

```bash
pkill -f 'influxdb3 serve'
```
