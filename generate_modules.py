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
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


def reorder_required_first(data):
    """Reorders suboptions to place required ones first."""
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


def determine_structure(potential_module):
    result = "unknown"
    list_count = 0
    if "suboptions" not in potential_module:
        raise ValueError("No suboptions found in potential module")
    suboptions = potential_module["suboptions"]
    if len(suboptions) == 1:
        property_name, property_value = next(iter(suboptions.items()))
        if property_value["type"] == "list":
            result = "single_list"
        else:
            result = "multiple_properties"
    else:
        for property_name, property_value in suboptions.items():
            if property_value["type"] == "list":
                list_count += 1
        if list_count == 1:
            result = "single_list_plus_properties"
        elif list_count > 1:
            if len(suboptions) == list_count:
                result = "multiple_lists"
            else:
                result = "multiple_lists_plus_properties"
        else:
            result = "multiple_properties"

    logging.info(f"Determined structure: {result}")
    if result == "unknown":
        logging.error(f"Determined structure: {result}")
        exit(1)
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
    is_properties_module=False,
):
    short_description = potential_module.get("description", "")
    description = potential_module.get("description", "")
    author = "Ciena"
    resource = module_name.replace("_", "-")
    xml_root_key = xml_root_key.replace("_", "-")
    config = potential_module

    if structure == "single_list" and xml_items:
        config = potential_module.get("suboptions", {})
        instance_description = config[xml_items].get("description", "")
        short_description += f"Manage the {module_name} {xml_items} configuration of a Ciena {network_os} device"
        config = config[xml_items]
        description = f"{description}\n {instance_description}"
    elif is_properties_module:
        short_description += f"Manage the {module_name} properties configuration of a Ciena {network_os} device"
        if "suboptions" in config:
            keys_to_delete = [key for key, value in config["suboptions"].items() if value["type"] == "list"]
            for key in keys_to_delete:
                del config["suboptions"][key]
        resource = xml_root_key
        xml_items = None

    config = reorder_required_first(config)

    result = OrderedDict(
        [
            ("GENERATOR_VERSION", "2.0"),
            ("NETWORK_OS", network_os),
            ("RESOURCE", resource),
            ("XML_NAMESPACE", xml_namespace),
            ("XML_ROOT_KEY", xml_root_key),
            ("XML_ITEMS", xml_items.replace("_", "-") if xml_items else None),
            ("XML_ITEMS_KEY", xml_items_key.replace("_", "-") if xml_items_key else None),
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
                        ("description", description),
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
                                                ("type", "str"),
                                                (
                                                    "choices",
                                                    ["merged", "deleted"],
                                                ),
                                                ("default", "merged"),
                                            ]
                                        ),
                                    ),
                                ]
                            ),
                        ),
                    ]
                ),
            ),
            ("EXAMPLES", ["merged_example_01.txt", "deleted_example_01.txt"]),
            (
                "notes",
                [
                    "This module requires the netconf system service be enabled on the remote device being managed.",
                    "This module works with connection C(netconf)",
                ],
            ),
            ("requirements", ["ncclient (>=v0.6.4)"]),
        ]
    )

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
        schema_name = os.path.splitext(os.path.basename(filepath))[0]
        for module_name, potential_module in data["potential_modules"].items():
            logging.info(f"Determining structure for module {filepath} - {module_name}")
            structure = determine_structure(potential_module)
            xml_root_key = module_name
            xml_items = None
            xml_items_key = None
            if structure == "single_list":
                suboptions = potential_module["suboptions"]
                for property_name, property_value in suboptions.items():
                    if property_value["type"] == "list":
                        xml_items = property_name
                        xml_items_key = property_value["key"]
                        break
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
                output_dir = os.path.join("models", network_os, schema_name, xml_root_key)
                os.makedirs(output_dir, exist_ok=True)
                output_filepath = os.path.join(output_dir, "model.yml")
                with open(output_filepath, "w") as output_file:
                    yaml.dump(
                        module, output_file, Dumper=CustomDumper, default_flow_style=False, width=140, allow_unicode=True
                    )
                logging.info(f"Module written to {output_filepath}")
            elif structure == "multiple_lists":
                suboptions = potential_module["suboptions"]
                for property_name, property_value in suboptions.items():
                    if property_value["type"] == "list":
                        xml_items = property_name
                        xml_items_key = property_value["key"]
                    module = create_module(
                        network_os,
                        module_name,
                        "single_list",
                        xml_namespace,
                        xml_root_key,
                        potential_module,
                        xml_items,
                        xml_items_key,
                    )
                    output_dir = os.path.join("models", network_os, schema_name, xml_items)
                    os.makedirs(output_dir, exist_ok=True)
                    output_filepath = os.path.join(output_dir, "model.yml")
                    with open(output_filepath, "w") as output_file:
                        yaml.dump(
                            module, output_file, Dumper=CustomDumper, default_flow_style=False, width=140, allow_unicode=True
                        )
                    logging.info(f"Module written to {output_filepath}")
            elif structure == "multiple_lists_plus_properties":
                suboptions = potential_module["suboptions"]
                for property_name, property_value in suboptions.items():
                    if property_value["type"] == "list":
                        xml_items = property_name
                        xml_items_key = property_value["key"]
                    module = create_module(
                        network_os,
                        module_name,
                        "single_list",
                        xml_namespace,
                        xml_root_key,
                        potential_module,
                        xml_items,
                        xml_items_key,
                    )
                    output_dir = os.path.join("models", network_os, schema_name, xml_items)
                    os.makedirs(output_dir, exist_ok=True)
                    output_filepath = os.path.join(output_dir, "model.yml")
                    with open(output_filepath, "w") as output_file:
                        yaml.dump(
                            module, output_file, Dumper=CustomDumper, default_flow_style=False, width=140, allow_unicode=True
                        )
                    logging.info(f"Module written to {output_filepath}")
                # Create properties module
                properties_module_name = f"{module_name}__properties"
                properties_module = create_module(
                    network_os,
                    properties_module_name,
                    "multiple_properties",
                    xml_namespace,
                    xml_root_key,
                    potential_module,
                    xml_items=xml_items,
                    is_properties_module=True,
                )
                properties_output_dir = os.path.join("models", network_os, schema_name, properties_module_name)
                os.makedirs(properties_output_dir, exist_ok=True)
                properties_output_filepath = os.path.join(properties_output_dir, "model.yml")
                with open(properties_output_filepath, "w") as output_file:
                    yaml.dump(
                        properties_module, output_file, Dumper=CustomDumper, default_flow_style=False, width=140, allow_unicode=True
                    )
                logging.info(f"Properties module written to {properties_output_filepath}")
            elif structure == "multiple_properties":
                module = create_module(
                    network_os,
                    module_name,
                    structure,
                    xml_namespace,
                    xml_root_key,
                    potential_module,
                )
                output_dir = os.path.join("models", network_os, schema_name, xml_root_key)
                os.makedirs(output_dir, exist_ok=True)
                output_filepath = os.path.join(output_dir, "model.yml")
                with open(output_filepath, "w") as output_file:
                    yaml.dump(
                        module, output_file, Dumper=CustomDumper, default_flow_style=False, width=140, allow_unicode=True
                    )
                logging.info(f"Module written to {output_filepath}")
            elif structure == "single_list_plus_properties":
                suboptions = potential_module["suboptions"]
                for property_name, property_value in suboptions.items():
                    if property_value["type"] == "list":
                        xml_items = property_name
                        xml_items_key = property_value["key"]
                        break
                # Create single_list module
                single_list_module = create_module(
                    network_os,
                    module_name,
                    "single_list",
                    xml_namespace,
                    xml_root_key,
                    potential_module,
                    xml_items,
                    xml_items_key,
                )
                output_dir = os.path.join("models", network_os, schema_name, xml_root_key)
                os.makedirs(output_dir, exist_ok=True)
                output_filepath = os.path.join(output_dir, "model.yml")
                with open(output_filepath, "w") as output_file:
                    yaml.dump(
                        single_list_module, output_file, Dumper=CustomDumper, default_flow_style=False, width=140, allow_unicode=True
                    )
                logging.info(f"Single list module written to {output_filepath}")
                # Create properties module
                properties_module_name = f"{module_name}__properties"
                properties_module = create_module(
                    network_os,
                    properties_module_name,
                    "multiple_properties",
                    xml_namespace,
                    xml_root_key,
                    potential_module,
                    xml_items=xml_items,
                    is_properties_module=True,
                )
                properties_output_dir = os.path.join("models", network_os, schema_name, properties_module_name)
                os.makedirs(properties_output_dir, exist_ok=True)
                properties_output_filepath = os.path.join(properties_output_dir, "model.yml")
                with open(properties_output_filepath, "w") as output_file:
                    yaml.dump(
                        properties_module, output_file, Dumper=CustomDumper, default_flow_style=False, width=140, allow_unicode=True
                    )
                logging.info(f"Properties module written to {properties_output_filepath}")


def main():
    logging.info("Starting module generation")
    parser = argparse.ArgumentParser(description="Generate modules from YAML files.")
    parser.add_argument(
        "--files", nargs="+", help="List of YAML files to process"
    )
    parser.add_argument(
        "--all", action="store_true", help="Process all YAML files in the directory"
    )
    parser.add_argument(
        "--network_os", help="Specify the network OS to process", required=True
    )
    args = parser.parse_args()

    base_dir = "schemas"
    files_to_process = args.files if args.files else []
    network_os = args.network_os

    if args.all:
        network_os_dir = os.path.join(base_dir, network_os)
        if os.path.isdir(network_os_dir):
            for filename in os.listdir(network_os_dir):
                if filename.endswith(".yml"):
                    files_to_process.append(filename)

    for filename in files_to_process:
        filepath = os.path.join(base_dir, network_os, filename)
        if os.path.isfile(filepath):
            process_yaml_file(filepath, network_os)
    logging.info("Module generation completed")


if __name__ == "__main__":
    main()
