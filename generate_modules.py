#! /bin/python3
# python3 generate_modules.py --files ciena-flexe.yml ciena-bgp.yml
import os
import yaml
import argparse  # Add argparse for command-line argument parsing


def determine_structure(potential_module):
    if "elements" in potential_module:
        return "single_list"
    elif "suboptions" in potential_module:
        return "list_with_properties"
    elif "type" in potential_module and potential_module["type"] == "dict":
        return "single_dict"
    else:
        return "unknown"


def create_module(
    network_os,
    module_name,
    structure,
    xml_namespace,
    xml_root_key,
    potential_module,  # Add potential_module parameter
    xml_items=None,
    xml_items_key=None,
):
    short_description = potential_module.get("description", "")
    author = "Ciena"  # You can modify this as needed
    config = potential_module.get("suboptions", {})

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
        "DOCUMENTATION": {
            "module": module_name,
            "short_description": short_description,
            "description": short_description,
            "author": author,
            "options": {
                "config": config,
                "state": {
                    "description": ["The state of the configuration"],
                    "required": True,
                    "choices": ["merged", "replaced", "deleted"],
                    "type": "str",
                },
            },
        },
        "requirements": ["ncclient (>=v0.6.4)"],
        "notes": [
            "This module requires the netconf system service be enabled on the remote device being managed.",
            "This module works with connection C(netconf)",
        ],
        "EXAMPLES": ["merged_example_01.txt", "deleted_example_01.txt"],
    }
    if structure == "single_list":
        result["XML_ITEMS"] = xml_items
        result["XML_ITEMS_KEY"] = xml_items_key
    return result


def process_yaml_file(filepath, network_os):
    with open(filepath, "r") as file:
        data = yaml.safe_load(file)
        if "xml_namespace" not in data:
            raise ValueError(f"Skipping {filepath} as it does not contain 'xml_namespace'")
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
                potential_module,  # Pass potential_module to create_module
                xml_items,
                xml_items_key,
            )
            output_dir = os.path.join("models", network_os, xml_root_key)
            os.makedirs(output_dir, exist_ok=True)
            output_filepath = os.path.join(output_dir, "model.yml")
            with open(output_filepath, "w") as output_file:
                yaml.dump(module, output_file, default_flow_style=False)
            print(f"Module written to {output_filepath}")


def main():
    parser = argparse.ArgumentParser(description="Generate modules from YAML files.")
    parser.add_argument(
        "--files",
        nargs="+",
        help="List of YAML files to process",
        required=True
    )
    args = parser.parse_args()

    base_dir = "schemas"
    files_to_process = args.files  # Get the list of files to process from command-line arguments
    for network_os in os.listdir(base_dir):
        network_os_dir = os.path.join(base_dir, network_os)
        if os.path.isdir(network_os_dir):
            for filename in os.listdir(network_os_dir):
                if filename.endswith(".yml") and filename in files_to_process:
                    filepath = os.path.join(network_os_dir, filename)
                    process_yaml_file(filepath, network_os)


if __name__ == "__main__":
    main()
