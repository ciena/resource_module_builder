#! /bin/python3
import os
import yaml
import argparse
import logging
from collections import OrderedDict

class CustomDumper(yaml.SafeDumper):
    pass

def represent_ordered_dict(dumper, data):
    return dumper.represent_dict(data.items())

CustomDumper.add_representer(OrderedDict, represent_ordered_dict)

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)

def reorder_required_first(data):
    if isinstance(data, dict):
        if "suboptions" in data and isinstance(data["suboptions"], dict):
            suboptions = data["suboptions"]
            required_items = OrderedDict(
                (k, v) for k, v in suboptions.items() if v.get("required", False)
            )
            other_items = OrderedDict(
                (k, v) for k, v in suboptions.items() if not v.get("required", False)
            )
            data["suboptions"] = OrderedDict(
                list(required_items.items()) + list(other_items.items())
            )
        return OrderedDict((k, reorder_required_first(v)) for k, v in data.items())
    elif isinstance(data, list):
        return [reorder_required_first(item) for item in data]
    return data

def create_module(
    network_os,
    module_name,
    resource,
    xml_namespace,
    xml_root_key,
    config,
    xml_items=None,
    xml_items_key=None,
    is_properties_module=False,
):
    short_description = config.get("description", "")
    description = config.get("description", "")
    author = "Ciena"
    xml_root_key = xml_root_key.replace("_", "-")

    if xml_items and not is_properties_module:
        # List module
        list_config = config["suboptions"][xml_items]
        config = OrderedDict([
            ("description", list_config.get("description", "")),
            ("type", "list"),
            ("elements", "dict"),
            ("key", list_config.get("key", "")),  # Preserve the key field
            ("suboptions", reorder_required_first(list_config.get("suboptions", {})))
        ])
        instance_description = list_config.get("description", "")
        short_description += f"Manage the {resource.replace('-',"_")} {xml_items} configuration of a Ciena {network_os} device"
        description = f"{description}\n {instance_description}"
    else:
        # Properties module
        config = reorder_required_first(config)
        short_description += f"Manage the {resource.replace('-',"_")} configuration of a Ciena {network_os} device"

    result = OrderedDict(
        [
            ("GENERATOR_VERSION", "2.0"),
            ("NETWORK_OS", network_os),
            ("RESOURCE", resource),
            ("XML_NAMESPACE", xml_namespace),
            ("XML_ROOT_KEY", xml_root_key),
            ("XML_ITEMS", xml_items.replace("_", "-") if xml_items else None),
            ("XML_ITEMS_KEY", xml_items_key.replace("_", "-") if xml_items_key else None),
            ("ANSIBLE_METADATA", OrderedDict([
                ("metadata_version", "2.0"),
                ("status", ["preview"]),
                ("supported_by", "network"),
            ])),
            ("COPYRIGHT", "Copyright 2025 Ciena"),
            ("DOCUMENTATION", OrderedDict([
                ("module", f"{network_os}_{module_name}"),
                ("short_description", short_description),
                ("description", description),
                ("author", author),
                ("options", OrderedDict([
                    ("config", config),
                    ("state", OrderedDict([
                        ("description", ["The state of the configuration"]),
                        ("type", "str"),
                        ("choices", ["merged", "deleted"]),
                        ("default", "merged"),
                    ])),
                ])),
            ])),
            ("EXAMPLES", ["merged_example_01.txt", "deleted_example_01.txt"]),
            ("notes", [
                "This module requires the netconf system service be enabled on the remote device being managed.",
                "This module works with connection C(netconf)",
            ]),
            ("requirements", ["ncclient (>=v0.6.4)"]),
        ]
    )
    return result

def process_yaml_file(filepath, network_os):
    logging.info(f"Processing file: {filepath}")
    with open(filepath, "r") as file:
        data = yaml.safe_load(file)
        if "xml_namespace" not in data:
            raise ValueError(f"Skipping {filepath} as it does not contain 'xml_namespace'")

        xml_namespace = data["xml_namespace"]
        # Extract schema name from the filename (without extension)
        schema_name = os.path.splitext(os.path.basename(filepath))[0]

        for module_name, potential_module in data["potential_modules"].items():
            if "suboptions" not in potential_module:
                raise ValueError(f"No suboptions found in module {module_name}")
            if potential_module["type"] == "list":
                logging.info(f"Creating list module for {module_name}")
                raise ValueError(f"Not implemented. Top level list: {module_name}")
            else:
                suboptions = potential_module["suboptions"]
                xml_root_key = module_name

            # Process each top-level list
            for property_name, property_value in suboptions.items():
                if property_value.get("type") == "list":
                    xml_items = property_name
                    xml_items_key = property_value.get("key")
                    resource = module_name.replace("_", "-")

                    module = create_module(
                        network_os, module_name, resource, xml_namespace, xml_root_key,
                        potential_module, xml_items, xml_items_key
                    )

                    output_dir = os.path.join("models", network_os, schema_name, xml_root_key)
                    os.makedirs(output_dir, exist_ok=True)
                    output_filepath = os.path.join(output_dir, "model.yml")
                    with open(output_filepath, "w") as output_file:
                        yaml.dump(
                            module, output_file, Dumper=CustomDumper,
                            default_flow_style=False, width=140, allow_unicode=True
                        )
                    logging.info(f"List module written to {output_filepath}")

            # Create properties module if there are non-list properties
            non_list_props = OrderedDict(
                (k, v) for k, v in suboptions.items() if v.get("type") != "list"
            )
            if non_list_props:
                properties_config = OrderedDict([
                    ("description", potential_module.get("description", "")),
                    ("type", "dict"),
                    ("suboptions", non_list_props)
                ])
                # Check if there are only non-list items
                if len(non_list_props) == len(suboptions):
                    logging.info(f"Creating properties module for {module_name}")
                    resource = module_name.replace("_", "-")
                    properties_module_name = module_name
                else:
                    logging.info(f"Creating properties module as __properties for {module_name}")
                    resource = module_name.replace("_", "-")
                    module_name = f"{module_name}__properties"
                    properties_module_name = module_name
                module = create_module(
                    network_os, module_name, resource, xml_namespace, xml_root_key,
                    properties_config, is_properties_module=True
                )

                output_dir = os.path.join("models", network_os, schema_name, properties_module_name)
                os.makedirs(output_dir, exist_ok=True)
                output_filepath = os.path.join(output_dir, "model.yml")
                with open(output_filepath, "w") as output_file:
                    yaml.dump(
                        module, output_file, Dumper=CustomDumper,
                        default_flow_style=False, width=140, allow_unicode=True
                    )
                logging.info(f"Properties module written to {output_filepath}")

def main():
    parser = argparse.ArgumentParser(description="Generate modules from YAML files.")
    parser.add_argument("--files", nargs="+", help="List of YAML files to process")
    parser.add_argument("--all", action="store_true", help="Process all YAML files in the directory")
    parser.add_argument("--network_os", help="Specify the network OS to process", required=True)
    args = parser.parse_args()

    base_dir = "schemas"
    files_to_process = args.files if args.files else []
    network_os = args.network_os

    if args.all:
        network_os_dir = os.path.join(base_dir, network_os)
        if os.path.isdir(network_os_dir):
            files_to_process = [f for f in os.listdir(network_os_dir) if f.endswith(".yml")]

    for filename in files_to_process:
        filepath = os.path.join(base_dir, network_os, filename)
        if os.path.isfile(filepath):
            process_yaml_file(filepath, network_os)
    logging.info("Module generation completed")

if __name__ == "__main__":
    main()
