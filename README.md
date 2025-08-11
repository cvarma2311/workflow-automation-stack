# README.md — Spark + Iceberg + MinIO (TLS) + PostgreSQL + Prefect on 2 VMs

This repo is an **Ansible-based, production-ready bootstrap** that brings up a full data stack on two VMs, with a modular and extensible design for future scaling:

- **MinIO (standalone, TLS)** for object storage (S3-compatible)  
- **Apache Spark 3.5.x (Standalone)** for compute  
- **Apache Iceberg** (Spark runtime) + **PostgreSQL 17** as the **Iceberg JDBC catalog**  
- **Prefect 2** (server + agent) for orchestration, **wired to submit jobs to Spark master**  
- Optional **UFW** firewall hardening

It also deploys:
- A **Prefect flow** that writes/reads **Iceberg tables** (intermediate data) in MinIO  
- An **on-demand `spark-submit` script** you can run manually

---

## 1) Repository Layout (Modular Roles)

This project is now structured using Ansible roles for better organization and scalability.

```
workflow-automation-stack/
├─ inventory.ini                      # Ansible hosts (your 2 VM IPs)
├─ roles/                             # Modular Ansible roles for each component
│  ├─ common/                         # Common packages, Java, and global variables
│  │  ├─ tasks/main.yml
│  │  └─ vars/main.yml                # Global versions, credentials, ports, and stack config
│  ├─ minio/                          # MinIO installation and configuration
│  │  ├─ tasks/main.yml
│  │  ├─ templates/minio.env.j2
│  │  └─ templates/minio.service.j2
│  ├─ postgresql/                     # PostgreSQL installation and configuration
│  │  └─ tasks/main.yml
│  ├─ spark/                          # Spark installation and configuration
│  │  ├─ tasks/main.yml
│  │  └─ templates/...                # Spark-related templates
│  ├─ prefect/                        # Prefect installation and configuration
│  │  ├─ tasks/main.yml
│  │  └─ templates/...                # Prefect-related templates
│  └─ ufw/                            # UFW firewall configuration
│     └─ tasks/main.yml
└─ site.yml                           # The main Ansible playbook orchestrating all roles
```

### What each component does

- **`inventory.ini`**  
  Defines host groups for your two VMs. The first VM (e.g., `150.230.139.113`) acts as **MinIO primary**, **PostgreSQL**, **Spark master**, and **Prefect server/agent**. The second VM (e.g., `129.159.224.74`) acts as a **Spark worker** and **Prefect agent**.

- **`roles/common/vars/main.yml`**  
  Centralized variables: exact software versions, credentials, endpoints, TLS settings, Spark master host/ports, and Prefect deployment names. **Edit this file** to change passwords, pin versions, or restrict firewall rules.

- **`roles/minio/`**  
  Installs MinIO in **standalone mode** on the designated primary host. Supports TLS when certs are present.

- **`roles/spark/`**  
  Installs Spark **Standalone** master and workers as systemd services. Configures Spark to use Iceberg + MinIO (HTTPS).

- **`roles/postgresql/`**  
  Installs PostgreSQL for the Iceberg catalog.

- **`roles/prefect/`**  
  Installs Prefect Server (UI/API) and Prefect Agent (listens on the “default” queue). Also deploys the demo flow.

- **`roles/ufw/`**  
  Configures UFW firewall rules.

- **`site.yml`**  
  The **master Ansible playbook**. It orchestrates the deployment by calling each role in sequence.

---

## 2) Prerequisites

- **Control node** with Ansible ≥ 2.14
- **Two Ubuntu 22.04 VMs** (bare metal or VMs, on-prem or cloud)
- **SSH key-based access** from your control node to both VMs (detailed steps below)
- At least **8 GB RAM per node**, 4 vCPUs recommended

### Setting up SSH Key-Based Access

Ansible connects to your VMs via SSH. For a smooth, passwordless experience, it's highly recommended to set up SSH key-based authentication.

**Scenario A: You have an SSH key pair (e.g., `id_rsa` and `id_rsa.pub`) and want to copy the public key to your VMs.**

1.  **Generate an SSH Key Pair (if you don't have one):**
    Open a terminal on your **control node** and run:
    ```bash
    ssh-keygen -t rsa -b 4096
    ```
    *   Press Enter to accept the default file location (`~/.ssh/id_rsa`).
    *   You can enter a passphrase for added security (recommended), or leave it empty for no passphrase.

2.  **Copy your Public SSH Key to your VMs:**
    Use `ssh-copy-id` to easily copy your public key to each VM. Replace `user` with your VM's username (e.g., `ubuntu` or `root`) and `your_vm_ip` with the actual IP address of your VM.

    ```bash
    ssh-copy-id user@150.230.139.113
    ssh-copy-id user@129.159.224.74
    ```
    *   You will be prompted for the VM's password (the only time you'll need it for SSH).
    *   If `ssh-copy-id` is not available, you can manually copy the content of `~/.ssh/id_rsa.pub` and append it to `~/.ssh/authorized_keys` on each VM.

**Scenario B: You only have a private SSH key file (e.g., `my_vm_key.key`) and no password for the VM.**

1.  **Ensure your private key has the correct permissions:**
    Your private key file (e.g., `my_vm_key.key`) should only be readable by you.
    ```bash
    chmod 400 /path/to/your/my_vm_key.key
    ```

