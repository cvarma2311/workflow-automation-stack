# Deploying Only Prefect Server and Agent

This guide provides step-by-step instructions to deploy only the Prefect server and agent using the provided Ansible repository.

## Prerequisites

1.  **Two Ubuntu 22.04 VMs:** One for the Prefect server (master) and one for the Prefect agent (worker).
2.  **IP Addresses:** The IP addresses for both VMs.
3.  **SSH Access:** You should have passwordless SSH access from your local machine (control node) to both VMs. Follow **Step 4: Set Up SSH Key-Based Access** in the `DEPLOYMENT_GUIDE.md` to set this up.
4.  **Ansible:** Ansible must be installed on your local machine.
5.  **Cloned Repository:** You have cloned this repository to your local machine.

## Step 1: Configure the VM IPs in `inventory.ini`

Ansible needs to know the IP addresses of your VMs.

1.  Open the `inventory.ini` file.
2.  You can remove or comment out all groups except for `[prefect_server]` and `[prefect_agents]`.
3.  Replace the placeholder IP addresses with the actual IP addresses of your master and worker VMs.

Your `inventory.ini` should look like this:

```ini
[prefect_server]
<master_vm_ip> ansible_ssh_private_key_file=/path/to/your/master_server_key ansible_user=<master_username>

[prefect_agents]
<worker_vm_ip> ansible_ssh_private_key_file=/path/to/your/worker_vm_key ansible_user=<worker_username>
```

Replace `<master_vm_ip>`, `<worker_vm_ip>`, `<master_username>`, and `<worker_username>` with the correct values. The `ansible_ssh_private_key_file` should be the absolute path to your private key.

## Step 2: Configure Prefect Variables

You need to update the Prefect settings in the `roles/common/vars/main.yml` file.

1.  Open `roles/common/vars/main.yml`.
2.  Find the `prefect_api_host` variable and change the IP to your master VM's IP address.

```yaml
# roles/common/vars/main.yml

# ... other variables
prefect_api_host: "http://<master_vm_ip>:4200"   # Prefect UI/API
# ... other variables
```

Replace `<master_vm_ip>` with your master VM's IP.

## Step 3: Modify the Prefect Ansible Role

The default `prefect` role tries to deploy an example flow that depends on Spark. To prevent errors, you need to disable the flow deployment tasks.

1.  Open the file `roles/prefect/tasks/main.yml`.
2.  Comment out the last three tasks: `Drop employee flow file`, `Build deployment`, and `Apply deployment`.

The end of your file should look like this:

```yaml
# roles/prefect/tasks/main.yml

# ... other tasks

- name: Enable & start Prefect agent
  ansible.builtin.systemd:
    name: prefect-agent
    state: started
    enabled: true
  when: inventory_hostname in groups['prefect_agents']

# - name: Drop employee flow file (wired to spark:// master)
#   ansible.builtin.template:
#     src: employee_flow_work_pool.py.j2
#     dest: "{{ prefect_flow_file }}"
#     mode: "0644"

# - name: Build deployment
#   ansible.builtin.shell: |
#     source "{{ prefect_install_venv }}/bin/activate"
#     prefect deployment build "{{ prefect_flow_file }}:{{ prefect_flow_name }}" \
#       -n "{{ prefect_deployment_name }}" --work-pool "{{ prefect_work_pool_name }}" \
#       -o "{{ prefect_home }}/{{ prefect_deployment_name }}.yaml"
#   args:
#     chdir: "{{ prefect_home }}"
#   when: inventory_hostname in groups['prefect_server']

# - name: Apply deployment
#   ansible.builtin.shell: |
#     source "{{ prefect_install_venv }}/bin/activate"
#     prefect deployment apply "{{ prefect_home }}/{{ prefect_deployment_name }}.yaml"
#   when: inventory_hostname in groups['prefect_server']
```

## Step 4: Create a New Ansible Playbook for Prefect

Create a new file named `prefect_only.yml` in the root of the repository with the following content. This playbook will only run the necessary roles for Prefect.

```yaml
---
- name: Deploy Common Dependencies
  hosts: prefect_server,prefect_agents
  become: true
  vars_files:
    - roles/common/vars/main.yml
  roles:
    - role: common
      tags: [ 'common' ]

- name: Deploy Prefect with Work Pools
  hosts: prefect_server,prefect_agents
  become: true
  roles:
    - role: prefect
      tags: [ 'prefect' ]
```

## Step 5: Run the Ansible Playbook

Now you can run the new playbook to deploy only Prefect.

From the root of the project on your local machine, run:

```bash
ansible-playbook -i inventory.ini prefect_only.yml
```

Ansible will use the keys specified in your `inventory.ini` file to connect to the VMs.

Ansible will now connect to your VMs and install the Prefect server and agent.

## Step 6: Verify the Deployment

Once the playbook is finished, you can verify that Prefect is working.

1.  **Prefect UI:** Open your web browser and go to `http://<master_vm_ip>:4200`.
2.  **Prefect Work Pool:** In the Prefect UI, go to the "Work Pools" section. You should see `default-pool`.
3.  **Check Services:** You can SSH into your VMs and check the status of the services:
    *   On the master VM: `sudo systemctl status prefect-server`
    *   On the worker VM: `sudo systemctl status prefect-agent`

You now have a running Prefect server and agent.
