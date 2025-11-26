import sys
import uuid # Kept for potential future use or if UUIDs are strictly required, but not used in current Polars-native gen.
from pathlib import Path
from memory_profiler import profile
import polars as pl

@profile(stream=sys.stdout)
def generate_data(output_file_path, num_records=500_000_000):
    print(f"Starting data generation for {num_records} records into {output_file_path}")
    output_path = Path(output_file_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Use Polars expressions for memory-efficient data generation
    # Generating 500M UUIDs in Python memory would still lead to OOM.
    # Using sequential integer IDs for optimization.
    df = pl.DataFrame({
        "id": pl.int_range(0, num_records, eager=True), # Sequential integer IDs
        "data_payload": ["some_random_payload_data"] * num_records # Duplicate string for data
    })
    
    df.write_parquet(output_path)
    
    print(f"Successfully generated {num_records} records and wrote to {output_file_path}")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python generate_data.py <output_file_path>")
        sys.exit(1)
    generate_data(sys.argv[1])
