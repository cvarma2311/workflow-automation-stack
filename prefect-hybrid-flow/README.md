# Prefect + Java Hybrid Data Processing Pipeline

This project demonstrates a hybrid data processing pipeline that uses Prefect for workflow orchestration and a high-performance Java application for the core data processing logic. This "conductor/engine" model allows for the best of both worlds: the powerful scheduling and observability of Prefect, and the performance of Java for heavy lifting.

The pipeline performs the following steps, orchestrated as separate Prefect tasks:
1.  **Generate Data:** Creates a text file with 500 million records.
2.  **Filter Data:** Streams the large file, filters it, and writes the result to a new file.
3.  **Join Data:** Joins a subset of the original data with the filtered data.

Each underlying Java job is launched from a Prefect task, and the Java application uses a custom `@MemoryProfiler` annotation to log performance metrics for each major step.

---

## Architecture

-   **`prefect-hybrid-flow` (This Project):**
    -   **Python Conductor (`flow.py`):** A minimal Python script that defines the Prefect workflow (`@flow` and `@task`). Each task's only responsibility is to launch the Java application with the correct parameters to execute a specific batch job.
    -   **Ansible Setup (`ansible/`):** An Ansible playbook to automate the installation of all necessary dependencies (Java, Maven, Python, Prefect).

-   **`java-engine` (The Engine):**
    -   A lightweight, standalone command-line application that contains all the business logic for data processing.
    -   It is configured to run one of three tasks (`generate`, `filter`, `join`) based on command-line arguments.
    -   The Prefect "conductor" passes the correct command at each step of the pipeline.

---

## How to Run the Pipeline

Follow these three steps to set up the environment, build the Java application, and run the Prefect workflow.

### Step 1: Set Up the Environment

The provided Ansible playbook will install Java, Maven, Python, and the correct version of Prefect.

1.  **Navigate to the Ansible directory:**
    ```bash
    cd prefect-hybrid-flow/ansible
    ```

2.  **Run the playbook:**
    ```bash
    ansible-playbook -i inventory.ini setup.yml
    ```
    You may be prompted for your `sudo` password as it needs to install system packages.

### Step 2: Build the Java Application

Compile the `java-engine` project and package it into an executable JAR.

1.  **Navigate to the Java project directory:**
    ```bash
    # From the repository root
    cd java-engine
    ```

2.  **Run Maven package:**
    ```bash
    mvn clean package
    ```
    This command creates the executable JAR file in the `java-engine/target/` directory, which is what the Prefect flow will execute.

### Step 3: Run the Prefect Flow

Execute the main Python workflow script to start the pipeline.

1.  **Navigate to the Prefect project directory:**
    ```bash
    # From the repository root
    cd prefect-hybrid-flow
    ```

2.  **Run the flow:**
    ```bash
    python3 flow.py
    ```

### What to Expect

-   The Python script will start, and you will see logs from Prefect as it begins executing the flow.
-   Prefect will trigger the first task, `generate_data`. This task will execute the Java JAR with the `generate` command. You will see logs from both the Python script and the Java application in your console.
-   **Warning:** The data generation step will create a very large file (`500m_records.txt`) and will take a considerable amount of time and disk space.
-   After the first task completes successfully, Prefect will proceed with the `filter_data` and `join_data` tasks sequentially.
-   Upon completion, you will find the `500m_records.txt`, `filtered_records.txt`, and `joined_records.txt` files in the `prefect-hybrid-flow/data/` directory.
