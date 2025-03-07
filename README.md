##  Resource module builder for Ciena

### Overview

Generates modules for:

* Waveserver Ai
* SAOS 10
* Waveserver 5
* RLS

### Resource Module Builder

The playbooks in this project generate modules for Ciena collections using the resource module builder.

Usage:

```bash
pip install git+https://github.com/ansible-network/collection_prep.git
# Download some yangs for the device type you are working on
ansible-playbook yang_get.yml
# Convert the yangs to RMB json
./generate_models.sh

# Generate the module code
ansible-playbook generate_saos10.yml
ansible-playbook generate_waveserver5.yml
```
