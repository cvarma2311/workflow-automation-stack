# Plan: Fully Automated Docker Swarm Deployment with Ansible

## 1. Objective

This document outlines the plan to create a self-contained Ansible project that automates the entire process of building a Docker Swarm cluster and deploying the MinIO and Prefect application stacks. 

The goal is to start with a set of fresh Ubuntu VMs and end with a running, multi-node application cluster, with all steps managed by Ansible. **This plan uses MinIO's native distributed mode for resilient object storage.**

## 2. Ansible Project Structure

We will create a new directory, `ansible_swarm_setup/`, which will contain the following structure:

```
ansible_swarm_setup/
├── inventory.ini
├── setup_swarm.yml
└── roles/
    ├── docker/
    │   └── tasks/main.yml
    ├── swarm_manager/
    │   └── tasks/main.yml
    ├── swarm_worker/
    │   └── tasks/main.yml
    └── stack_deploy/
        ├── tasks/main.yml
        └── templates/
            ├── docker-compose.minio.yml.j2
            └── docker-compose.prefect.yml.j2
```

- **`inventory.ini`**: Where you will define the IP addresses of your manager and worker VMs.
- **`setup_swarm.yml`**: The master playbook you will execute.
- **`roles/docker/`**: An Ansible role to install Docker Engine on all VMs.
- **`roles/swarm_manager/`**: A role to initialize Docker Swarm on the manager node and create the necessary network.
- **`roles/swarm_worker/`**: A role to make worker nodes join the swarm.
- **`roles/stack_deploy/`**: A role to deploy the MinIO and Prefect application stacks onto the cluster.

## 3. The Automated Workflow

When you run the final `ansible-playbook` command, the following will happen automatically:

1.  **Install Docker:** The `docker` role will run on all your VMs. It will add the official Docker repository, install the Docker engine, and ensure the service is running.

2.  **Create MinIO Storage Directories:** A task will run on all VMs to create a local directory (`/mnt/minio/data`) for each MinIO instance to store its data.

3.  **Initialize Swarm:** The `swarm_manager` role will run on your designated manager VM. It will initialize the Swarm and securely capture the unique join-token required for worker nodes.

4.  **Join Workers:** The `swarm_worker` role will run on all your worker VMs. It will use the token captured in the previous step to securely join the Swarm cluster.

5.  **Create Network:** The `swarm_manager` role will also create the `ai-net` overlay network that the application services will use for communication.

6.  **Deploy Applications:** Finally, the `stack_deploy` role will run on the manager. It will:
    - Create the required Docker Secrets for MinIO credentials.
    - Copy the Docker Compose files to the manager.
    - Execute `docker stack deploy` to launch the MinIO, Prefect Server, and Prefect Agent services onto the cluster. **MinIO will be deployed as a global service, with one instance on each node, running in its native distributed mode. The Prefect server will be constrained to the manager node, and Prefect agents will run on the worker nodes.**

## 4. Your Instructions

Once this Ansible project is built, your only manual steps will be:

1.  **Edit `inventory.ini`**: Add the IP addresses and any necessary SSH details for your fresh Ubuntu VMs.
2.  **Run the Ansible Playbook**: Execute the master playbook from your local machine:
    ```bash
    ansible-playbook -i inventory.ini setup_swarm.yml
    ```
3.  **Create Prefect Work Pool (One-time setup):** After the playbook completes, access the Prefect UI at `http://<any_swarm_node_ip>:4200`. Navigate to the "Work Pools" page and create a new pool:
    - Choose the **Docker** infrastructure type.
    - Name the pool `my-docker-pool`.
    - After creating the pool, the agents will automatically connect to it.

## 5. Next Steps

This document now reflects the complete plan. The next step is to proceed with the implementation.