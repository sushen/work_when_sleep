def remove_duplicates(input_file, output_file):
    seen = set()
    unique_lines = []

    # Read input file
    with open(input_file, "r", encoding="utf-8") as f:
        for line in f:
            stripped = line.strip()
            if stripped and stripped not in seen:
                unique_lines.append(stripped)
                seen.add(stripped)

    # Write output file
    with open(output_file, "w", encoding="utf-8") as f:
        f.write("\n".join(unique_lines))

    print(f"Deduplicated list saved to: {output_file}")


if __name__ == "__main__":
    input_path = "groups_list.txt"          # replace with your input file path
    output_path = "groups_list_unique.txt"  # replace with your desired output file path
    remove_duplicates(input_path, output_path)
