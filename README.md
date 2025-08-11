# README.md — Spark + Iceberg + MinIO (TLS) + PostgreSQL + Prefect on 3 VMs

This repo is an **Ansible-based, production-ready bootstrap** that brings up a full data stack on three VMs:

- **MinIO (distributed, TLS)** for object storage (S3-compatible)  
- **Apache Spark 3.5.x (Standalone)** for compute  
- **Apache Iceberg** (Spark runtime) + **PostgreSQL 17** as the **Iceberg JDBC catalog**  
- **Prefect 2** (server + agent) for orchestration, **wired to submit jobs to Spark master**  
- Optional **UFW** firewall hardening

It also deploys:
- A **Prefect flow** that writes/reads **Iceberg tables** (intermediate data) in MinIO  
- An **on-demand `spark-submit` script** you can run manually

---

## 1) Repository Layout

```
iceberg-stack/
├─ inventory.ini                      # Ansible hosts (your 3 VM IPs)
├─ group_vars/
│  └─ all.yml                         # Global versions, credentials, ports, and stack config
├─ templates/
│  ├─ minio.service.j2                # systemd: MinIO distributed service
│  ├─ minio.env.j2                    # env vars for MinIO (root user/password)
│  ├─ spark-defaults.conf.j2          # Spark config: Spark master, Iceberg catalog, S3A, TLS truststore
│  ├─ spark-master.service.j2         # systemd: Spark Standalone master
│  ├─ spark-worker.service.j2         # systemd: Spark worker (joins the master)
│  ├─ spark-env.sh.j2                 # optional Spark env file (JAVA_HOME, master host/ports)
│  ├─ prefect-server.service.j2       # systemd: Prefect server (API/UI)
│  ├─ prefect-agent.service.j2        # systemd: Prefect agent (pulls & runs flows)
│  ├─ employee_flow.py.j2             # Prefect flow: demo pipeline using Iceberg tables
│  └─ run_employee_job.sh.j2          # On-demand spark-submit demo job (writes/reads Iceberg tables)
└─ site.yml                           # The Ansible playbook (all roles end-to-end)
```

### What each file does

- **inventory.ini**  
  Defines 3 host groups: `[minio]`, `[postgres]`, `[spark]`, and `[prefect]`.  
  Put your three VM IPs here. The first IP (e.g. `1.1.1.1`) acts as **MinIO primary**, **PostgreSQL**, **Spark master**, and **Prefect**.

- **group_vars/all.yml**  
  Centralized variables: exact software versions, credentials, endpoints, TLS settings, Spark master host/ports, and Prefect deployment names. **Edit this file** to change passwords, pin versions, or restrict firewall rules.

- **templates/minio.service.j2** / **minio.env.j2**  
  Installs MinIO in **distributed mode** across the 3 nodes, with creds from `all.yml`. Supports TLS when certs are present in `/etc/minio/certs`.

- **templates/spark-defaults.conf.j2**  
  Sets:
  - `spark.master=spark://<master>:7077`
  - Iceberg **JDBC catalog** pointing to PostgreSQL
  - S3A endpoint pointing to **MinIO over HTTPS**
  - Java truststore options so Spark trusts the (self-signed) MinIO TLS cert  
  This is used by both the Prefect flow and the manual job.

- **templates/spark-master.service.j2** / **spark-worker.service.j2**  
  Spark **Standalone** master and workers as systemd services.  
  Web UIs: master `:8080`, workers `:8081`. RPC at `:7077`.

- **templates/spark-env.sh.j2**  
  Helper env file for Spark (JAVA_HOME + master ports/host). Optional but included.

- **templates/prefect-server.service.j2** / **prefect-agent.service.j2**  
  Prefect Server (UI/API at `:4200`) and Prefect Agent (listens on the “default” queue).

- **templates/employee_flow.py.j2**  
  A Prefect flow (two tasks):  
  1) Create a small DataFrame and **write an Iceberg table** `local.db.active_employees`  
  2) Read that table, group by department, and log results.

- **templates/run_employee_job.sh.j2**  
  Simple shell script to `spark-submit` a PySpark job that writes & reads the same table — a manual test outside of Prefect.

- **site.yml**  
  The **master Ansible playbook**. It:
  1) Installs base dependencies (Java, Python, etc.)
  2) Deploys and configures MinIO with TLS
  3) Deploys PostgreSQL for Iceberg catalog
  4) Deploys Spark Standalone master & workers
  5) Configures Spark to use Iceberg + MinIO (HTTPS)
  6) Deploys Prefect server + agent
  7) Registers the demo flow
  8) (Optional) Configures UFW firewall rules

---

## 2) Prerequisites

- **Control node** with Ansible ≥ 2.14
- **Three Ubuntu 22.04 VMs** (bare metal or VMs, on-prem or cloud)
- SSH key-based access from control node to all VMs
- At least **8 GB RAM per node**, 4 vCPUs recommended

---

## 3) How to run

1. **Edit `inventory.ini`** to match your VM IPs.

2. **Edit `group_vars/all.yml`** to set:
   - Passwords for MinIO, PostgreSQL, Prefect
   - Hostnames/IPs
   - TLS settings (self-signed or real certs)

3. From your control node:

```bash
ansible-playbook -i inventory.ini site.yml
```

4. When finished:
   - MinIO Console: `https://<minio_primary_host>:9001`  
   - Spark Master UI: `http://<spark_master_host>:8080`  
   - Prefect UI: `http://<prefect_host>:4200`  
   - PostgreSQL: port `5432` (Iceberg catalog DB)

5. **Test Prefect flow**:
   - In Prefect UI, trigger the `employee-flow` deployment.

6. **Test manual Spark job**:
```bash
ssh <spark_master_host>
bash /opt/spark-jobs/run_employee_job.sh
```

---

## 4) Notes

- Iceberg metadata stored in PostgreSQL (`iceberg_catalog` DB)
- Intermediate data stored in MinIO under `s3a://intermediate/`
- Spark Standalone cluster ensures all Prefect-submitted jobs run distributed
- TLS cert for MinIO imported into Java truststore for Spark S3A

---

## 5) Cleanup

To remove all services and data:

```bash
ansible-playbook -i inventory.ini cleanup.yml
```

(*`cleanup.yml` not included; write as needed*)
