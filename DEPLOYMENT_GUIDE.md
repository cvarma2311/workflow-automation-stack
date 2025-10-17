# Deployment Guide: Step-by-Step

This guide provides detailed, step-by-step instructions for a junior developer to deploy the data stack using this Ansible repository. No prior knowledge of the stack is assumed.

## Prerequisites

Before you begin, make sure you have the following:

1.  **Two Ubuntu 22.04 VMs:** One will be the **master** node (running the Prefect server, Spark master, etc.), and the other will be the **worker** node.
2.  **IP Addresses:** The IP addresses for both VMs.
3.  **SSH Access:** You should be able to SSH into both VMs from your local machine.
4.  **Ansible:** Ansible must be installed on your local machine (the control node).

## Step 1: Get the Code

First, you need to clone this repository to your local machine.

```bash
git clone <repository_url>
cd <repository_name>
```

## Step 2: Configure the VM IPs

Ansible needs to know the IP addresses of your VMs. You will put them in the `inventory.ini` file.

1.  Open the `inventory.ini` file in a text editor.
2.  You will see several groups like `[minio]`, `[postgres]`, `[spark_master]`, `[spark_workers]`, `[prefect_server]`, and `[prefect_agents]`.
3.  Replace the placeholder IP addresses with the actual IP addresses of your master and worker VMs as described in the file.

## Step 3: Configure Passwords and Settings

For security, you must change the default passwords.

1.  Open the `roles/common/vars/main.yml` file.
2.  This file contains all the important settings for the stack.
3.  Find the following variables and change their default values:
    *   `minio_root_password`
    *   `pg_password`
4.  Review the other variables in this file. You may not need to change them, but it is good to know what they are.

## Step 4: Set Up SSH Key-Based Access

Ansible uses SSH to connect to your VMs. To avoid using passwords, you should set up SSH key-based authentication. This is a one-time setup.

1.  **Check for an existing SSH key:** On your local machine, run:
    ```bash
    ls -al ~/.ssh/id_rsa.pub
    ```
    If you see a file, you already have a key. If not, you need to generate one.

2.  **Generate a new SSH key (if you don't have one):**
    ```bash
    ssh-keygen -t rsa -b 4096
    ```
    Press Enter to accept the default file location and you can optionally add a passphrase.

3.  **Copy your SSH key to the VMs:** This is the most important step. You need to copy your public SSH key to both of your VMs.
    ```bash
    ssh-copy-id <your_vm_user>@<master_vm_ip>
    ssh-copy-id <your_vm_user>@<worker_vm_ip>
    ```
    Replace `<your_vm_user>` with the username you use to SSH into your VMs (e.g., `ubuntu`), and `<master_vm_ip>` and `<worker_vm_ip>` with the actual IPs.

4.  **Test your SSH connection:**
    ```bash
    ssh <your_vm_user>@<master_vm_ip>
    ```
    If you can connect without a password, you are ready for the next step.

## Step 5: Run the Ansible Playbook

Now you are ready to run the Ansible playbook to deploy the stack.

1.  From the root of this project on your local machine, run the following command:
    ```bash
    ansible-playbook -i inventory.ini site.yml
    ```
2.  If you are using a specific SSH key that is not the default `id_rsa`, you need to tell Ansible where to find it:
    ```bash
    ansible-playbook -i inventory.ini site.yml --private-key /path/to/your/private_key
    ```
3.  Ansible will now connect to your VMs and install everything. This will take some time. You will see a lot of output on your screen.

## Step 6: Verify the Deployment

Once the playbook is finished, you can verify that everything is working.

1.  **MinIO Console:** Open your web browser and go to `https://<master_vm_ip>:9001`.
2.  **Spark Master UI:** Open your web browser and go to `http://<master_vm_ip>:8080`.
3.  **Prefect UI:** Open your web browser and go to `http://<master_vm_ip>:4200`.
4.  **Prefect Work Pool:** In the Prefect UI, go to the "Work Pools" section. You should see your work pool (e.g., `default-pool`).
5.  **Prefect Flow:** In your work pool, you should see the `employee-flow` deployment ready to be run.

Congratulations! You have successfully deployed the data stack.
