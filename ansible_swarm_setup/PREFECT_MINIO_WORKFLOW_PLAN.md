# Plan: Prefect & MinIO Data Pipeline Workflow

## 1. Objective

This document outlines the plan to create a multi-step data processing workflow using Prefect for orchestration and MinIO for storage. The goal is to demonstrate a realistic data pipeline where data is generated, processed in multiple stages, and stored back to an object store at each step.

This workflow will be self-contained in a single Python script and will be deployed to the existing Prefect server.

## 2. Workflow Overview

The pipeline will consist of three main steps:

1.  **Generate Data:** Create a dataset of 100,000 records, each with a unique ID and a random name. Store this dataset in MinIO.
2.  **Filter Even IDs:** Read the initial dataset from MinIO, filter it to keep only records with an even-numbered ID, and store the result back in MinIO.
3.  **Filter by Name and ID:** Read the intermediate dataset, apply a final filter (name starts with 's' and ID is not divisible by 10), and store the final result in MinIO.

## 3. Implementation Details

### 3.1. New File

A new Python script, `prefect_minio_flow.py`, will be created in the root of the `ansible_swarm_setup` directory.

### 3.2. Dependencies

The script will require the following Python libraries. These will need to be installed in the Prefect worker's execution environment.

- `prefect`
- `pandas`
- `faker` (for generating random names)
- `s3fs` and `boto3` (for MinIO/S3 communication)

A `requirements.txt` file will be created for these dependencies.

### 3.3. Python Script Structure (`prefect_minio_flow.py`)

The script will be organized as follows:

1.  **Configuration:** A global section will define MinIO connection parameters (endpoint, credentials) and the bucket name (`prefect-data`).

2.  **Task 1: `generate_and_upload_raw_data`**
    - A Prefect `@task`.
    - Creates a pandas DataFrame with 100,000 rows and two columns: `id` and `name`.
    - Writes the DataFrame to a Parquet file in MinIO at `s3://prefect-data/raw/initial_records.parquet`.
    - Returns the S3 path of the created file.

3.  **Task 2: `filter_for_even_ids`**
    - A Prefect `@task` that accepts the file path from the previous task.
    - Reads the Parquet file from MinIO.
    - Filters the DataFrame for records where `id` is even.
    - Writes the filtered DataFrame to a new Parquet file at `s3://prefect-data/processed/even_id_records.parquet`.
    - Returns the S3 path of this new file.

4.  **Task 3: `filter_by_name_and_id`**
    - A Prefect `@task` that accepts the file path from the second task.
    - Reads the intermediate Parquet file from MinIO.
    - Filters the DataFrame for records where `name` starts with 's' (case-insensitive) AND `id` is not divisible by 10.
    - Writes the final DataFrame to a Parquet file at `s3://prefect-data/final/filtered_records.parquet`.

5.  **Flow: `minio_data_pipeline`**
    - A Prefect `@flow` that orchestrates the entire pipeline.
    - It will first ensure the `prefect-data` bucket exists in MinIO.
    - It will then call the three tasks in sequence, chaining their inputs and outputs.

## 4. Deployment and Execution

After the script is created, the following steps will be taken:

1.  **Deploy the Flow:** A `prefect deploy` command will be used to register the workflow with the Prefect server and associate it with the `my-docker-pool` work pool.
2.  **Run the Flow:** The pipeline will be executed from the Prefect UI to test the full implementation.
