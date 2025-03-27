#!/bin/python3
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
    level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s"
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

def get_example_value(prop_name, prop_config):
    """Generate an example value based on property type"""
    prop_type = prop_config.get("type")
    choices = prop_config.get("choices")
    logging.debug(f"Getting example value for {prop_name}: type={prop_type}, choices={choices}")

    if prop_type == "str":
        if choices:
            return choices[0]
        return f"sample_{prop_name}"
    elif prop_type == "int":
        return 100
    elif prop_type == "bool":
        return "true"
    elif prop_type == "list":
        suboptions = prop_config.get("suboptions", {})
        if suboptions:
            key_field = prop_config.get("key", list(suboptions.keys())[0])
            example_item = {}
            for sub_name, sub_config in suboptions.items():
                if sub_name == key_field or sub_config.get("required"):
                    example_item[sub_name] = get_example_value(sub_name, sub_config)
            return [example_item]
        return ["sample_item"]
    return f"sample_{prop_name}"

def generate_example_content(module_name, config, network_os, is_list_module=False):
    """Generate content for merged and deleted example files"""
    logging.debug(f"Starting example generation for {module_name}, is_list_module={is_list_module}")
    merged_content = f"# Using merged\n\n- name: Configure {module_name}\n  ciena.{network_os}.{network_os}_{module_name}:\n    config:\n"
    deleted_content = f"# Using deleted\n\n- name: Delete {module_name}\n  ciena.{network_os}.{network_os}_{module_name}:\n    config:\n"

    suboptions = config.get("suboptions", {})
    logging.debug(f"Available suboptions: {list(suboptions.keys())}")

    if is_list_module:
        key_field = config.get("key", "name")
        logging.debug(f"Using key field: {key_field}")

        # Merged example with two entries
        for key_value in ["untagged", "foo-100"]:
            logging.debug(f"Building entry with {key_field}={key_value}")
            merged_content += f"      - {key_field}: {key_value}\n"
            additional_prop_added = False
            for prop_name, prop_config in suboptions.items():
                if prop_name != key_field:  # Explicitly exclude the key field
                    logging.debug(f"Considering additional property: {prop_name}")
                    value = get_example_value(prop_name, prop_config)
                    if isinstance(value, list):
                        merged_content += f"        {prop_name}:\n"
                        for item in value:
                            for k, v in item.items():
                                merged_content += f"          - {k}: {v}\n"
                                logging.debug(f"Added list item {prop_name}.{k}: {v}")
                    else:
                        merged_content += f"        {prop_name}: {value}\n"
                        logging.debug(f"Added property {prop_name}: {value}")
                    additional_prop_added = True
                    break  # Only add one additional property
            if not additional_prop_added:
                logging.debug("No additional properties added for this entry")

        # Deleted example - just needs the key
        deleted_content += f"      - {key_field}: untagged\n"
        logging.debug("Added deleted example with key only")

    else:
        # For dict/properties modules
        logging.debug("Processing as properties module")
        if suboptions:
            prop_added = False
            for prop_name, prop_config in suboptions.items():
                if prop_config.get("required") or not prop_added:
                    logging.debug(f"Adding property: {prop_name}")
                    value = get_example_value(prop_name, prop_config)
                    if isinstance(value, list):
                        merged_content += f"      {prop_name}:\n"
                        deleted_content += f"      {prop_name}:\n"
                        for item in value:
                            for k, v in item.items():
                                merged_content += f"        - {k}: {v}\n"
                                deleted_content += f"        - {k}: {v}\n"
                                logging.debug(f"Added list item {prop_name}.{k}: {v}")
                    else:
                        merged_content += f"      {prop_name}: {value}\n"
                        deleted_content += f"      {prop_name}: {value}\n"
                        logging.debug(f"Added property {prop_name}: {value}")
                    prop_added = True

    merged_content += "    state: merged\n"
    deleted_content += "    state: deleted\n"

    logging.debug(f"Generated merged content:\n{merged_content}")
    logging.debug(f"Generated deleted content:\n{deleted_content}")
    return merged_content, deleted_content

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
            ("key", list_config.get("key", "")),
            ("suboptions", reorder_required_first(list_config.get("suboptions", {})))
        ])
        instance_description = list_config.get("description", "")
        short_description += f"Manage the {resource.replace('-', '_')} {xml_items} configuration of a Ciena {network_os} device"
        description = f"{description}\n {instance_description}"
    else:
        # Properties module
        config = reorder_required_first(config)
        short_description += f"Manage the {resource.replace('-', '_')} configuration of a Ciena {network_os} device"

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
        schema_name = os.path.splitext(os.path.basename(filepath))[0]

        for module_name, potential_module in data["potential_modules"].items():
            if "suboptions" not in potential_module:
                raise ValueError(f"No suboptions found in module {module_name}")
            if potential_module["type"] == "list":
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

                    # Write model.yml
                    output_filepath = os.path.join(output_dir, "model.yml")
                    with open(output_filepath, "w") as output_file:
                        yaml.dump(
                            module, output_file, Dumper=CustomDumper,
                            default_flow_style=False, width=140, allow_unicode=True
                        )
                    logging.info(f"List module written to {output_filepath}")

                    # Generate and write example files
                    merged_content, deleted_content = generate_example_content(
                        module_name, module["DOCUMENTATION"]["options"]["config"],
                        network_os, is_list_module=True
                    )
                    with open(os.path.join(output_dir, "merged_example_01.txt"), "w") as f:
                        f.write(merged_content)
                    with open(os.path.join(output_dir, "deleted_example_01.txt"), "w") as f:
                        f.write(deleted_content)
                    logging.info(f"Example files written to {output_dir}")

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

                # Write model.yml
                output_filepath = os.path.join(output_dir, "model.yml")
                with open(output_filepath, "w") as output_file:
                    yaml.dump(
                        module, output_file, Dumper=CustomDumper,
                        default_flow_style=False, width=140, allow_unicode=True
                    )
                logging.info(f"Properties module written to {output_filepath}")

                # Generate and write example files
                merged_content, deleted_content = generate_example_content(
                    module_name, module["DOCUMENTATION"]["options"]["config"],
                    network_os, is_list_module=False
                )
                with open(os.path.join(output_dir, "merged_example_01.txt"), "w") as f:
                    f.write(merged_content)
                with open(os.path.join(output_dir, "deleted_example_01.txt"), "w") as f:
                    f.write(deleted_content)
                logging.info(f"Example files written to {output_dir}")

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