# How to Run the Automated Docker Swarm Deployment

## 1. Introduction

This guide provides detailed instructions on how to use the Ansible project in this directory to automatically deploy a full Docker Swarm cluster and run the MinIO and Prefect application stacks.

The playbook automates everything from installing Docker on fresh Ubuntu VMs to deploying the final services. **This setup uses MinIO's native distributed mode, deploying one MinIO instance on each node of the cluster for a resilient and performant object store. It also ensures that the Prefect server runs on the manager node, while Prefect workers (formerly agents) run on the worker nodes.**

## 2. Prerequisites

Before you begin, ensure you have the following:

- **A Local Machine:** Your computer, where you will run the Ansible commands.
- **Python and Pip:** You need a Python environment to run Ansible.
- **Project Dependencies:** Install all the necessary Python packages and Ansible collections by running the following commands from the root of the project:
  ```bash
  pip install -r requirements.txt
  ansible-galaxy collection install community.docker
  ```
- **Fresh Ubuntu VMs:** A set of new Ubuntu VMs (22.04 is recommended) with known IP addresses. For MinIO's distributed mode to be effective, you should have at least 4 nodes, which is the minimum for erasure coding.
- **SSH Access:** You must have SSH key-based access from your local machine to all the Ubuntu VMs. Ensure your public key is in the `~/.ssh/authorized_keys` file on each VM for the user you will connect with.

## 3. Configuration

Before running the playbook, you need to configure it for your specific environment.

### 3.1. Server Inventory (`inventory.ini`)

This is the most important file to edit. Open `inventory.ini` and configure the IP addresses and SSH connection details for your servers.

- **Host Groups (`[managers]`, `[workers]`):** Place the IP addresses of your VMs into the appropriate groups. The `ansible_host` parameter is where the IP goes.
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
worker-3 ansible_host=198.51.100.13 ansible_user=ubuntu ansible_ssh_private_key_file=~/.ssh/worker.key

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

The playbook creates a directory on each node at `/mnt/minio/data` to be used by that node's MinIO instance. If you need to use a different path, you can change it in the `setup_swarm.yml` playbook, in the play named `Create MinIO data directories on all nodes`.

## 4. Run the Deployment

Once your configuration is complete, you can run the master playbook. The playbook is tagged to allow for granular deployments.

### 4.1. Full Deployment (MinIO + Prefect)

To deploy or update the entire stack, run the playbook without any tags. This is the default behavior.

```bash
ansible-playbook -i ansible_swarm_setup/inventory.ini ansible_swarm_setup/setup_swarm.yml
```

### 4.2. Deploying Only Prefect

To deploy or update only the Prefect stack, run the playbook and specify the `prefect` tag. This will run all tasks required for Prefect, including shared prerequisites like Docker and Swarm setup, while skipping all MinIO-specific tasks.

```bash
ansible-playbook -i ansible_swarm_setup/inventory.ini ansible_swarm_setup/setup_swarm.yml --tags "prefect"
```

### 4.3. Deploying Only MinIO

To deploy or update only the MinIO stack, run the playbook and specify the `minio` tag. This will run all tasks required for MinIO, including shared prerequisites, while skipping all Prefect-specific tasks.

```bash
ansible-playbook -i ansible_swarm_setup/inventory.ini ansible_swarm_setup/setup_swarm.yml --tags "minio"
```

### 4.4. Deploying the Monitoring Stack

This project includes a monitoring stack based on Prometheus and Grafana to provide visibility into container and host metrics. To deploy it, use the `monitoring` tag.

```bash
ansible-playbook -i ansible_swarm_setup/inventory.ini ansible_swarm_setup/setup_swarm.yml --tags "monitoring"
```

Once deployed, you can access the Grafana dashboard by navigating to `http://<your_manager_ip>:3000`.

- **User:** `admin`
- **Password:** `grafana`

The Docker Swarm dashboard should be pre-loaded, allowing you to immediately see CPU, memory, and network usage for all containers.

Ansible will now perform all steps automatically. This may take several minutes.

## 5. Post-Deployment Verification

After the playbook finishes successfully:

1.  **Verify Swarm Nodes:** SSH into your manager node and run `docker node ls` to see all nodes in the cluster.

2.  **Verify Services:** On the manager, run `docker service ls` to see the MinIO and Prefect services running. You should see one `minio_stack_minio` task running on each node. You can also run `docker service ps <service_name>` (e.g., `docker service ps prefect_stack_prefect-server`) to verify that services are running on the correct nodes.

