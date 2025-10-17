# Docker Swarm Deployment Plan: MinIO & Prefect

## 1. Overview

This document outlines the implementation plan to deploy MinIO and Prefect as resilient, scalable services on a Docker Swarm cluster. This approach replaces the previous VM-based Ansible deployment with a modern, container-based architecture.

We will proceed in two main phases:
1.  **Deploy MinIO:** For S3-compatible object storage.
2.  **Deploy Prefect:** For workflow orchestration, including its required database.

All files related to this deployment will be stored in the `docker_swarm_deployment` directory.

## 2. Prerequisites

This plan assumes the following setup is already complete:

- **Docker Swarm Cluster:** A multi-node cluster has been initialized (`docker swarm init`) and worker nodes have joined.
- **Overlay Network:** A swarm-scoped overlay network has been created with the name `ai-net` (`docker network create --driver overlay ai-net`).
- **NVMe Storage:** At least one Swarm node has NVMe-backed storage available at a known, persistent path (e.g., `/mnt/nvme`).
- **SSH Access:** You have SSH access to the Swarm manager node to execute `docker` commands.

## 3. Networking Explained

Docker Swarm provides a sophisticated networking model that handles service discovery and routing.

### External Connections (Your Browser, External VMs)

- **Routing Mesh:** When we publish a port (e.g., `4200` for Prefect), Docker Swarm's "routing mesh" makes that service available on the published port across **every node in the cluster**.
- **How to Connect:** You can access a service using the IP address of **any** node in the swarm (e.g., `http://<IP_of_ANY_swarm_node>:4200`). The routing mesh automatically forwards your request to the correct container, wherever it may be running.
- **Firewall Prerequisite:** For this to work, you must **allow incoming traffic** on the published ports in your cloud security groups or on-premise firewalls:
    - `4200/tcp` (for Prefect UI)
    - `9000/tcp` (for MinIO API)
    - `9001/tcp` (for MinIO Console)

### Internal Connections (Service-to-Service)

- **Overlay Network & DNS:** All services (`minio`, `prefect-server`, `postgres`) will be attached to the `ai-net` overlay network. Docker provides automatic DNS service discovery on this network.
- **How Services Connect:** One service can find another simply by using its service name as a hostname. For example, the `prefect-server` will connect to its database using the hostname `postgres`. Docker's internal DNS resolves this to the correct container's private IP address on the `ai-net` network.

---

## 4. Phase 1: Deploy MinIO

### Step 1.1: Prepare the MinIO Storage Node

We must constrain the MinIO service to only run on the node(s) with NVMe storage.

1.  **Find Node ID:** On your Swarm manager, find the ID of the node with NVMe storage:
    ```bash
    docker node ls
    ```
2.  **Apply Node Label:** Apply a label to that node. This label will be used as a placement constraint.
    ```bash
    docker node update --label-add minio.storage=true <NODE_ID_FROM_STEP_1>
    ```
3.  **Create Storage Directory:** SSH into the labeled storage node and create the directory where MinIO's data will be persistently stored:
    ```bash
    mkdir -p /mnt/nvme/minio/data
    ```

### Step 1.2: Create Docker Secrets for MinIO

On your Swarm manager, create secrets to securely manage MinIO's credentials.

```bash
printf "minioadmin" | docker secret create minio_root_user -
printf "your-secure-minio-password" | docker secret create minio_root_password -
```

### Step 1.3: Create `docker-compose.minio.yml`

On your Swarm manager, create a file named `docker-compose.minio.yml` inside the `docker_swarm_deployment` directory with the following content:

```yaml
version: '3.8'

services:
  minio:
    image: minio/minio:latest
    command: server /data --console-address ":9001"
    ports:
      - "9000:9000"
      - "9001:9001"
    networks:
      - ai-net
    secrets:
      - minio_root_user
      - minio_root_password
    environment:
      MINIO_ROOT_USER_FILE: /run/secrets/minio_root_user
      MINIO_ROOT_PASSWORD_FILE: /run/secrets/minio_root_password
    volumes:
      - /mnt/nvme/minio/data:/data
    deploy:
      placement:
        constraints:
          - node.labels.minio.storage == true

networks:
  ai-net:
    external: true

secrets:
  minio_root_user:
    external: true
  minio_root_password:
    external: true
```

### Step 1.4: Deploy and Verify MinIO

1.  **Deploy the Stack:**
    ```bash
    docker stack deploy -c docker-compose.minio.yml minio_stack
    ```
2.  **Verify Service:** Check that the service is running. It may take a minute to start.
    ```bash
    docker service ls
    ```
3.  **Access Console:** Open your browser and navigate to `http://<storage_node_ip>:9001`.

---

## 5. Phase 2: Deploy Prefect

For Prefect, we will use an environment file (`.env`) to manage the database credentials. This is a common and straightforward pattern.

### Step 2.1: Create a `.env` file for PostgreSQL Credentials

On your Swarm manager, inside the `docker_swarm_deployment` directory, create a file named `.env` with the following content. Be sure to use a strong, secure password.

```.env
# This file stores credentials for the Prefect database
POSTGRES_USER=prefect_user
POSTGRES_PASSWORD=your-secure-pg-password
```

### Step 2.2: Create `docker-compose.prefect.yml`

On your Swarm manager, create a file named `docker-compose.prefect.yml` inside the `docker_swarm_deployment` directory. It will automatically read the variables from the `.env` file.

```yaml
version: '3.8'

services:
  postgres:
    image: postgres:14
    networks:
      - ai-net
    environment:
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
      POSTGRES_DB: prefect_server
    volumes:
      - prefect-db:/var/lib/postgresql/data

  prefect-server:
    image: prefecthq/prefect:latest-python3.11
    command: prefect server start --host 0.0.0.0
    ports:
      - "4200:4200"
    networks:
      - ai-net
    environment:
      PREFECT_API_DATABASE_CONNECTION_URL: "postgresql+asyncpg://${POSTGRES_USER}:${POSTGRES_PASSWORD}@postgres:5432/prefect_server"
    depends_on:
      - postgres

volumes:
  prefect-db:

networks:
  ai-net:
    external: true
```

### Step 2.3: Deploy and Verify Prefect

1.  **Deploy the Stack:** From the `docker_swarm_deployment` directory on your manager, run:
    ```bash
    docker stack deploy -c docker-compose.prefect.yml prefect_stack
    ```
2.  **Verify Services:** Check that both services are running.
    ```bash
    docker service ls
    ```
3.  **Access UI:** Open your browser and navigate to `http://<any_swarm_node_ip>:4200`.

## 6. Next Steps

Once MinIO and Prefect are confirmed to be running correctly, we can proceed with designing the deployment for Spark and the Prefect agent.
