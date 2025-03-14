from Bio import Entrez
import pandas as pd
import os

print("Use this tool to fetch list of Reference Sequences from NCBI based on TaxID")
print("Tool Compiled using Bio.Entrez ; Dr. Varun CN; NIMHANS")

# Need Entrez registered API Key to get uninterrupted download
Entrez.email = input("Entrez API Key: ")

# file input and output and checks
csv_file = input("Path to .CSV file containing list of TaxIDs: ")
output_dir = input("Directory where all the References are to be stored: ")  # Directory to save FASTA files
os.makedirs(output_dir, exist_ok=True)

df = pd.read_csv(csv_file)
tax_ids = df['tax_id'].tolist()  # Replace 'tax_id' with the actual column name

# Main Function: Fetch
def fetch_fasta(tax_id):
    try:
        search_handle = Entrez.esearch(db="nuccore", term=f"txid{tax_id}[Organism] AND refseq[filter]", retmax=1)
        search_results = Entrez.read(search_handle)
        search_handle.close()
        if search_results['IdList']:
            sequence_id = search_results['IdList'][0]
            fetch_handle = Entrez.efetch(db="nuccore", id=sequence_id, rettype="fasta", retmode="text")
            fasta_data = fetch_handle.read()
            fetch_handle.close()
            return fasta_data
        else:
            print(f"No sequences found for Taxonomy ID: {tax_id}")
            return None
    except Exception as e:
        print(f"Error fetching Taxonomy ID {tax_id}: {e}")
        return None

# Download FASTA and iterate over the list
for tax_id in tax_ids:
    print(f"Processing Taxonomy ID: {tax_id}")
    fasta_content = fetch_fasta(tax_id)
    if fasta_content:
        file_path = os.path.join(output_dir, f"{tax_id}.fasta")
        with open(file_path, "w") as f:
            f.write(fasta_content)
        print(f"Saved: {file_path}")
    else:
        print(f"Skipped: {tax_id}")

print("Download completed!!!")
