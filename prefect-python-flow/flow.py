import subprocess
import sys
from pathlib import Path
from prefect import task, flow, get_run_logger
from profiler import memory_profiler

# --- Configuration ---
# Assumes the script is run from the `prefect-python-flow` directory.

# Create a directory for the data outputs
DATA_DIR = Path("./data")
DATA_DIR.mkdir(exist_ok=True)

# File paths
RAW_DATA_FILE = DATA_DIR / "500m_records.parquet"
FILTERED_DATA_FILE = DATA_DIR / "filtered_records.parquet"
JOINED_DATA_FILE = DATA_DIR / "joined_records.parquet"


def run_python_script(script_name: str, args: list[str]):
    """Helper function to run a Python data processing script."""
    logger = get_run_logger()
    
    script_path = Path(script_name)
    if not script_path.exists():
        logger.error(f"Script '{script_path}' not found!")
        sys.exit(1)

    command = [
        sys.executable, # Use the Python interpreter from the current environment
        str(script_path)
    ] + args
    
    logger.info(f"Running command: {' '.join(command)}")
    
    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1
    )

    script_output = []
    for line in iter(process.stdout.readline, ''):
        logger.info(line.strip())
        script_output.append(line)
    
    process.stdout.close()
    return_code = process.wait()

    if return_code != 0:
        logger.error(f"Python script '{script_name}' failed with exit code {return_code}")
        logger.error("--- Script Output (START) ---")
        for line in script_output:
            logger.error(line.strip())
        logger.error("--- Script Output (END) ---")
        raise RuntimeError(f"Python script '{script_name}' failed!")
    
    logger.info(f"Python script '{script_name}' completed successfully.")


@task
@memory_profiler
def generate_data_task():
    """Generates the initial 500 million record file."""
    run_python_script("generate_data.py", [str(RAW_DATA_FILE)])
    return RAW_DATA_FILE

@task
@memory_profiler
def filter_data_task(raw_data_path: Path):
    """Filters the raw data."""
    run_python_script("filter_data.py", [str(raw_data_path), str(FILTERED_DATA_FILE)])
    return FILTERED_DATA_FILE

@task
@memory_profiler
def join_data_task(raw_data_path: Path, filtered_data_path: Path):
    """Joins the datasets."""
    run_python_script(
        "join_data.py",
        [str(raw_data_path), str(filtered_data_path), str(JOINED_DATA_FILE)]
    )
    return JOINED_DATA_FILE


@flow(name="Python Data Processing Pipeline")
def python_data_pipeline():
    """
    Orchestrates the full data pipeline using Prefect to trigger Python scripts.
    """
    logger = get_run_logger()

    logger.info("Starting the Python data processing pipeline.")

    raw_file = generate_data_task()
    filtered_file = filter_data_task(raw_file)
    join_data_task(raw_file, filtered_file)

    logger.info("Pipeline execution complete. Final output is at: %s", JOINED_DATA_FILE)

if __name__ == "__main__":
    python_data_pipeline()
