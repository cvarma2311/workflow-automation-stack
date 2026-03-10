import subprocess
import sys
from pathlib import Path
from typing import Any

import polars as pl
from prefect import flow, get_run_logger, task
from prefect.task_runners import ConcurrentTaskRunner

from profiler import memory_profiler


PROJECT_DIR = Path(__file__).resolve().parent
DATA_DIR = PROJECT_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)


def run_python_script(script_name: str, args: list[str]) -> None:
    logger = get_run_logger()

    script_path = PROJECT_DIR / script_name
    if not script_path.exists():
        logger.error("Script '%s' not found!", script_path)
        sys.exit(1)

    command = [sys.executable, str(script_path), *args]
    logger.info("Running command: %s", " ".join(command))

    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )

    output_lines = []
    for line in iter(process.stdout.readline, ""):
        logger.info(line.strip())
        output_lines.append(line)

    process.stdout.close()
    return_code = process.wait()
    if return_code != 0:
        logger.error("Script '%s' failed with exit code %s", script_name, return_code)
        logger.error("--- Script Output (START) ---")
        for line in output_lines:
            logger.error(line.strip())
        logger.error("--- Script Output (END) ---")
        raise RuntimeError(f"Script '{script_name}' failed")


@task
@memory_profiler
def generate_data_task(output_path: str, num_records: int) -> str:
    run_python_script("generate_data.py", [output_path, str(num_records)])
    return output_path


@task
@memory_profiler
def filter_data_task(raw_path: str, output_path: str, divisor: int) -> str:
    run_python_script("filter_data.py", [raw_path, output_path, str(divisor)])
    return output_path


@task
@memory_profiler
def join_data_task(raw_path: str, filtered_path: str, output_path: str, original_file_limit: int) -> str:
    run_python_script("join_data.py", [raw_path, filtered_path, output_path, str(original_file_limit)])
    return output_path


@task
def parquet_row_count(path: str) -> int:
    return pl.scan_parquet(path).select(pl.len()).collect().item()


@task
def file_size_mb(path: str) -> float:
    return round(Path(path).stat().st_size / (1024 * 1024), 2)


@task
def build_branch_aggregations(
    dataset_name: str,
    branch_name: str,
    joined_path: str,
    complexity_rounds: int,
) -> str:
    out_path = DATA_DIR / f"agg_{dataset_name}_{branch_name}.parquet"
    base_df = (
        pl.read_parquet(joined_path)
        .with_columns(
            ((pl.col("id") * 1.13) % 10000).cast(pl.Float64).alias("revenue_base"),
            (pl.col("id") % 24).alias("hour_bucket_base"),
            (pl.col("id") % 7).alias("weekday_bucket_base"),
            pl.when(pl.col("id") % 2 == 0).then(pl.lit("even")).otherwise(pl.lit("odd")).alias("parity_base"),
        )
    )

    round_outputs = []
    for round_id in range(1, complexity_rounds + 1):
        per_round = (
            base_df.lazy()
            .with_columns(
                (pl.col("revenue_base") * (1 + (round_id / 100))).alias("revenue"),
                ((pl.col("hour_bucket_base") + round_id) % 24).alias("hour_bucket"),
                ((pl.col("weekday_bucket_base") + round_id) % 7).alias("weekday_bucket"),
                pl.col("parity_base").alias("parity"),
            )
            .group_by(["hour_bucket", "weekday_bucket", "parity"])
            .agg(
                pl.len().alias("rows"),
                pl.col("revenue").sum().alias("revenue_sum"),
                pl.col("revenue").mean().alias("revenue_avg"),
                pl.col("revenue").max().alias("revenue_max"),
                pl.col("revenue").min().alias("revenue_min"),
            )
            .with_columns(pl.lit(round_id).alias("round_id"))
            .collect()
        )
        round_outputs.append(per_round)

    pl.concat(round_outputs).sort(["round_id", "hour_bucket", "weekday_bucket", "parity"]).write_parquet(out_path)
    return str(out_path)


@task
def make_dataset_total_summary(dataset_name: str, branch_results: list[dict[str, Any]]) -> dict[str, Any]:
    total_filtered_rows = sum(item["filtered_rows"] for item in branch_results)
    total_joined_rows = sum(item["joined_rows"] for item in branch_results)
    total_joined_size_mb = round(sum(item["joined_size_mb"] for item in branch_results), 2)
    return {
        "dataset": dataset_name,
        "branches": len(branch_results),
        "total_filtered_rows": total_filtered_rows,
        "total_joined_rows": total_joined_rows,
        "total_joined_size_mb": total_joined_size_mb,
    }


