import pandas as pd
import argparse

def filter_sample_file(input_file, nc_file, unique_reads_threshold, output_file):
    # Read NC.csv file and extract the list of taxIDs
    nc_taxids = pd.read_csv(nc_file, header=None, names=["taxID"])["taxID"].tolist()
    
    # Read the Sample.tsv file
    sample_data = pd.read_csv(input_file, sep="\t")
    
    # Filter out rows where taxID is in NC.csv
    filtered_data = sample_data[~sample_data["taxID"].isin(nc_taxids)]
    
    # Filter out rows where numUniqueReads is less than the threshold
    filtered_data = filtered_data[filtered_data["numUniqueReads"] >= unique_reads_threshold]
    
    # Write the filtered data to the output file in TSV format
    filtered_data.to_csv(output_file, sep="\t", index=False)

def main():
    # Set up argument parsing
    parser = argparse.ArgumentParser(description="Filter a Sample.tsv file based on NC.csv and numUniqueReads threshold.")
    parser.add_argument("--i", required=True, help="Input Sample.tsv file")
    parser.add_argument("--nc", required=True, help="Input NC.csv file containing taxIDs to exclude")
    parser.add_argument("--unique", type=int, required=True, help="Minimum value for numUniqueReads")
    parser.add_argument("--o", required=True, help="Output file for filtered data (TSV format)")
    args = parser.parse_args()
    
    # Run the filtering function
    filter_sample_file(args.i, args.nc, args.unique, args.o)

if __name__ == "__main__":
    main()

