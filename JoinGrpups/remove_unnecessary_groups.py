# remove_not_relevant.py

def remove_lines(groups_file, not_relevant_file, output_file):
    # Load not relevant lines into a set for fast lookup
    with open(not_relevant_file, "r", encoding="utf-8") as f:
        not_relevant = set(line.strip() for line in f if line.strip())

    # Filter groups list while preserving order
    with open(groups_file, "r", encoding="utf-8") as f:
        groups = [line.strip() for line in f if line.strip()]

    filtered = [line for line in groups if line not in not_relevant]

    # Save the result
    with open(output_file, "w", encoding="utf-8") as f:
        for line in filtered:
            f.write(line + "\n")

    print(f"Filtered list saved to {output_file}")


if __name__ == "__main__":
    remove_lines("groups_list.txt", "programmers_groups.txt", "filtered_groups_list.txt")
