# Resource module builder using Yang models

- [1. Overview](#1-overview)
- [2. Usage](#2-usage)
  - [2.1. Download yangs](#21-download-yangs)
  - [2.2. Create the module type directory and files](#22-create-the-module-type-directory-and-files)
  - [2.3. Generate the model.yml file](#23-generate-the-modelyml-file)
  - [2.4. Generate the module code](#24-generate-the-module-code)

## 1. Overview

This builder uses a yang definition to generate a resource module for the Ciena collections.

Generates modules for:

* SAOS 10
* Waveserver 5

## 2. Usage

### 2.1. Download yangs

```bash
# update inventory.yml with the device type you are working on
ansible-playbook yang_get.yml
```

### 2.2. Create the module type directory and files

The playbooks in this project generate modules for Ciena collections using the resource module builder.

Add the module type to the device type directory. Create the input.yml file and merged_example.txt file.

Diagram of Directory Structure

```
models/
|-- saos10/
|   |-- classifiers/
|   |   |-- input.yml
|   |   `-- merged_example.txt
|   |-- fds/
|   |   |-- input.yml
|   |   `-- merged_example.txt
|   `-- fps/
|   |   |-- input.yml
|   |   `-- merged_example.txt
`-- waveserver5/
    |-- aaa/
    |   |-- input.yml
    |   `-- merged_example.txt
    `-- integration/
        |-- input.yml
        `-- merged_example.txt
```

The input.yml file is used to generate the model.yml file. It specifies the namespace, module name, and if any nested suboptions from the yang are required.

```yml
XML_NAMESPACE: "urn:ciena:params:xml:ns:yang:ciena-pn::ciena-mef-classifier"
NETWORK_OS: "saos10"
RESOURCE: "classifiers"
XML_ROOT_KEY: "classifiers"
XML_ITEMS: "classifier"
config_path: "suboptions.classifier"
module: "saos10_classifiers"
short_description: "Manage classifiers on Ciena SAOS 10 devices"
description: "This module provides declarative management of a classifier on Ciena SAOS 10 devices."
author: "Jeff Groom (@jgroom33)"
EXAMPLES:
  - merged_example_01.txt
  - deleted_example_01.txt
```

### 2.3. Generate the model.yml file

This step uses a custom pyang translator to generate the model.yml file. The input.yml and the yang file are used to generate the model.yml file.

```bash
#!/bin/bash
export PYANG_PLUGINPATH#~/src/resource_module_builder/pyang-plugin
# SAOS10
pyang -f ansible -p yangs/saos10 -i models/saos10/classifiers/input.yml yangs/saos10/ciena-mef-classifier.yang > models/saos10/classifiers/model.yml
pyang -f ansible -p yangs/saos10 -i models/saos10/fds/input.yml yangs/saos10/ciena-mef-fd.yang > models/saos10/fds/model.yml
pyang -f ansible -p yangs/saos10 -i models/saos10/fps/input.yml yangs/saos10/ciena-mef-fp.yang > models/saos10/fps/model.yml
```

### 2.4. Generate the module code

This step is roughly the traditional resource module builder way to generate the module code. It uses the model.yml file to generate the module code. However, it uses a newer schema for the model generation.

> **Note:**
> The module generation assumes that the ansible collections are installed in the following directory:
> /home/{{ansible_user_id}}/src/ansible_collections

```bash
# Generate the module code
ansible-playbook generate_saos10.yml
ansible-playbook generate_waveserver5.yml
```
