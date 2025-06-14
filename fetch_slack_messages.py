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


def get_user_name(client: WebClient, user_id: str, cache: dict, max_retries: int = 3) -> str:
    """Resolve a user ID to a user name with simple caching and retries."""
    if not user_id:
        return ""
    if user_id in cache:
        return cache[user_id]

    retries = 0
    while retries < max_retries:
        try:
            response = client.users_info(user=user_id)
            profile = response.get("user", {})
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
                retries += 1
            else:
                break
        except Exception:
            retries += 1
            time.sleep(1)

    cache[user_id] = user_id
    return user_id


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
        user_cache = {}
        for channel_id in args.channels:
            try:
                for msg in fetch_messages(client, channel_id):
                    user_name = get_user_name(client, msg.get("user"), user_cache)
                    writer.writerow(
                        {
                            "channel": channel_id,
                            "ts": msg.get("ts"),
                            "user": user_name,
                            "text": msg.get("text", "").replace("\n", " "),
                        }
                    )
            except SlackApiError as e:
                print(f"Failed to fetch channel {channel_id}: {e}")


if __name__ == "__main__":
    main()
