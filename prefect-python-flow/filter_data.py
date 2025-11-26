import sys
from pathlib import Path
from memory_profiler import profile
import polars as pl

@profile(stream=sys.stdout)
def filter_data(input_file_path, output_file_path):
    print(f"Starting data filtering from {input_file_path} to {output_file_path}")
    
    input_path = Path(input_file_path)
    output_path = Path(output_file_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    filter_divisor = 10 # Keep records where id % 10 == 0

    # Read Parquet file into Polars DataFrame
    df = pl.read_parquet(input_path)

    # Perform filtering using Polars expressions
    df_filtered = df.filter(pl.col("id") % filter_divisor == 0)

    # Write the filtered DataFrame to a Parquet file
    df_filtered.write_parquet(output_path)
    
    print(f"Successfully filtered data. Processed {df.shape[0]} records, kept {df_filtered.shape[0]} records.")

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python filter_data.py <input_file_path> <output_file_path>")
        sys.exit(1)
    filter_data(sys.argv[1], sys.argv[2])
