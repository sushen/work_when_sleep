"""Persistent group queue and inactive-group file operations."""

from __future__ import annotations

import os

from .settings import GROUP_LIST_FILE, INACTIVE_GROUPS_FILE


def read_group_queue_lines(group_list_file=GROUP_LIST_FILE):
    try:
        with open(group_list_file, encoding="utf-8") as file:
            return file.read().splitlines()
    except OSError as error:
        print(f"[ERROR] Could not read group list: {error}")
        return []


def is_group_queue_entry(line):
    stripped_line = line.strip()
    return bool(stripped_line) and not stripped_line.startswith("#")


def load_group_urls(group_list_file=GROUP_LIST_FILE, log=True):
    group_urls = [
        line.strip()
        for line in read_group_queue_lines(group_list_file)
        if is_group_queue_entry(line)
    ]

    if log:
        print(f"[QUEUE] {len(group_urls)} groups loaded from {group_list_file}")

    return group_urls


def get_current_group(group_urls=None, group_list_file=GROUP_LIST_FILE):
    if group_urls is None:
        group_urls = load_group_urls(group_list_file=group_list_file, log=False)

    if not group_urls:
        return None

    return group_urls[0]


def save_group_queue(queue_lines, group_list_file=GROUP_LIST_FILE):
    temp_file = group_list_file.with_name(f"{group_list_file.name}.tmp")

    try:
        text = "\n".join(queue_lines)
        if text:
            text += "\n"

        with open(temp_file, "w", encoding="utf-8", newline="\n") as file:
            file.write(text)
            file.flush()
            os.fsync(file.fileno())

        os.replace(temp_file, group_list_file)
        return True
    except OSError as error:
        print(f"[ERROR] Could not update group queue: {error}")
        return False


def rotate_current_group(completed_group_url, group_list_file=GROUP_LIST_FILE):
    queue_lines = read_group_queue_lines(group_list_file)

    for index, line in enumerate(queue_lines):
        if not is_group_queue_entry(line):
            continue

        current_group = line.strip()
        if current_group != completed_group_url:
            print("[ERROR] Group queue changed before rotation.")
            print(f"[QUEUE] Expected current group: {completed_group_url}")
            print(f"[QUEUE] Actual current group: {current_group}")
            return False

        updated_queue = list(queue_lines)
        updated_queue.pop(index)
        updated_queue.append(current_group)

        if save_group_queue(updated_queue, group_list_file):
            print("[QUEUE] Current group moved to bottom")
            print("[QUEUE] Appended to bottom:")
            print(f"    {current_group}")
            return True

        return False

    print("[ERROR] Could not rotate queue because it is empty.")
    return False


def load_inactive_group_urls(inactive_groups_file=INACTIVE_GROUPS_FILE):
    try:
        with open(inactive_groups_file, encoding="utf-8") as file:
            return {
                line.strip()
                for line in file.read().splitlines()
                if is_group_queue_entry(line)
            }
    except FileNotFoundError:
        return set()
    except OSError as error:
        print(f"[ERROR] Could not read inactive group list: {error}")
        return set()


def append_inactive_group(group_url, inactive_groups_file=INACTIVE_GROUPS_FILE):
    inactive_urls = load_inactive_group_urls(inactive_groups_file)
    if group_url in inactive_urls:
        return True

    try:
        with open(inactive_groups_file, "a", encoding="utf-8", newline="\n") as file:
            file.write(group_url + "\n")
            file.flush()
            os.fsync(file.fileno())
        print(f"[QUEUE] Group added to inactive list: {group_url}")
        return True
    except OSError as error:
        print(f"[ERROR] Could not update inactive group list: {error}")
        return False


def move_group_to_inactive(
    group_url,
    group_list_file=GROUP_LIST_FILE,
    inactive_groups_file=INACTIVE_GROUPS_FILE,
):
    if not append_inactive_group(group_url, inactive_groups_file):
        return False

    queue_lines = read_group_queue_lines(group_list_file)
    for index, line in enumerate(queue_lines):
        if not is_group_queue_entry(line):
            continue

        current_group = line.strip()
        if current_group == group_url:
            updated_queue = list(queue_lines)
            updated_queue.pop(index)

            if save_group_queue(updated_queue, group_list_file):
                print("[QUEUE] Inactive group removed from active queue")
                return True

            return False

    print(f"[ERROR] Could not move inactive group {group_url} because it was not found in active queue.")
    return False
