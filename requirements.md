# requirements.md

This document explains what’s in `requirements.txt`, why each package is needed, and exactly how to install and use it in this stack (Spark + Iceberg + MinIO (TLS) + PostgreSQL + Prefect). It assumes **only three fresh Ubuntu 22.04 VMs**; everything else is installed by the Ansible playbook, including Python environments.

> **Important version note**  
> The stack installs **Spark 3.5.6** on all nodes. For best compatibility, set **`pyspark==3.5.6`** in `requirements.txt`. If your current `requirements.txt` uses a different `pyspark` version, update it to match your Spark version.

---

## 1) Recommended `requirements.txt`

Use this file at the repo root so the playbook (or you) can install it into the Prefect virtual environment.

```txt
# Orchestration
prefect==2.*

# Spark + Iceberg (match PySpark to Spark version installed by Ansible)
pyspark==3.5.6
pyiceberg==0.6.*        # Optional: Python-native Iceberg API for ad-hoc work

# Storage
minio==7.*              # Python client for MinIO (S3-compatible)
boto3==1.*              # AWS S3 SDK - also works with MinIO

# Database connectivity
psycopg2-binary==2.9.*  # PostgreSQL connector (for catalog ops from Python)
SQLAlchemy==2.*         # Optional: convenience for DB tasks in flows

# Utilities
pandas==2.2.*
pyarrow==16.*           # Arrow + Parquet helpers used in Python tasks

# TLS roots (helpful when dealing with custom certs)
certifi==2024.*
```

> If you explicitly want to pin exact patch versions, you can. The playbook already installs the **Iceberg Spark runtime JAR** and **spark-hadoop-cloud JAR** that line up with Spark 3.5.6 on the JVM side; `pyspark==3.5.6` keeps your Python API in sync.

---

## 2) What each dependency is for

| Package            | Why it’s needed |
|--------------------|-----------------|
| `prefect`          | Orchestrates your flows and triggers Spark jobs (flow/agent/server). |
| `pyspark`          | Python bindings for Spark; required by Prefect tasks that run Spark code. |
| `pyiceberg`        | Optional Python client for Iceberg tables (listing snapshots, schema ops, etc.) without Spark. |
| `minio`            | Python client for MinIO (S3-compatible) if your flows need object-store ops directly from Python. |
| `boto3`            | AWS SDK for Python; useful for S3-style interactions and credentials flows (works with MinIO). |
| `psycopg2-binary`  | PostgreSQL driver used if a flow connects to the catalog database for admin tasks. |
| `SQLAlchemy`       | Optional convenience layer for SQL tasks. |
| `pandas`, `pyarrow`| Data munging and Parquet/Arrow helpers inside Python tasks. |
| `certifi`          | CA roots; helps Python validate TLS endpoints if system CA store is limited. |

> **Note:** The Spark → MinIO integration uses the Java-side S3A connector and the Java truststore (set in `spark-defaults.conf`). The Python `minio`/`boto3` packages are **only** for flows that talk to object storage directly from Python — not required for Spark’s own I/O.

---

## 3) Where this gets installed

The playbook creates a **virtual environment** for Prefect on the Prefect node:

- **Virtualenv path:** `/opt/prefect/venv`  
- **Flow location:** `/opt/prefect/flows/employee_iceberg_flow.py`  
- **Agent & Server** run under systemd and use that venv.

You have two ways to install `requirements.txt`:

### A) Install manually (one-time)
```bash
# on the Prefect host (e.g., 1.1.1.1)
sudo /opt/prefect/venv/bin/pip install -r /path/to/requirements.txt
```

### B) Install via Ansible (recommended)
Add the following task into your `site.yml` within the “Install Prefect, configure services, deploy flow” play (on hosts: `prefect`) **after** the venv is created:

```yaml
- name: Install Python requirements into Prefect venv
  command: "{{ prefect_install_venv }}/bin/pip install -r /root/iceberg-stack/requirements.txt"
  args:
    chdir: "/root/iceberg-stack"
```

