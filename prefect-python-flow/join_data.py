import sys
from pathlib import Path
from memory_profiler import profile
import polars as pl

@profile(stream=sys.stdout)
def join_data(original_file_path, filtered_ids_path, output_file_path, original_file_limit=100_000_000):
    print(f"Starting data joining. Reading up to {original_file_limit} records from {original_file_path}")

    original_path = Path(original_file_path)
    filtered_path = Path(filtered_ids_path)
    output_path = Path(output_file_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Read original data (limited by original_file_limit)
    df_original = pl.read_parquet(original_path, n_rows=original_file_limit)
    print(f"Loaded {df_original.shape[0]} records from original file for joining.")

    # Read filtered data
    df_filtered = pl.read_parquet(filtered_path)
    print(f"Loaded {df_filtered.shape[0]} records from filtered file.")

    # Perform join operation using Polars
    # Assumes 'id' column exists in both DataFrames
    df_joined = df_original.join(df_filtered, on="id", how="inner")

    # Write the resulting DataFrame to a Parquet file
    df_joined.write_parquet(output_path)
    
    print(f"Successfully joined data. Resulting DataFrame has {df_joined.shape[0]} records.")

if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("Usage: python join_data.py <original_file_path> <filtered_ids_path> <output_file_path>")
        sys.exit(1)
    join_data(sys.argv[1], sys.argv[2], sys.argv[3])
