#! /bin/python3
import os
import yaml


def determine_structure(potential_module):
    if "elements" in potential_module:
        return "single_list"
    elif "suboptions" in potential_module:
        return "list_with_properties"
    elif "type" in potential_module and potential_module["type"] == "dict":
        return "single_dict"
    else:
        return "unknown"


def create_module(network_os, module_name, structure, xml_namespace, xml_root_key, xml_items=None, xml_items_key=None):
    result = {
        "GENERATOR_VERSION": "2.0",
        "ANSIBLE_METADATA": {
            "metadata_version": "2.0",
            "status": ["preview"],
            "supported_by": "network",
        },
        "NETWORK_OS": network_os,
        "RESOURCE": module_name,
        "COPYRIGHT": "Copyright 2025 Ciena",
        "XML_NAMESPACE": xml_namespace,
        "XML_ROOT_KEY": xml_root_key,
        "DOCUMENTATION": {},
        "requirements": ["ncclient (>=v0.6.4)"],
        "notes": [
            "This module requires the netconf system service be enabled on the remote device being managed.",
            "This module works with connection C(netconf)",
        ],
        "EXAMPLES": ["merged_example_01.txt", "deleted_example_01.txt"],
    }
    if structure == 'single_list':
        result["XML_ITEMS"] = xml_items
        result["XML_ITEMS_KEY"] = xml_items_key
    return result


def process_yaml_file(filepath, network_os):
    with open(filepath, "r") as file:
        data = yaml.safe_load(file)
        xml_namespace = data["xml_namespace"]
        for module_name, potential_module in data["potential_modules"].items():
            structure = determine_structure(potential_module)
            xml_root_key = module_name
            xml_items = None
            xml_items_key = None
            if structure == "single_list":
                xml_items = list(potential_module["suboptions"].keys())[0]
                xml_items_key = potential_module["suboptions"][xml_items]["key"]
            module = create_module(
                network_os,
                module_name,
                structure,
                xml_namespace,
                xml_root_key,
                xml_items,
                xml_items_key,
            )
            print(module)


def main():
    base_dir = "schemas"
    for network_os in os.listdir(base_dir):
        network_os_dir = os.path.join(base_dir, network_os)
        if os.path.isdir(network_os_dir):
            for filename in os.listdir(network_os_dir):
                if filename.endswith(".yml"):
                    filepath = os.path.join(network_os_dir, filename)
                    process_yaml_file(filepath, network_os)


if __name__ == "__main__":
    main()
