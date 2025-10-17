# How to Run the Automated Docker Swarm Deployment

## 1. Introduction

This guide provides detailed instructions on how to use the Ansible project in this directory to automatically deploy a full Docker Swarm cluster and run the MinIO and Prefect application stacks. 

The playbook automates everything from installing Docker on fresh Ubuntu VMs to deploying the final services.

## 2. Prerequisites

Before you begin, ensure you have the following:

- **A Local Machine:** Your computer, where you will run the Ansible commands.
- **Ansible Installed:** If you don't have it, you can install it via `pip` or `brew`.
- **Ansible Docker Collection:** The playbook requires this. Install it with:
  ```bash
  ansible-galaxy collection install community.docker
  ```
- **Fresh Ubuntu VMs:** A set of new Ubuntu VMs (22.04 is recommended) with known IP addresses.
- **SSH Access:** You must have SSH key-based access from your local machine to all the Ubuntu VMs. Ensure your public key is in the `~/.ssh/authorized_keys` file on each VM for the user you will connect with.

## 3. Configuration

Before running the playbook, you need to configure it for your specific environment.

### 3.1. Server Inventory (`inventory.ini`)

This is the most important file to edit. Open `inventory.ini` and configure the IP addresses and SSH connection details for your servers.

- **Host Groups (`[managers]`, `[workers]`, `[storage]`):** Place the IP addresses of your VMs into the appropriate groups. The `ansible_host` parameter is where the IP goes.
- **Connection Variables (`ansible_user`, `ansible_ssh_private_key_file`):** You can define the SSH username and path to your private key (`.key` or `.pem` file) in two ways:

    1.  **Per-Host (Most Flexible):** If your VMs have different users or keys, define them on the same line as the host. This is the recommended approach for clarity.
    2.  **Globally (in `[all:vars]`):** If all your VMs share the same user and key, you can set it once in the `[all:vars]` section.

**Example `inventory.ini` with Per-Host Variables:**
```ini
[managers]
# This manager uses the 'admin' user and a specific key
manager-1 ansible_host=198.51.100.10 ansible_user=admin ansible_ssh_private_key_file=~/.ssh/manager.key

[workers]
# These workers use the 'ubuntu' user and a different key
worker-1 ansible_host=198.51.100.11 ansible_user=ubuntu ansible_ssh_private_key_file=~/.ssh/worker.key
worker-2 ansible_host=198.51.100.12 ansible_user=ubuntu ansible_ssh_private_key_file=~/.ssh/worker.key

[storage]
# The storage node must also be defined here
worker-1 ansible_host=198.51.100.11 ansible_user=ubuntu ansible_ssh_private_key_file=~/.ssh/worker.key

[all:vars]
# You can leave this empty if you define variables per-host
```

### 3.2. Application Passwords (Recommended)

For security, you should change the default passwords for MinIO and PostgreSQL.

1.  Open the file `roles/stack_deploy/tasks/main.yml`.
2.  Find the task named `Define credentials`.
3.  Change the values for `minio_root_password` and `postgres_password`.

```yaml
- name: Define credentials
  ansible.builtin.set_fact:
    minio_root_user: "minioadmin"
    minio_root_password: "your-new-secure-minio-password" # <-- CHANGE THIS
    postgres_user: "prefect_user"
    postgres_password: "your-new-secure-pg-password"  # <-- CHANGE THIS
  run_once: true
```

### 3.3. MinIO Storage Path (Optional)

The playbook assumes you will store MinIO's data in `/mnt/nvme/minio/data` on the storage host.

If your persistent storage is located at a different path (e.g., `/data/storage`), you must update it in **two** places:

1.  `roles/stack_deploy/tasks/main.yml`: In the task `Create MinIO data directory on the storage node`, change the `path` value.
2.  `roles/stack_deploy/templates/docker-compose.minio.yml.j2`: In the `volumes` section for the `minio` service, change the host path part of the volume mount.

## 4. Run the Deployment

Once your configuration is complete, run the master playbook from the root of the `workflow-automation-stack` directory:

```bash
ansible-playbook -i ansible_swarm_setup/inventory.ini ansible_swarm_setup/setup_swarm.yml
```

Ansible will now perform all steps automatically. This may take several minutes.

## 5. Post-Deployment Verification

After the playbook finishes successfully:

1.  **Verify Swarm Nodes:** SSH into your manager node and run `docker node ls` to see all nodes in the cluster.

2.  **Verify Services:** On the manager, run `docker service ls` to see the MinIO and Prefect services running.

3.  **Access Web UIs:**
    - **MinIO:** `http://<IP_of_storage_node>:9001`
    - **Prefect:** `http://<IP_of_any_swarm_node>:4200`

4.  **Final Prefect Setup (One-time):**
    - In the Prefect UI, go to the **Work Pools** page.
    - Click the `+` button to create a new pool.
    - Select **Docker** as the infrastructure type.
    - Name the pool `my-docker-pool` and save it.
    - The Prefect agents will automatically find this pool and start looking for work.

Your deployment is now complete.
