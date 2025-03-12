#  Resource module builder for Ciena

## Overview

Generates modules for:

* Waveserver Ai
* SAOS 10
* Waveserver 5
* RLS

## Resource Module Builder

The playbooks in this project generate modules for Ciena collections using the resource module builder.

### Download YANGs

```bash
pip install git+https://github.com/ansible-network/collection_prep.git
# Download some yangs for the device type you are working on
ansible-playbook yang_get.yml
```

### Convert YANGs to Module Potentials

1. Convert the yangs to a module format. This will create a yml file for each yang.
2. Each produced yml file contains:
* xml_namespace
* Dictionary of the potential modules

```bash
./generate_potential_modules.sh
```

### Convert Potential Modules to Modules

The potential modules are the modules that might be created. The structure of each is evaluated to determine the best structure for each module.
Potential YML data structures are:
* single module containing single list (fds, fps, bgp)
* single module containing a list and some properties (g8032-rings)
* multiple modules each containing a single list (flexe)
* single module containing a dictionary (???)

To handle each of these cases the following steps are taken:

1. Determine the structure of the potential module
2. Create a module for each potential module
3. Create a merged example file for each module
4. Create a deleted example file for each module
5. Create a module for each potential module

For all output modules, the following properties are set:
* XML_NAMESPACE
* XML_ROOT_KEY

For a single list module, the module is created with the list as the main resource. The additional properties are set:
* XML_ITEMS
* XML_ITEMS_KEY

For potential modules structures that contain a list and some properties, the module is created with the list as the main resource. The additional properties are created in a separate module. The separate module is named `{network_os}_{module_name}__properties`.

```bash
./generate_modules.py
```

### Convert Modules to collection code

```bash
# Generate the module code
ansible-playbook generate_saos10.yml
ansible-playbook generate_waveserver5.yml
```
