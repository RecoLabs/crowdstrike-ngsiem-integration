import json
import yaml
import base64
import requests
import copy
from pathlib import Path
from datetime import datetime, timezone
from helper import get_logger, checkpoint_get, checkpoint_save

logger = get_logger()

CONFIG_PATH = Path(__file__).parent / "config.yaml"
RECO_API_TIMEOUT_IN_SECONDS = 300
RECO_ALERT_VIEW = "ALERT_VIEW_WITH_SHARED_STATUS"
CREATED_AT_FIELD = "updated_at"
NGSIEM_OCCURRED_FORMAT = "%Y-%m-%dT%H:%M:%S.%fZ"
FILTER_RELATIONSHIP_AND = "AND"
MAX_LOG_BYTES = 500 * 1024

def load_config():
    try:
        with open(CONFIG_PATH, 'r') as f:
            config = yaml.safe_load(f)
        logger.info("Configuration loaded successfully.")
        return config
    except Exception as e:
        logger.exception(f"Failed to load config: {e}")
        raise

def create_alerts_payload(view_name, limit, after=None):
    filters = {"relationship": FILTER_RELATIONSHIP_AND, "filters": {"filters": []}}
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
                "sorts": [{"sortBy": CREATED_AT_FIELD, "sortDirection": "SORT_DIRECTION_ASC"}]
            }
        }
    }

def parse_table_row_to_dict(cells):
    result = {}
    for cell in cells:
        key = cell.get("key")
        value = cell.get("value")
        if key and value:
            try:
                result[key] = base64.b64decode(value).decode("utf-8").replace('"', '')
            except Exception:
                result[key] = value
    return result


def shrink_alert(alert_obj, max_bytes=MAX_LOG_BYTES):
    """Return a deep-copied alert where items are removed from
    `policyViolations` until the JSON size of `{"event": alert}` is
    <= max_bytes. If the alert is still too large after clearing
    `policyViolations`, the function will keep the cleared alert and
    log a warning.
    """
    candidate = copy.deepcopy(alert_obj)
    try:
        size = len(json.dumps({"event": candidate}, separators=(",",":"), ensure_ascii=False).encode("utf-8"))
    except Exception:
        return candidate

    if size <= max_bytes:
        return candidate

    pv = candidate.get("policyViolations")
    if isinstance(pv, list):
        # pop items until size fits or list is empty
        while pv and size > max_bytes:
            pv.pop()
            try:
                size = len(json.dumps({"event": candidate}, separators=(",",":"), ensure_ascii=False).encode("utf-8"))
            except Exception:
                break

    if size > max_bytes:
        logger.warning("Alert still exceeds size limit after truncating policyViolations; sending truncated alert")
        candidate["policyViolations"] = []

    return candidate

def fetch_alerts(config, after=None):
    url = f"https://{config['reco']['tenant_url']}/api/v1/policy-subsystem/alert-inbox/table"
    headers = {"Authorization": f"Bearer {config['reco']['api_key']}", "User-Agent": "NG-SIEM/1.0.0"}
    payload = create_alerts_payload(RECO_ALERT_VIEW, config['alerts']['fetch_limit'], after)

    logger.info(f"Fetching alert summaries from Reco after {after}...")
    resp = requests.put(url, json=payload, headers=headers, timeout=RECO_API_TIMEOUT_IN_SECONDS)
    if resp.status_code != 200:
        raise ValueError(f"Failed to retrieve data, status code: {resp.status_code}")

    rows = resp.json().get("getTableResponse", {}).get("data", {}).get("rows", [])
    alerts = [parse_table_row_to_dict(row.get("cells", [])) for row in rows]

    logger.info(f"Fetched {len(alerts)} alerts.")
    return alerts

def fetch_alert_details(config, alert_id):
    url = f"https://{config['reco']['tenant_url']}/api/v1/policy-subsystem/alert-inbox/{alert_id}"
    headers = {"Authorization": f"Bearer {config['reco']['api_key']}", "User-Agent": "NG-SIEM/1.0.0"}
    resp = requests.get(url, headers=headers, timeout=RECO_API_TIMEOUT_IN_SECONDS)

    if resp.status_code != 200:
        logger.error(f"Failed to fetch alert {alert_id}: {resp.status_code}")
        return None

    alert = resp.json().get("alert", {})
    alert.pop("aggregationRulesToKeys", None)

    for v in alert.get("policyViolations", []):
        try:
            decoded = json.loads(base64.b64decode(v.get("jsonData", "")))
            decoded.pop("violation", None)
            v["jsonData"] = decoded
        except Exception:
            pass

    return alert

def send_to_logscale(alerts, config):
    page_size = 500
    hec_url = config["sink"]["ngsiemurl"]
    token = config["sink"]["token"]

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "User-Agent": "NG-SIEM/1.0.0"
    }
    

    logger.info(f"Sending {len(alerts)} enriched alerts to LogScale...")
    # Ensure each event is under the size limit by shrinking if needed
    processed_alerts = [shrink_alert(a) for a in alerts]

    for i in range(0, len(processed_alerts), page_size):
        try:
            payload = '\n'.join(json.dumps({"event": log}) for log in processed_alerts[i:i+page_size])
            resp = requests.post(hec_url, headers=headers, data=payload)
            if resp.status_code not in (200, 202):
                logger.error(f"Failed to send alerts: {resp.status_code}, {resp.text}")
        except Exception as e:
            logger.exception(f"Error sending alerts to sink: {e}")

def main():
    try:
        config = load_config()

        after_str = checkpoint_get("last_alert_run_time")
        after = datetime.strptime(after_str, NGSIEM_OCCURRED_FORMAT) if after_str else None

        raw_alerts = fetch_alerts(config, after)
        enriched_alerts = []

        for alert in raw_alerts:
            try:
                decoded_id = base64.b64decode(alert.get("id")).decode("utf-8")
                full_alert = fetch_alert_details(config, decoded_id)
                if full_alert:
                    enriched_alerts.append(full_alert)
            except Exception as e:
                logger.warning(f"Skipping alert due to error: {e}")

        if enriched_alerts:
            now = datetime.now(timezone.utc).strftime(NGSIEM_OCCURRED_FORMAT)
            checkpoint_save("last_alert_run_time", now)
            logger.info(f"Saved checkpoint (last run time): {now}")

        send_to_logscale(enriched_alerts, config)
        logger.info("Alert script completed successfully.")

    except Exception:
        logger.exception("Unhandled error during alert script execution.")

if __name__ == "__main__":
    main()