@flow(name="Filter + Join Branch", task_runner=ConcurrentTaskRunner())
def branch_subflow(
    dataset_name: str,
    raw_path: str,
    branch_name: str,
    divisor: int,
    join_limit: int,
    complexity_rounds: int,
) -> dict[str, Any]:
    logger = get_run_logger()
    logger.info(
        "Starting branch subflow dataset=%s branch=%s divisor=%s join_limit=%s",
        dataset_name,
        branch_name,
        divisor,
        join_limit,
    )

    filtered_file = DATA_DIR / f"filtered_{dataset_name}_{branch_name}.parquet"
    joined_file = DATA_DIR / f"joined_{dataset_name}_{branch_name}.parquet"

    filtered_future = filter_data_task.submit(raw_path, str(filtered_file), divisor)
    joined_future = join_data_task.submit(raw_path, filtered_future, str(joined_file), join_limit)

    filtered_rows_future = parquet_row_count.submit(filtered_future)
    joined_rows_future = parquet_row_count.submit(joined_future)
    joined_size_future = file_size_mb.submit(joined_future)
    agg_file_future = build_branch_aggregations.submit(dataset_name, branch_name, joined_future, complexity_rounds)

    result = {
        "dataset": dataset_name,
        "branch": branch_name,
        "divisor": divisor,
        "filtered_file": filtered_future.result(),
        "joined_file": joined_future.result(),
        "aggregation_file": agg_file_future.result(),
        "filtered_rows": filtered_rows_future.result(),
        "joined_rows": joined_rows_future.result(),
        "joined_size_mb": joined_size_future.result(),
    }
    logger.info("Completed branch subflow: %s", result)
    return result


@task
def run_branch_subflow(
    dataset_name: str,
    raw_path: str,
    branch_name: str,
    divisor: int,
    join_limit: int,
    complexity_rounds: int,
) -> dict[str, Any]:
    return branch_subflow(dataset_name, raw_path, branch_name, divisor, join_limit, complexity_rounds)


@flow(name="Dataset Pipeline", task_runner=ConcurrentTaskRunner())
def dataset_subflow(
    dataset_name: str,
    num_records: int,
    join_limit: int,
    branch_divisors: tuple[int, ...],
    complexity_rounds: int,
) -> dict[str, Any]:
    logger = get_run_logger()
    raw_file = DATA_DIR / f"raw_{dataset_name}.parquet"

    logger.info(
        "Starting dataset subflow dataset=%s records=%s branches=%s",
        dataset_name,
        num_records,
        len(branch_divisors),
    )

    raw_path = generate_data_task.submit(str(raw_file), num_records).result()
    raw_size_mb = file_size_mb.submit(raw_path).result()

    branch_futures = []
    for idx, divisor in enumerate(branch_divisors, start=1):
        branch_name = f"branch_{idx}"
        branch_futures.append(
            run_branch_subflow.submit(
                dataset_name, raw_path, branch_name, divisor, join_limit, complexity_rounds
            )
        )

    branch_results = [future.result() for future in branch_futures]
    totals = make_dataset_total_summary.submit(dataset_name, branch_results).result()

    result = {
        "dataset": dataset_name,
        "records_generated": num_records,
        "raw_data_file": raw_path,
        "raw_size_mb": raw_size_mb,
        "branch_results": branch_results,
        "totals": totals,
    }
    logger.info("Completed dataset subflow %s", dataset_name)
    return result


@task
def run_dataset_subflow(
    dataset_name: str,
    num_records: int,
    join_limit: int,
    branch_divisors: tuple[int, ...],
    complexity_rounds: int,
) -> dict[str, Any]:
    return dataset_subflow(dataset_name, num_records, join_limit, branch_divisors, complexity_rounds)


@task
def write_global_summary(dataset_results: list[dict[str, Any]]) -> str:
    summary_rows = []
    for dataset in dataset_results:
        totals = dataset["totals"]
        summary_rows.append(
            {
                "dataset": dataset["dataset"],
                "records_generated": dataset["records_generated"],
                "raw_size_mb": dataset["raw_size_mb"],
                "branches": totals["branches"],
                "total_filtered_rows": totals["total_filtered_rows"],
                "total_joined_rows": totals["total_joined_rows"],
                "total_joined_size_mb": totals["total_joined_size_mb"],
            }
        )

    out_path = DATA_DIR / "advanced_global_summary.parquet"
    pl.DataFrame(summary_rows).write_parquet(out_path)
    return str(out_path)


@flow(name="Python Data Pipeline Advanced", task_runner=ConcurrentTaskRunner())
def python_data_pipeline_advanced(
    datasets: tuple[tuple[str, int], ...] = (
        ("dataset_a", 4_000_000),
        ("dataset_b", 5_000_000),
        ("dataset_c", 6_000_000),
    ),
    branch_divisors: tuple[int, ...] = (5, 7, 9, 11, 13, 17),
    join_limit: int = 1_500_000,
    complexity_rounds: int = 5,
) -> dict[str, Any]:
    logger = get_run_logger()
    logger.info(
        "Starting advanced parent flow with multi-dataset parallel subflows and branch-level parallelism."
    )

    dataset_futures = []
    for dataset_name, record_count in datasets:
        dataset_futures.append(
            run_dataset_subflow.submit(
                dataset_name, record_count, join_limit, branch_divisors, complexity_rounds
            )
        )

    dataset_results = [future.result() for future in dataset_futures]
    global_summary_path = write_global_summary.submit(dataset_results).result()

    final_summary = {
        "datasets_processed": len(dataset_results),
        "branch_divisors": list(branch_divisors),
        "join_limit": join_limit,
        "complexity_rounds": complexity_rounds,
        "global_summary_file": global_summary_path,
        "datasets": dataset_results,
    }

    logger.info("Advanced parent flow completed.")
    logger.info("Final summary: %s", final_summary)
    return final_summary


if __name__ == "__main__":
    python_data_pipeline_advanced()
