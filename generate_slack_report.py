#!/usr/bin/env python3
"""Generate a Slack message report with per-user statistics and a modern HTML output."""

import os
import argparse
import csv
import time
from collections import defaultdict, Counter
from datetime import datetime

from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from jinja2 import Template


def fetch_messages(client: WebClient, channel_id: str, max_retries: int = 3):
    """Fetch all messages from a Slack channel."""
    messages = []
    cursor = None
    while True:
        attempt = 0
        while attempt < max_retries:
            try:
                resp = client.conversations_history(channel=channel_id, cursor=cursor, limit=200)
                messages.extend(resp.get("messages", []))
                cursor = resp.get("response_metadata", {}).get("next_cursor")
                break
            except SlackApiError as e:
                if e.response.status_code == 429:
                    retry_after = int(e.response.headers.get("Retry-After", 1))
                    time.sleep(retry_after)
                    attempt += 1
                else:
                    raise
            except Exception:
                attempt += 1
                time.sleep(1)
        else:
            print(f"Failed to fetch messages from {channel_id} after {max_retries} attempts")
            break
        if not cursor:
            break
    return messages


def get_user_name(client: WebClient, user_id: str, cache: dict, max_retries: int = 3) -> str:
    """Resolve a user ID to a display name with simple caching."""
    if not user_id:
        return ""
    if user_id in cache:
        return cache[user_id]

    attempt = 0
    while attempt < max_retries:
        try:
            resp = client.users_info(user=user_id)
            profile = resp.get("user", {})
            name = (
                profile.get("profile", {}).get("display_name")
                or profile.get("real_name")
                or profile.get("name")
                or user_id
            )
            cache[user_id] = name
            return name
        except SlackApiError as e:
            if e.response.status_code == 429:
                retry_after = int(e.response.headers.get("Retry-After", 1))
                time.sleep(retry_after)
                attempt += 1
            else:
                break
        except Exception:
            attempt += 1
            time.sleep(1)
    cache[user_id] = user_id
    return user_id


def compute_stats(messages):
    """Compute per-user statistics from raw Slack messages."""
    user_counts = Counter()
    daily_counts = defaultdict(int)
    for msg in messages:
        user = msg.get("user")
        ts = msg.get("ts")
        if user:
            user_counts[user] += 1
        if ts:
            day = datetime.fromtimestamp(float(ts)).strftime("%Y-%m-%d")
            daily_counts[day] += 1
    return user_counts, daily_counts


def render_html(user_counts, daily_counts, user_map):
    """Render an HTML report using a simple CSS layout."""
    template = Template(
        """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8" />
<title>Slack Activity Report</title>
<style>
  body { font-family: Arial, sans-serif; margin: 40px; background: #f7f7f7; color: #333; }
  h1 { text-align: center; }
  table { width: 80%; margin: 20px auto; border-collapse: collapse; }
  th, td { padding: 8px 12px; border: 1px solid #ddd; text-align: left; }
  th { background: #333; color: #fff; }
  tr:nth-child(even) { background: #f2f2f2; }
  .chart { display: flex; align-items: flex-end; height: 200px; margin: 40px auto; width: 80%; }
  .bar { flex: 1; margin: 0 4px; background: #4e73df; position: relative; }
  .bar span { position: absolute; bottom: 100%; left: 0; width: 100%; text-align: center; font-size: 12px; }
</style>
</head>
<body>
<h1>Slack Activity Report</h1>
<h2>Messages by User</h2>
<table>
  <tr><th>User</th><th>Messages</th></tr>
  {% for uid, count in user_counts %}
  <tr><td>{{ user_map.get(uid, uid) }}</td><td>{{ count }}</td></tr>
  {% endfor %}
</table>
<h2>Messages by Day</h2>
<div class="chart">
{% for day, count in daily_counts %}
  <div class="bar" style="height: {{ count * 10 }}px"><span>{{ day }}</span></div>
{% endfor %}
</div>
</body>
</html>
        """
    )
    # Sort counts for display
    sorted_users = sorted(user_counts.items(), key=lambda x: x[1], reverse=True)
    sorted_days = sorted(daily_counts.items())
    return template.render(user_counts=sorted_users, daily_counts=sorted_days, user_map=user_map)


def main():
    parser = argparse.ArgumentParser(description="Generate Slack HTML report")
    parser.add_argument("--channels", nargs="+", required=True, help="Channel IDs to fetch")
    parser.add_argument("--output", required=True, help="Output HTML file")
    args = parser.parse_args()

    token = os.getenv("SLACK_TOKEN")
    if not token:
        raise EnvironmentError("SLACK_TOKEN environment variable not set")

    client = WebClient(token=token)
    user_cache = {}

    all_messages = []
    for channel in args.channels:
        for msg in fetch_messages(client, channel):
            # Resolve user name later via cache
            all_messages.append(msg)

    # Build user map and stats
    user_counts_raw, daily_counts = compute_stats(all_messages)
    user_map = {}
    for uid in user_counts_raw.keys():
        user_map[uid] = get_user_name(client, uid, user_cache)

    html = render_html(user_counts_raw, daily_counts, user_map)
    with open(args.output, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"Report written to {args.output}")


if __name__ == "__main__":
    main()