3.  **Verify MinIO Cluster Health (Optional):**

    To confirm that all MinIO instances have formed a single, healthy cluster, you can use the MinIO Client (`mc`). SSH into your manager node and follow these steps:

    a. **Install `mc`:**
    ```bash
    wget https://dl.min.io/client/mc/release/linux-amd64/mc
    chmod +x mc
    sudo mv mc /usr/local/bin/
    ```

    b. **Add your cluster as an alias:**
    ```bash
    mc alias set minio http://localhost:9000 minioadmin minioadmin
    mc alias set minio http://172.31.9.234:9000 minioadmin minioadmin
    ```
    *(Note: Replace `minioadmin minioadmin` if you changed the default credentials in the playbook).*

    c. **Check cluster info:**
    ```bash
    mc admin info minio
    ```

    You should see output confirming that all nodes are online (e.g., `Status: 4/4 online`). This proves that the distributed, erasure-coded cluster is working correctly.

4.  **Access Web UIs:**
    - **MinIO:** `http://<IP_of_ANY_swarm_node>:9001`
    - **Prefect:** `http://<IP_of_ANY_swarm_node>:4200`

5.  **Verify Prefect Work Pool:**
    - In the Prefect UI, go to the **Work Pools** page.
    - You should see the `my-docker-pool` already created and the workers connected to it, ready for work.

Your deployment is now complete and fully automated.

 Minio

  # Check Service Status:
    docker service ps minio_stack_minio

  # View Service Logs:
    docker service logs minio_stack_minio

  Prefect

  Check Service Status:

   # For the server
    docker service ps prefect_stack_prefect-server
   
   # For the worker
    docker service ps prefect_stack_prefect-worker

   # For the database
    docker service ps prefect_stack_postgres

  View Service Logs:

   # For the server
    docker service logs prefect_stack_prefect-server

   # For the worker
    docker service logs prefect_stack_prefect-worker

   # For the database
    docker service logs prefect_stack_postgres

   # the definitive configuration of the service.
    sudo docker service inspect minio_stack_minio

## 6. Troubleshooting

### 6.1. MinIO Network Verification

If you suspect issues with MinIO nodes not being able to communicate with each other, you can perform these checks from the manager node.

**1. Inspect the Overlay Network:**

This command shows which nodes are connected to the `ai-net` overlay network. You should see all your swarm nodes listed as peers.

```bash
sudo docker network inspect ai-net | grep Peers -A 10
```

**2. Test Connectivity Between MinIO Containers:**

This script will `exec` into one of the MinIO containers and test its ability to reach the other MinIO containers (`minio1` through `minio4`) over the network.

```bash
cid=$(sudo docker ps --filter "name=minio_stack_minio" -q | head -n 1)
sudo docker exec -it $cid sh -c '
for host in minio1 minio2 minio3 minio4; do
  echo "Testing connection to $host:9000"
  getent hosts $host && (echo > /dev/tcp/$host/9000 && echo "✅ reachable" || echo "❌ cannot connect")
done
'
```
All hosts should report as "✅ reachable". If not, there may be a firewall issue or a problem with the Docker overlay network.

## 7. Running the Example Data Pipeline

This project includes an example Prefect workflow (`prefect_minio_flow.py`) that demonstrates a multi-step data pipeline using MinIO for storage.

### 7.1. Overview of the Flow

1.  **Generate Data:** Creates 100,000 records and saves them to a Parquet file in the `prefect-data` bucket in MinIO.
2.  **Filter Data (Step 1):** Reads the raw data and filters for records with even-numbered IDs, saving the result to a new file in MinIO.
3.  **Filter Data (Step 2):** Reads the intermediate data and applies a final filter, saving the result to a final file in MinIO.

### 7.2. How to Deploy and Run

SSH into your **manager node** to perform the following steps.

**1. Deploy the Workflow:**

Run the following command from the `ansible_swarm_setup` directory to deploy the flow to your Prefect server. This makes the flow available to be run by your workers.

```bash
prefect deploy --name minio-pipeline --pool my-docker-pool prefect_minio_flow.py:minio_data_pipeline
```

**2. Trigger a Flow Run:**

- Navigate to the Prefect UI at `http://<your_manager_ip>:4200`.
- Go to the **Flows** page. You should see the `minio-data-pipeline` flow.
- Click the **Run** button to trigger a new execution of the pipeline.

**3. Observe the Execution:**

- Click on the new run to see the live graph. You can watch as each task is executed by a Prefect worker.
- Check the logs for each task to see the output, including the number of records being processed and the paths to the data in MinIO.
- Once complete, you can use the MinIO UI (`http://<your_manager_ip>:9001`) to browse the `prefect-data` bucket and inspect the final Parquet files.
