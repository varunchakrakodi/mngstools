import pandas as pd
import argparse

def filter_tab_file(input_file, output_file, pident_threshold, exclude_staxids_file):
    # Read the tab-delimited file into a pandas DataFrame
    columns = ["qseqid", "sseqid", "pident", "length", "mismatch", "qstart", "qend", 
               "sstart", "send", "evalue", "bitscore", "staxids", "sscinames"]
    df = pd.read_csv(input_file, sep="\t", names=columns, dtype=str)

    # Convert pident to float for comparison
    df["pident"] = pd.to_numeric(df["pident"], errors="coerce")

    # Remove rows where pident is less than the user-defined threshold
    df = df[df["pident"] >= pident_threshold]

    # Remove rows where staxids is blank
    df = df[df["staxids"].notnull() & (df["staxids"].str.strip() != "")]

    # Keep only the first entry in staxids if there are multiple entries separated by a ";"
    df["staxids"] = df["staxids"].str.split(";").str[0]

    # Read the exclude_staxids file and create a set of staxids to exclude
    with open(exclude_staxids_file, 'r') as f:
        exclude_staxids = set(f.read().splitlines())

    # Remove rows where staxids match any in the exclude_staxids set
    df = df[~df["staxids"].isin(exclude_staxids)]

    # Save the filtered DataFrame to the output file
    df.to_csv(output_file, sep="\t", index=False, header=False)

    # Extract unique staxids from the original file and save to a new file
    unique_staxids = pd.read_csv(input_file, sep="\t", names=columns, usecols=[11], dtype=str)
    unique_staxids["staxids"] = unique_staxids["staxids"].str.split(";").str[0]
    unique_staxids = unique_staxids["staxids"].dropna().drop_duplicates()
    unique_staxids.to_csv("unique_staxids.txt", index=False, header=False)

def main():
    parser = argparse.ArgumentParser(description="Filter tab-delimited file based on pident and staxids criteria.")
    parser.add_argument("--input_file", required=True, help="Path to the input tab-delimited file.")
    parser.add_argument("--output_file", required=True, help="Path to the output filtered file.")
    parser.add_argument("--pident_threshold", type=float, required=True, help="Minimum pident threshold for filtering.")
    parser.add_argument("--exclude_staxids_file", required=True, help="Path to the file containing staxids to exclude.")

    args = parser.parse_args()

    filter_tab_file(args.input_file, args.output_file, args.pident_threshold, args.exclude_staxids_file)

if __name__ == "__main__":
    main()

