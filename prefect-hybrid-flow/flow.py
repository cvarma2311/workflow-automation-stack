import subprocess
import sys
from pathlib import Path
from prefect import task, flow, get_run_logger
from profiler import memory_profiler

# --- Configuration ---
# Assumes the script is run from the `prefect-hybrid-flow` directory.
# The Java project is in a sibling directory.
JAVA_PROJECT_DIR = Path("../java-engine")
JAR_NAME = "java-engine-1.0.0-jar-with-dependencies.jar"
JAR_PATH = JAVA_PROJECT_DIR / "target" / JAR_NAME

# JVM arguments for verbose GC logging and heap statistics
# This will create a gc.log file in the DATA_DIR for each run.
JVM_ARGS = [
    "-Xlog:gc*=info,heap*=info:file=" + str(Path("./data/gc.log")) + ":tags,time,uptime,level",
    "-XX:+HeapDumpOnOutOfMemoryError",
    "-XX:HeapDumpPath=" + str(Path("./data/heapdump.hprof"))
]


# Create a directory for the data outputs
DATA_DIR = Path("./data")
DATA_DIR.mkdir(exist_ok=True)

# File paths
RAW_DATA_FILE = DATA_DIR / "500m_records.txt"
FILTERED_DATA_FILE = DATA_DIR / "filtered_records.txt"
JOINED_DATA_FILE = DATA_DIR / "joined_records.txt"


def run_java_command(command_args: list[str]):
    """Helper function to run a command on the Java application."""
    logger = get_run_logger()

    if not JAR_PATH.exists():
        logger.error(f"JAR file not found at '{JAR_PATH}'!")
        logger.error("Please build the Java project first by navigating to '../java-engine' and running 'mvn clean package'.")
        sys.exit(1)

    command = [
        "java",
    ] + JVM_ARGS + [ # Prepend JVM arguments
        "-jar",
        str(JAR_PATH),
    ] + command_args

    logger.info(f"Running command: {' '.join(command)}")

    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, # Merge stderr into stdout
        text=True,
        bufsize=1
    )

    java_output = []
    # Log and store output as it comes
    for line in iter(process.stdout.readline, ''):
        logger.info(line.strip())
        java_output.append(line)
    
    process.stdout.close()
    return_code = process.wait()

    if return_code != 0:
        logger.error(f"Java command '{command_args[0]}' failed with exit code {return_code}")
        logger.error("--- Java Application Output (START) ---")
        for line in java_output:
            logger.error(line.strip())
        logger.error("--- Java Application Output (END) ---")
        raise RuntimeError(f"Java command '{command_args[0]}' failed!")
    
    logger.info(f"Java command '{command_args[0]}' completed successfully.")

@task
@memory_profiler
def generate_data():
    """Runs the Java command to generate the initial data file."""
    run_java_command(["generate", str(RAW_DATA_FILE)])
    return RAW_DATA_FILE

@task
@memory_profiler
def filter_data(raw_data_path: Path):
    """Runs the Java command to filter the data."""
    run_java_command(["filter", str(raw_data_path), str(FILTERED_DATA_FILE)])
    return FILTERED_DATA_FILE

@task
@memory_profiler
def join_data(raw_data_path: Path, filtered_data_path: Path):
    """Runs the Java command to join the datasets."""
    run_java_command([
        "join",
        str(raw_data_path),
        str(filtered_data_path),
        str(JOINED_DATA_FILE)
    ])
    return JOINED_DATA_FILE


@flow(name="Hybrid Java-Python Data Pipeline")
def java_data_pipeline():
    """
    Orchestrates the full data pipeline using Prefect to trigger Java commands.
    1. Generate 500M records.
    2. Filter records based on a hash function.
    3. Join the first 100M of the original records with the filtered set.
    """
    logger = get_run_logger()
    logger.info("Starting the Hybrid Java-Python data pipeline.")

    raw_file = generate_data()
    filtered_file = filter_data(raw_file)
    join_data(raw_file, filtered_file)

    logger.info("Pipeline execution complete. Final output is at: %s", JOINED_DATA_FILE)

if __name__ == "__main__":
    java_data_pipeline()