2.  **Copy your Public SSH Key to your VMs using your private key:**
    You can use `ssh-copy-id` with the `-i` flag to specify your private key for authentication. This will use your key for authentication instead of prompting for a password.

    ```bash
    ssh-copy-id -i /path/to/your/my_vm_key.key user@150.230.139.113
    ssh-copy-id -i /path/to/your/my_vm_key.key user@129.159.224.74
    ```
    *   Replace `/path/to/your/my_vm_key.key` with the actual path to your private key file.
    *   Replace `user` with your VM's username.
    *   `ssh-copy-id` will automatically find the corresponding public key (`my_vm_key.key.pub` if it exists in the same directory) or generate it from the private key if it doesn't.

    **Alternatively, manually copy the public key if `ssh-copy-id` is not suitable:**
    *   **Extract the public key from your private key (if you don't have a `.pub` file):**
        ```bash
        ssh-keygen -y -f /path/to/your/my_vm_key.key > /path/to/your/my_vm_key.key.pub
        ```
    *   **Copy the public key to the VM:**
        Use `ssh` with your private key to execute commands on the remote VM.
        ```bash
        ssh -i /path/to/your/my_vm_key.key user@150.230.139.113 "mkdir -p ~/.ssh && chmod 700 ~/.ssh && echo \"$(cat /path/to/your/my_vm_key.key.pub)\" >> ~/.ssh/authorized_keys && chmod 600 ~/.ssh/authorized_keys"
        ssh -i /path/to/your/my_vm_key.key user@129.159.224.74 "mkdir -p ~/.ssh && chmod 700 ~/.ssh && echo \"$(cat /path/to/your/my_vm_key.key.pub)\" >> ~/.ssh/authorized_keys && chmod 600 ~/.ssh/authorized_keys"
        ```
        This command:
        *   Creates the `.ssh` directory if it doesn't exist.
        *   Sets correct permissions for `.ssh`.
        *   Appends your public key to `authorized_keys`.
        *   Sets correct permissions for `authorized_keys`.

**After either Scenario A or B:**

3.  **Verify SSH Connection:**
    Test that you can now SSH into your VMs without being prompted for a password.
    *   If you used `id_rsa` (Scenario A):
        ```bash
        ssh user@150.230.139.113
        ssh user@129.159.224.74
        ```
    *   If you used a specific private key (Scenario B):
        ```bash
        ssh -i /path/to/your/my_vm_key.key user@150.230.139.113
        ssh -i /path/to/your/my_vm_key.key user@129.159.224.74
        ```
    If you connect without a password prompt, you're all set!

---

## 3) How to run

1.  **Clone this repository** to your **control node**:
    ```bash
    git clone https://github.com/your-repo-url/workflow-automation-stack.git # Replace with actual repo URL
    cd workflow-automation-stack
    ```

2.  **Review and Update Variables:**
    *   The `inventory.ini` file has already been updated with the two VM IPs you provided. If your VM IPs change, you will need to update this file accordingly.
    *   **Crucially, review and update sensitive credentials** in `roles/common/vars/main.yml` (e.g., `minio_root_password`, `pg_password`). These are placeholders and *must* be changed for security.
    *   Adjust `admin_allow_cidr` in `roles/common/vars/main.yml` if you want to restrict firewall access to specific IPs.

3.  **Run the Ansible Playbook:**
    From the root directory of this project on your **control node**:
    ```bash
    ansible-playbook -i inventory.ini site.yml
    ```
    **Important Note:** If you are using a private key other than the default `~/.ssh/id_rsa` (i.e., Scenario B in SSH setup), you'll need to tell Ansible to use your private key for authentication when running the playbook:
    ```bash
    ansible-playbook -i inventory.ini site.yml --private-key /path/to/your/my_vm_key.key
    ```
    Ansible will connect to your VMs via SSH and provision them according to the playbook.

4.  **Verification (After Deployment):**
    *   **MinIO Console:** `https://150.230.139.113:9001` (Use the `minio_root_user` and `minio_root_password` from `roles/common/vars/main.yml`)
    *   **Spark Master UI:** `http://150.230.139.113:8080`
    *   **Prefect UI:** `http://150.230.139.113:4200`
    *   **Test Prefect flow**: In the Prefect UI, navigate to the "Deployments" section and trigger the `employee-flow` deployment.
    *   **Test manual Spark job**: SSH to your first VM (`150.230.139.113`) and run:
        ```bash
        bash /opt/prefect/jobs/run_employee_job.sh
        ```

---

## 4) Notes

- Iceberg metadata stored in PostgreSQL (`iceberg_catalog` DB)
- Intermediate data stored in MinIO under `s3a://iceberg-warehouse/`
- Spark Standalone cluster ensures all Prefect-submitted jobs run distributed
- TLS cert for MinIO imported into Java truststore for Spark S3A

---

## 5) Flexibility for Future Expansion

The modular role structure allows for easier scaling:

-   **Adding more Spark Workers:** To add more Spark workers, simply add their IPs to the `[spark_workers]` group in `inventory.ini` and re-run the playbook. The `spark` role is designed to deploy workers to all hosts in this group.
-   **Adding more Prefect Agents:** Similarly, add new VM IPs to the `[prefect_agents]` group in `inventory.ini` and re-run the playbook.
-   **Scaling MinIO/PostgreSQL:** If you need to scale MinIO to a distributed cluster or set up a PostgreSQL cluster, this would require more significant changes to the respective roles, as they are currently configured for single-node deployments. However, the modular role structure makes it easier to modify these specific roles without affecting the entire setup.

---

## 6) Cleanup

To remove all services and data:

```bash
ansible-playbook -i inventory.ini cleanup.yml
```

(*`cleanup.yml` not included; write as needed*)
