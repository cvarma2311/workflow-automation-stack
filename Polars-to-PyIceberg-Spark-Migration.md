# Migration Plan: Polars → PyIceberg → Spark DataFrames → Spark SQL

This guide describes a phased approach to migrate your workflow automation from **Polars** to **PyIceberg** and later to **Spark DataFrames** and **Spark SQL**, using **MinIO**, **PostgreSQL (Iceberg catalog)**, and **Prefect**.

---

## Phase 0 — Prep (shared config + project shape)

**Goal:** centralize endpoints/paths and keep engines swappable.

### Example `config/config.yaml`
```yaml
env: dev

catalog:
  name: local
  jdbc_uri: "jdbc:postgresql://1.1.1.1:5432/iceberg_catalog"
  user: "iceberg_user"
  password: "iceberg_pass"
  warehouse: "s3a://iceberg-warehouse/"

s3:
  endpoint: "https://1.1.1.1:9000"
  access_key: "minioadmin"
  secret_key: "minioadmin"
  path_style: true

tables:
  stg_active_employees: "local.stg.active_employees"
  cur_employee_counts:  "local.cur.employee_counts"

paths:
  raw_employees: "s3://data-raw/employees/*.csv"
  stage_root:   "s3://data-staging/intermediate"

housekeeping:
  target_file_size: 134217728  # 128MB
  expire_days: 7
```

### Project layout
```
src/
  cfg.py
  io_polars.py
  io_pyiceberg.py
  io_spark.py
  pipeline.py
  flow_prefect.py
```

---

## Phase 1 — Polars → PyIceberg (read path first)

**Goal:** Keep transforms in Polars but use **PyIceberg for reads** from Iceberg tables.

### Stage in Polars
```python
import polars as pl
def polars_stage_employees(raw_glob: str, stage_root: str, run_id: str) -> str:
    lf = (pl.scan_csv(raw_glob, infer_schema_length=0)
            .filter(pl.col("status")=="active")
            .select(["id","name","department","status"]))
    df = lf.collect()
    out = f"{stage_root}/employees_active/run={run_id}/"
    df.write_parquet(f"{out}part.parquet")
    return out
```

### Read with PyIceberg
```python
from pyiceberg.catalog import load_catalog
import pyarrow as pa, polars as pl

def iceberg_to_polars(cfg, table_name: str, limit: int|None=None) -> pl.DataFrame:
    cat = load_catalog(
        cfg["catalog"]["name"],
        **{
          "uri": cfg["catalog"]["jdbc_uri"],
          "jdbc.user": cfg["catalog"]["user"],
          "jdbc.password": cfg["catalog"]["password"],
          "s3.endpoint": cfg["s3"]["endpoint"],
          "s3.access-key-id": cfg["s3"]["access_key"],
          "s3.secret-access-key": cfg["s3"]["secret_key"],
          "s3.path-style-access": "true" if cfg["s3"]["path_style"] else "false",
        }
    )
    table = cat.load_table(table_name)
    scan = table.scan()
    if limit:
        scan = scan.limit(limit)
    batches = list(scan.to_arrow())
    arrow_tbl = pa.Table.from_batches(batches) if batches else pa.table({})
    return pl.from_arrow(arrow_tbl)
```

---

## Phase 2 — Introduce Spark DataFrames (writer first)

**Goal:** Keep Polars transforms; use **Spark to publish to Iceberg**.

```python
from pyspark.sql import SparkSession

def spark_session(app="Writer"):
    return SparkSession.builder.appName(app).getOrCreate()

def spark_write_parquet_to_iceberg(staged_path: str, table: str, coalesce: int = 8, target_file_size=134_217_728):
    spark = spark_session("LoadToIceberg")
    df = spark.read.parquet(staged_path)
    df = df.coalesce(coalesce)
    df.writeTo(table).createOrReplace()
    spark.sql(f"ALTER TABLE {table} SET TBLPROPERTIES ('write.target-file-size-bytes'='{target_file_size}')")
```

---

## Phase 3 — Spark DataFrames for heavy transforms

**Goal:** Migrate joins/aggregations to Spark.

```python
from pyspark.sql import SparkSession, functions as F

def curate_employee_counts(staging_table: str, curated_table: str):
    spark = SparkSession.builder.appName("Curate").getOrCreate()
    df = spark.read.table(staging_table)
    out = df.groupBy("department").count().coalesce(4)
    out.writeTo(curated_table).createOrReplace()
```

---

## Phase 4 — Spark SQL for business logic

```sql
CREATE TABLE IF NOT EXISTS local.cur.employee_counts (department STRING, cnt BIGINT) USING iceberg;

INSERT OVERWRITE local.cur.employee_counts
SELECT department, COUNT(*) AS cnt
FROM local.stg.active_employees
GROUP BY department;
```

---

## Prefect Flow Example

```python
import os, yaml
from datetime import datetime
from prefect import flow, task
from src.io_polars import polars_stage_employees
from src.io_spark import spark_write_parquet_to_iceberg
from src.pipeline import curate_employee_counts
from src.io_pyiceberg import iceberg_to_polars

def load_cfg(p="config/config.yaml"):
    with open(p) as f: return yaml.safe_load(f)

@task
def stage(input_glob, stage_root):
    run_id = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    return polars_stage_employees(input_glob, stage_root, run_id)

@task
def publish(staged_path, table, target_file_size):
    spark_write_parquet_to_iceberg(staged_path, table, target_file_size=target_file_size)

@task
def curate(staging_table, curated_table):
    curate_employee_counts(staging_table, curated_table)

@task
def validate_read(table):
    df = iceberg_to_polars(load_cfg(), table, limit=200_000)
    assert df.height > 0
    return df.height

@flow(name="employees_pipeline")
def employees_pipeline(cfg_path="config/config.yaml"):
    cfg = load_cfg(cfg_path)
    staged = stage(cfg["paths"]["raw_employees"], cfg["paths"]["stage_root"])
    publish(staged, cfg["tables"]["stg_active_employees"], cfg["housekeeping"]["target_file_size"])
    curate(cfg["tables"]["stg_active_employees"], cfg["tables"]["cur_employee_counts"])
    validate_read(cfg["tables"]["cur_employee_counts"])
```

---

## Validation & Ops Checklist

- ✅ Schema parity (Polars vs Iceberg tables)
- ✅ Row count parity between staged Parquet and Iceberg
- ✅ File sizes ~64–128 MB
- ✅ Periodic maintenance:
```sql
CALL local.system.rewrite_data_files('local.stg.active_employees');
CALL local.system.expire_snapshots('local.stg.active_employees', TIMESTAMP 'now' - INTERVAL '7' DAY);
```

---

## Final Outcome

1. **Phase 1:** Polars + PyIceberg reads  
2. **Phase 2:** Polars + Spark writes to Iceberg  
3. **Phase 3:** Heavy transforms in Spark DF  
4. **Phase 4:** Declarative logic in Spark SQL
