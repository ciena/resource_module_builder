#! /bin/python3
# python3 generate_modules.py --files ciena-flexe.yml ciena-bgp.yml
import os
import yaml
import argparse
import logging
from collections import OrderedDict


# Custom YAML Dumper for OrderedDict support
class CustomDumper(yaml.SafeDumper):
    pass


def represent_ordered_dict(dumper, data):
    return dumper.represent_dict(data.items())


CustomDumper.add_representer(OrderedDict, represent_ordered_dict)


# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


def determine_structure(potential_module):
    result = "unknown"
    logging.info("Determining structure for module")
    if "elements" in potential_module:
        result = "single_list"
    elif "suboptions" in potential_module:
        suboptions = potential_module["suboptions"]
        if len(suboptions) == 1:
            property_name, property_value = next(iter(suboptions.items()))
            if property_value["type"] == "list":
                result = "single_list"
    elif "type" in potential_module and potential_module["type"] == "dict":
        result = "single_dict"
    else:
        result = "unknown"
    logging.info(f"Determined structure: {result}")
    return result


def create_module(
    network_os,
    module_name,
    structure,
    xml_namespace,
    xml_root_key,
    potential_module,
    xml_items=None,
    xml_items_key=None,
):
    short_description = potential_module.get("description", "")
    author = "Ciena"
    config = potential_module.get("suboptions", {})

    result = OrderedDict(
        [
            ("GENERATOR_VERSION", "2.0"),
            ("NETWORK_OS", network_os),
            ("RESOURCE", module_name),
            ("XML_NAMESPACE", xml_namespace),
            ("XML_ROOT_KEY", xml_root_key),
            (
                "ANSIBLE_METADATA",
                OrderedDict(
                    [
                        ("metadata_version", "2.0"),
                        ("status", ["preview"]),
                        ("supported_by", "network"),
                    ]
                ),
            ),
            ("COPYRIGHT", "Copyright 2025 Ciena"),
            (
                "DOCUMENTATION",
                OrderedDict(
                    [
                        ("module", f"{network_os}_{module_name}"),
                        ("short_description", short_description),
                        ("description", short_description),
                        ("author", author),
                        (
                            "options",
                            OrderedDict(
                                [
                                    ("config", config),
                                    (
                                        "state",
                                        OrderedDict(
                                            [
                                                (
                                                    "description",
                                                    ["The state of the configuration"],
                                                ),
                                                ("required", True),
                                                (
                                                    "choices",
                                                    ["merged", "replaced", "deleted"],
                                                ),
                                                ("type", "str"),
                                            ]
                                        ),
                                    ),
                                ]
                            ),
                        ),
                    ]
                ),
            ),
            ("requirements", ["ncclient (>=v0.6.4)"]),
            (
                "notes",
                [
                    "This module requires the netconf system service be enabled on the remote device being managed.",
                    "This module works with connection C(netconf)",
                ],
            ),
            ("EXAMPLES", ["merged_example_01.txt", "deleted_example_01.txt"]),
        ]
    )
    if structure == "single_list":
        result["XML_ITEMS"] = xml_items
        result["XML_ITEMS_KEY"] = xml_items_key
    return result


def process_yaml_file(filepath, network_os):
    logging.info(f"Processing file: {filepath}")
    with open(filepath, "r") as file:
        data = yaml.safe_load(file)
        if "xml_namespace" not in data:
            raise ValueError(
                f"Skipping {filepath} as it does not contain 'xml_namespace'"
            )
        xml_namespace = data["xml_namespace"]
        for module_name, potential_module in data["potential_modules"].items():
            structure = determine_structure(potential_module)
            xml_root_key = module_name
            xml_items = None
            xml_items_key = None
            if structure == "single_list":
                suboptions = potential_module["suboptions"]
                property_name, property_value = next(iter(suboptions.items()))
                xml_items = property_name
                xml_items_key = property_value["key"]
            module = create_module(
                network_os,
                module_name,
                structure,
                xml_namespace,
                xml_root_key,
                potential_module,
                xml_items,
                xml_items_key,
            )
            output_dir = os.path.join("models", network_os, xml_root_key)
            os.makedirs(output_dir, exist_ok=True)
            output_filepath = os.path.join(output_dir, "model.yml")
            with open(output_filepath, "w") as output_file:
                yaml.dump(
                    module, output_file, Dumper=CustomDumper, default_flow_style=False
                )
            logging.info(f"Module written to {output_filepath}")


def main():
    logging.info("Starting module generation")
    parser = argparse.ArgumentParser(description="Generate modules from YAML files.")
    parser.add_argument(
        "--files", nargs="+", help="List of YAML files to process", required=True
    )
    args = parser.parse_args()

    base_dir = "schemas"
    files_to_process = args.files
    for network_os in os.listdir(base_dir):
        network_os_dir = os.path.join(base_dir, network_os)
        if os.path.isdir(network_os_dir):
            for filename in os.listdir(network_os_dir):
                if filename.endswith(".yml") and filename in files_to_process:
                    filepath = os.path.join(network_os_dir, filename)
                    process_yaml_file(filepath, network_os)
    logging.info("Module generation completed")


if __name__ == "__main__":
    main()
