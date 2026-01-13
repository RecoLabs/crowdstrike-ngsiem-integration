import json
import yaml
import base64
import requests
from pathlib import Path
from datetime import datetime, timedelta
from helper import get_logger, checkpoint_get, checkpoint_save

logger = get_logger()

CONFIG_PATH = Path(__file__).parent / "config.yaml"
NGSIEM_OCCURRED_FORMAT = "%Y-%m-%dT%H:%M:%S.%fZ"
RECO_ACTIVE_ALERTS_VIEW = "POSTURE_CHECKLIST"
RECO_API_TIMEOUT_IN_SECONDS = 300
CREATED_AT_FIELD = "updated_at"
FILTER_RELATIONSHIP_AND = "AND"

def load_config():
    try:
        with open(CONFIG_PATH, 'r') as f:
            config = yaml.safe_load(f)
        logger.info("Configuration loaded successfully.")
        return config
    except Exception as e:
        logger.exception(f"Failed to load config: {e}")
        raise

def create_reco_payload(view_name, limit, status=None, source=None, after=None):
    filters = {"relationship": FILTER_RELATIONSHIP_AND, "filters": {"filters": []}}
    if status:
        filters["filters"]["filters"].append({"field": "status", "stringEquals": {"value": status}})
    if source:
        filters["filters"]["filters"].append({"field": "data_source", "stringEquals": {"value": source}})
    if after:
        filters["filters"]["filters"].append({
            "field": CREATED_AT_FIELD,
            "after": {"value": after.strftime(NGSIEM_OCCURRED_FORMAT)}
        })

    return {
        "getTableRequest": {
            "tableName": view_name,
            "pageSize": limit,
            "fieldFilters": filters,
            "fieldSorts": {
                "sorts": [{"sortBy": "updated_at", "sortDirection": "SORT_DIRECTION_ASC"}]
            }
        }
    }

def parse_response(response):
    if response.status_code != 200:
        raise ValueError(f"Failed to retrieve data, status code: {response.status_code}")
    rows = response.json().get("getTableResponse", {}).get("data", {}).get("rows", [])
    return [parse_table_row_to_dict(row.get("cells", [])) for row in rows]


def parse_table_row_to_dict(cells):
    alert_dict = {}
    for cell in cells:
        key = cell.get("key")
        value = cell.get("value")
        if key and value:
            try:
                decoded = base64.b64decode(value).decode("utf-8").replace('"', "")
                alert_dict[key] = decoded
            except Exception:
                alert_dict[key] = value
    return alert_dict

def fetch_alerts(config, after=None):
    try:
        url = f"https://{config['reco']['tenant_url']}/api/v1/policy-subsystem/alert-inbox/table"
        headers = {"Authorization": f"Bearer {config['reco']['api_key']}", "User-Agent": "NG-SIEM/1.0.0"}
        payload = create_reco_payload(
            RECO_ACTIVE_ALERTS_VIEW,
            config['posture']['fetch_limit'],
            status=None,
            source=None,
            after=after
        )

        logger.info(f"Fetching alerts from Reco API after {after}...")
        resp = requests.put(url, json=payload, headers=headers, timeout=RECO_API_TIMEOUT_IN_SECONDS)
        alerts = parse_response(resp)
        logger.info(f"Fetched {len(alerts)} alerts from Reco.")

        for alert in alerts:
            try:
                alert["alert_id"] = base64.b64decode(alert.get("alert_id")).decode("utf-8")
                alert["all_policy"] = None
                alert["instance_id"] = base64.b64decode(alert.get("instance_id")).decode("utf-8")
            except Exception:
                continue
        return alerts

    except Exception as e:
        logger.exception(f"Error while fetching alerts: {e}")
        return []

def send_to_sink(alerts, config):
    page_size = 500
    hec_url = config["sink"]["ngsiemurl"]
    token = config["sink"]["token"]

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "User-Agent": "NG-SIEM/1.0.0"
    }

    logger.info(f"Sending {len(alerts)} alerts to sink...")
    for i in range(0, len(alerts), page_size):
        try:
            payload = '\n'.join(json.dumps({"event": log}) for log in alerts[i:i+page_size])
            resp = requests.post(hec_url, headers=headers, data=payload)
            if resp.status_code not in (200, 202):
                logger.error(f"Failed to send alert: {resp.status_code}, {resp.text}")
        except Exception as e:
            logger.exception(f"Exception while sending alert: {e}")

def main():
    try:
        config = load_config()

        after_str = checkpoint_get("last_updated_at")
        after = datetime.strptime(after_str, NGSIEM_OCCURRED_FORMAT) if after_str else None

        alerts = fetch_alerts(config, after=after)
        send_to_sink(alerts, config)

        if alerts:
            latest = max(
                a["updated_at"] for a in alerts if "updated_at" in a
            )
            latest_dt = datetime.strptime(latest, "%Y-%m-%dT%H:%M:%S.%fZ")
            checkpoint_save("last_updated_at", (latest_dt + timedelta(seconds=1)).strftime("%Y-%m-%dT%H:%M:%S.%fZ"))
            logger.info(f"Saved checkpoint: {latest}")

        logger.info("Script completed successfully.")
    except Exception:
        logger.exception("Script failed due to an unhandled exception.")

if __name__ == "__main__":
    main()
