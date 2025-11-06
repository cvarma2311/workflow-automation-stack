# Plan: Deploying a Monitoring Stack

## 1. Objective

This document outlines the plan to deploy a comprehensive monitoring stack onto the Docker Swarm cluster. The goal is to gain visibility into the resource consumption (CPU, memory, network) of all running services, including Prefect and MinIO, to diagnose performance bottlenecks.

## 2. Proposed Solution

The chosen solution is the industry-standard stack of Prometheus, Grafana, and cAdvisor, which provides a powerful and flexible monitoring platform for containerized environments.

- **Prometheus:** To collect and store time-series metrics.
- **Grafana:** To visualize the collected metrics in dashboards.
- **cAdvisor:** To expose container-level metrics from every node.
- **Node Exporter:** To expose host-level (VM) metrics.

## 3. Implementation Steps

### 3.1. New Files and Configuration

- **`monitoring-stack.yml`:** A new Docker Compose file will be created in the `ansible_swarm_setup/` directory. It will define the `prometheus`, `grafana`, `cadvisor`, and `node-exporter` services.
    - The `cadvisor` and `node-exporter` services will be deployed in `global` mode to run on every node.
    - The `prometheus` and `grafana` services will be constrained to run on a manager node.

- **`prometheus.yml.j2`:** A Jinja2 template for the Prometheus configuration will be created. It will be configured to use Docker Swarm's DNS service discovery to automatically find and scrape all `cadvisor` and `node-exporter` tasks.

- **`docker-swarm-dashboard.json`:** A pre-built Grafana dashboard definition will be downloaded and included. This will be automatically provisioned into Grafana to provide an immediate, detailed view of the cluster's performance.

### 3.2. Ansible Playbook Modifications

- A new play, "Deploy Monitoring Stack," will be added to `setup_swarm.yml`.
- This play will be assigned the tag `monitoring` to allow for independent deployment.
- The play will contain tasks to:
    1. Copy the new configuration files (`monitoring-stack.yml`, `prometheus.yml.j2`, etc.) to the manager node.
    2. Deploy the stack using the `community.docker.docker_stack` module.

### 3.3. Documentation Updates

The `HOW_TO_RUN.md` guide will be updated to include:

- A new section explaining the monitoring stack.
- Instructions on how to access the Grafana UI (on port 3000).
- The command to deploy the stack using `--tags "monitoring"`.
- An overview of the metrics that will be available in the Grafana dashboard.