Adjust the `chdir` path to wherever the repository lives on the Prefect node.

> If you want **all Spark nodes** to have the same Python deps (for auxiliary scripts), you can add a similar task under the `hosts: spark` play, pointing to a venv of your choice.

---

## 4) End-to-end deployment steps (no VM prerequisites)

1. **From your control node:** install Ansible and clone the repo
   ```bash
   sudo apt update && sudo apt install -y python3-pip git sshpass
   pip install ansible==9.*
   git clone <your_repo_url> && cd iceberg-stack
   ```

2. **Put your three VM IPs** in `inventory.ini`. Ensure you can SSH into each VM.

3. **Edit `group_vars/all.yml`** to set credentials, host IPs, and (optionally) use real TLS certs.

4. **Place `requirements.txt`** in the repo root (same directory as `site.yml`).

5. **Run the playbook:**
   ```bash
   ansible-playbook -i inventory.ini site.yml
   ```

6. **(Optional) Install the Python requirements automatically** by adding the Ansible task from section 3B. Otherwise, run the manual install once (section 3A).

7. **Open the UIs to verify:**
   - MinIO Console (TLS): `https://<vm1_ip>:9001`
   - Spark Master UI: `http://<vm1_ip>:8080`
   - Prefect UI: `http://<vm1_ip>:4200`

8. **Run the demo flow from Prefect UI** (deployment name: *EmployeePipeline*) or run the on-demand script:
   ```bash
   ssh <any_spark_node>
   sudo /opt/prefect/jobs/run_employee_job.sh
   ```

---

## 5) Version alignment & troubleshooting

- **PySpark must match Spark:** If Spark is 3.5.6, use `pyspark==3.5.6`. Mismatches can cause ClassNotFound errors or API drift.
- **Iceberg JAR vs. Python:** The Iceberg **Spark runtime JAR** (installed by Ansible) is what Spark uses. `pyiceberg` is a separate Python client and doesn’t affect Spark’s Iceberg IO.
- **TLS issues to MinIO:** If Spark can’t connect via S3A with TLS, re-check:
  - The MinIO cert exists at `/etc/minio/certs/public.crt` and key at `/etc/minio/certs/private.key` on each MinIO node.
  - The cert has correct SANs for your IPs/hostnames.
  - The cert is imported into the **Java truststore** on Spark nodes (the playbook includes this step).
- **Firewall:** If UFW is enabled, confirm ports are allowed (SSH 22, MinIO 9000/9001, Spark 7077/8080/8081, PostgreSQL 5432, Prefect 4200).

---

## 6) Updating requirements later

If you change `requirements.txt`, re-run installation on the Prefect host:
```bash
sudo /opt/prefect/venv/bin/pip install -r /path/to/requirements.txt --upgrade
sudo systemctl restart prefect-agent
```

If you pinned `pyspark`, remember to keep it aligned with your Spark version. For example, if you upgrade Spark via the playbook to 3.5.7, also update `pyspark==3.5.7`.

---

## 7) FAQ

- **Do executors need Python libs from `requirements.txt`?**  
  No for Spark I/O, because I/O is handled by JVM and the provided JARs. Yes if your tasks import Python-only libs (like `pandas`) on executors. For those cases, distribute the venv or use `--archives`/`--py-files`, or pre-install on all worker nodes.
  
- **Do we need Hive Metastore?**  
  No. Iceberg uses **PostgreSQL** as a JDBC catalog here.

- **Can we use real TLS certs?**  
  Yes. Set `minio_tls_use_self_signed: false` and provide `minio_public_crt_src` / `minio_private_key_src` in `group_vars/all.yml` (or copy certs to `/etc/minio/certs/`).

---

That’s it — drop this alongside your `requirements.txt`, run the playbook, and you’re ready to orchestrate Spark + Iceberg over a secure MinIO object store with Prefect.
