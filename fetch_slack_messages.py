#!/usr/bin/env python3
"""Fetch messages from Slack channels and write them to a CSV file."""

import os
import csv
import time
import argparse

from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError


def fetch_messages(client: WebClient, channel_id: str, max_retries: int = 3):
    """Fetch all messages from a channel using cursor-based pagination."""
    messages = []
    cursor = None
    while True:
        attempt = 0
        while attempt < max_retries:
            try:
                response = client.conversations_history(
                    channel=channel_id,
                    cursor=cursor,
                    limit=200,
                )
                messages.extend(response.get("messages", []))
                cursor = response.get("response_metadata", {}).get("next_cursor")
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


def main():
    parser = argparse.ArgumentParser(description="Fetch Slack channel messages to CSV")
    parser.add_argument(
        "--channels",
        nargs="+",
        required=True,
        help="Channel IDs to fetch messages from",
    )
    parser.add_argument(
        "--output",
        required=True,
        help="Path to output CSV file",
    )
    args = parser.parse_args()

    token = os.getenv("SLACK_TOKEN")
    if not token:
        raise EnvironmentError("SLACK_TOKEN environment variable not set")

    client = WebClient(token=token)

    with open(args.output, "w", newline="", encoding="utf-8") as csvfile:
        fieldnames = ["channel", "ts", "user", "text"]
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        for channel_id in args.channels:
            try:
                for msg in fetch_messages(client, channel_id):
                    writer.writerow(
                        {
                            "channel": channel_id,
                            "ts": msg.get("ts"),
                            "user": msg.get("user"),
                            "text": msg.get("text", "").replace("\n", " "),
                        }
                    )
            except SlackApiError as e:
                print(f"Failed to fetch channel {channel_id}: {e}")


if __name__ == "__main__":
    main()
