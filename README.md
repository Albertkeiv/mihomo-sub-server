# Mihomo sub server
Mihomo Subscription Server

Small Python 3 subscription server for Mihomo. It reads `config.yaml` at
startup and serves one configured Mihomo YAML file per user through that
user's secret URL.

## Configuration

```yaml
somebody:
  url_prefix: "/secret_path/secret_key"
  config: "/configs/somebody.yaml"
```

- `url_prefix` is the exact HTTP path used to fetch the subscription.
- `config` is the path to the Mihomo YAML file inside the container.
- Changes to `config.yaml` or subscription files require a container restart.

## Docker Compose

```powershell
docker compose up --build
```

The default compose file exposes the server on `http://localhost:8080` and
mounts:

- `./config.yaml` to `/app/config.yaml`
- `./configs` to `/configs`

Fetch the example subscription:

```powershell
curl http://localhost:8080/secret_path/secret_key
```

Health check:

```powershell
curl http://localhost:8080/healthz
```

## Local tests

```powershell
pip install -r requirements.txt
pytest
```
