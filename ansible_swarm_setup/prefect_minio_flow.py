import os
import pandas as pd
from faker import Faker
from prefect import flow, task
from prefect.engine import get_run_logger
import s3fs

# --- Configuration ---
# In a real-world scenario, use Prefect Blocks to store sensitive credentials.
MINIO_ENDPOINT_URL = "http://minio:9000"
MINIO_ACCESS_KEY = "minioadmin"
MINIO_SECRET_KEY = "minioadmin"
BUCKET_NAME = "prefect-data"

# S3FS client for MinIO interaction
s3 = s3fs.S3FileSystem(
    key=MINIO_ACCESS_KEY,
    secret=MINIO_SECRET_KEY,
    client_kwargs={"endpoint_url": MINIO_ENDPOINT_URL}
)

# --- Helper Functions ---
def install_dependencies():
    """A simple function to install dependencies at runtime.
    
    NOTE: In a production environment, it is best practice to build a custom 
    Docker image with these dependencies pre-installed rather than installing
    them at runtime. This is included for demonstration purposes.
    """
    logger = get_run_logger()
    try:
        import pandas
        import faker
        import s3fs
        logger.info("Dependencies are already satisfied.")
    except ImportError:
        logger.info("Installing missing dependencies: pandas, faker, s3fs...")
        os.system("pip install pandas faker s3fs")
        logger.info("Dependencies installed.")

# --- Prefect Tasks ---

@task(name="Generate and Upload Raw Data")
def generate_and_upload_raw_data(num_records: int = 100_000):
    """Generates a dataset and uploads it to MinIO."""
    logger = get_run_logger()
    install_dependencies()

    logger.info(f"Generating {num_records} records...")
    fake = Faker()
    data = {
        "id": range(1, num_records + 1),
        "name": [fake.name() for _ in range(num_records)]
    }
    df = pd.DataFrame(data)

    output_path = f"s3://{BUCKET_NAME}/raw/initial_records.parquet"
    logger.info(f"Writing data to MinIO at: {output_path}")
    df.to_parquet(output_path, index=False, filesystem=s3)
    
    return output_path

@task(name="Filter for Even IDs")
def filter_for_even_ids(path: str):
    """Reads data from MinIO, filters for even IDs, and writes back."""
    logger = get_run_logger()
    logger.info(f"Reading data from: {path}")
    df = pd.read_parquet(path, filesystem=s3)
    
    logger.info("Filtering for even IDs...")
    even_df = df[df['id'] % 2 == 0].copy()
    
    output_path = f"s3://{BUCKET_NAME}/processed/even_id_records.parquet"
    logger.info(f"Writing {len(even_df)} records to: {output_path}")
    even_df.to_parquet(output_path, index=False, filesystem=s3)

    return output_path

@task(name="Filter by Name and ID")
def filter_by_name_and_id(path: str):
    """Reads data, filters by name ('s') and ID (not divisible by 10)."""
    logger = get_run_logger()
    logger.info(f"Reading data from: {path}")
    df = pd.read_parquet(path, filesystem=s3)

    logger.info("Filtering for names starting with 's' and ID not divisible by 10...")
    filtered_df = df[
        df['name'].str.lower().str.startswith('s') & (df['id'] % 10 != 0)
    ].copy()

    output_path = f"s3://{BUCKET_NAME}/final/filtered_records.parquet"
    logger.info(f"Writing {len(filtered_df)} final records to: {output_path}")
    filtered_df.to_parquet(output_path, index=False, filesystem=s3)

    return output_path

# --- Prefect Flow ---

@flow(name="MinIO Data Pipeline")
def minio_data_pipeline():
    """Orchestrates the full data generation and filtering pipeline."""
    logger = get_run_logger()
    
    # Ensure the bucket exists
    logger.info(f"Ensuring MinIO bucket '{BUCKET_NAME}' exists...")
    if not s3.exists(BUCKET_NAME):
        s3.mkdir(BUCKET_NAME)
        logger.info(f"Bucket '{BUCKET_NAME}' created.")
    else:
        logger.info(f"Bucket '{BUCKET_NAME}' already exists.")

    # Run the pipeline
    raw_data_path = generate_and_upload_raw_data()
    even_ids_path = filter_for_even_ids(raw_data_path)
    final_path = filter_by_name_and_id(even_ids_path)

    logger.info(f"Pipeline complete! Final data is at: {final_path}")

if __name__ == "__main__":
    minio_data_pipeline()