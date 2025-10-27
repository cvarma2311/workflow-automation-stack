import os
import pandas as pd
from faker import Faker
from prefect import flow, task
from prefect.logging import get_run_logger
import s3fs

# --- Configuration ---
# Use private IP for MinIO endpoint (same VPC)
MINIO_ENDPOINT_URL = "http://172.31.26.14:9000"
MINIO_ACCESS_KEY = "minioadmin"
MINIO_SECRET_KEY = "minioadmin"
BUCKET_NAME = "prefect-data"

# S3FS client for MinIO interaction
s3 = s3fs.S3FileSystem(
    key=MINIO_ACCESS_KEY,
    secret=MINIO_SECRET_KEY,
    client_kwargs={"endpoint_url": MINIO_ENDPOINT_URL}
)


# --- Helper Function ---
def install_dependencies():
    """Install required libraries at runtime if missing (for demo purposes)."""
    logger = get_run_logger()
    try:
        import pandas, faker, s3fs  # noqa: F401
        logger.info("Dependencies are already installed.")
    except ImportError:
        logger.info("Installing missing dependencies: pandas, faker, s3fs...")
        os.system("pip install pandas faker s3fs")
        logger.info("Dependencies installed successfully.")


# --- Prefect Tasks ---

@task(name="Generate and Upload Raw Data")
def generate_and_upload_raw_data(num_records: int = 100_000):
    """Generates a fake dataset and uploads it to MinIO."""
    logger = get_run_logger()
    install_dependencies()

    logger.info(f"Generating {num_records} fake records...")
    fake = Faker()
    data = {
        "id": range(1, num_records + 1),
        "name": [fake.name() for _ in range(num_records)]
    }
    df = pd.DataFrame(data)

    output_path = f"s3://{BUCKET_NAME}/raw/initial_records.parquet"
    logger.info(f"Uploading dataset to MinIO path: {output_path}")
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
    """Reads data, filters by names starting with 's' and IDs not divisible by 10."""
    logger = get_run_logger()
    logger.info(f"Reading data from: {path}")
    df = pd.read_parquet(path, filesystem=s3)

    logger.info("Filtering for names starting with 's' and ID not divisible by 10...")
    filtered_df = df[
        df['name'].str.lower().str.startswith('s') & (df['id'] % 10 != 0)
        ].copy()

    output_path = f"s3://{BUCKET_NAME}/final/filtered_records.parquet"
    logger.info(f"Writing {len(filtered_df)} filtered records to: {output_path}")
    filtered_df.to_parquet(output_path, index=False, filesystem=s3)

    return output_path


# --- Prefect Flow ---
@flow(name="MinIO Data Pipeline")
def minio_data_pipeline():
    """Full ETL flow for generating, filtering, and saving data to MinIO."""
    logger = get_run_logger()

    # Ensure the bucket exists
    logger.info(f"Checking if bucket '{BUCKET_NAME}' exists...")
    if not s3.exists(BUCKET_NAME):
        s3.mkdir(BUCKET_NAME)
        logger.info(f"Bucket '{BUCKET_NAME}' created successfully.")
    else:
        logger.info(f"Bucket '{BUCKET_NAME}' already exists.")

    # Run ETL pipeline
    raw_data_path = generate_and_upload_raw_data()
    even_ids_path = filter_for_even_ids(raw_data_path)
    final_path = filter_by_name_and_id(even_ids_path)

    logger.info(f"✅ Pipeline completed successfully. Final data: {final_path}")


# --- Run Locally ---
if __name__ == "__main__":
    minio_data_pipeline()
