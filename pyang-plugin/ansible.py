"""Ansible output plugin"""

# pylint: disable=C0111

from __future__ import print_function

import re
import yaml
import optparse
import logging
import sys
from collections import OrderedDict

from pyang import plugin
from pyang import statements
from pyang import types
from pyang import error

# Set recursion limit - increased for safety, but depth checks are better
sys.setrecursionlimit(3000)


# Custom YAML Dumper for OrderedDict support
class CustomDumper(yaml.SafeDumper):
    pass


def represent_ordered_dict(dumper, data):
    return dumper.represent_dict(data.items())


CustomDumper.add_representer(OrderedDict, represent_ordered_dict)


def load_mappings(file_path):
    """Loads YAML mappings from a file."""
    try:
        with open(file_path, "r") as file:
            return yaml.safe_load(file)
    except FileNotFoundError:
        logging.error(f"Mapping file not found: {file_path}")
        return {}  # Or raise, depending on desired behavior
    except yaml.YAMLError as e:
        logging.error(f"Error parsing YAML file {file_path}: {e}")
        return {}  # Or raise


def pyang_plugin_init():
    plugin.register_plugin(AnsiblePlugin())


def order_dict(obj, priority_keys):
    """Orders dictionary keys with specified keys first, followed by others alphabetically."""
    if isinstance(obj, dict):
        ordered = OrderedDict((k, obj[k]) for k in priority_keys if k in obj)
        for key in sorted(obj.keys()):
            if key not in ordered:
                ordered[key] = obj[key]
        return OrderedDict(
            (k, order_dict(v, priority_keys)) for k, v in ordered.items()
        )
    elif isinstance(obj, list):
        return [order_dict(element, priority_keys) for element in obj]
    return obj


def get_nested_schema(schema, sub_path):
    """Retrieves a nested schema element by its path."""
    keys = sub_path.split(".")
    for key in keys:
        schema = schema.get(key, {})
        if not schema:
            return {}  # Or None, depending on the use case
    return schema


def prune_statements(stmt):
    """Prunes notification and rpc statements, as well as containers that are config false."""
    pruned_children = []
    for child in stmt.i_children:
        if child.keyword in ("notification", "rpc"):
            logging.debug(f"Pruning {child.keyword} statement: {child.arg}")
            continue
        if child.keyword == "container" and not child.i_config:
            logging.debug(f"Pruning config false container: {child.arg}")
            continue
        pruned_children.append(child)
    stmt.i_children = pruned_children
    return stmt


class AnsiblePlugin(plugin.PyangPlugin):
    def add_output_format(self, fmts):
        fmts["ansible"] = self

    def add_opts(self, optparser):
        optlist = [
            optparse.make_option(
                "--ansible-debug",
                dest="ansible_debug",
                action="store_true",
                help="Enable debugging output for the Ansible plugin.",
            ),
            optparse.make_option(
                "-n",
                "--network-os",
                dest="network_os",
                default="saos10",
                help="Specify the network operating system (default: saos10).",
            ),
        ]

        group = optparser.add_option_group("Ansible-specific options")
        group.add_options(optlist)

    def setup_ctx(self, ctx):
        ctx.opts.stmts = None  # Not used in this plugin

    def setup_fmt(self, ctx):
        ctx.implicit_errors = False

    def emit(self, ctx, modules, fd):
        if not modules:
            logging.error("No modules provided to emit.")
            return
        if len(modules) > 1:
            logging.error("Multiple modules provided. Using the first one.")
            exit(1)

        root_stmt = modules[0]

        # Prune unwanted statements
        root_stmt = prune_statements(root_stmt)

        # Configure logging based on debug option
        if ctx.opts.ansible_debug:
            logging.basicConfig(level=logging.DEBUG)
        else:
            logging.basicConfig(level=logging.INFO)  # Or INFO, as appropriate

        network_os = ctx.opts.network_os
        logging.debug(f"network_os: {network_os}")

        # Extract namespace; raise a more specific exception
        namespace_stmt = root_stmt.search_one("namespace")
        if not namespace_stmt:
            raise error.EmitError(f"YANG module must contain a namespace statement: {root_stmt.arg}")
        xml_namespace = namespace_stmt.arg

        logging.info(f"Producing schema for namespace: {xml_namespace}")
        try:
            schema = produce_schema(root_stmt)
            logging.info(f"Converting schema to Ansible format: {xml_namespace}")
            converted_schema = convert_schema_to_ansible(
                schema, xml_namespace, root_stmt, network_os
            )
        except Exception as e:
            logging.error(
                f"Error during schema processing: {e}", exc_info=ctx.opts.ansible_debug
            )  # Show stack trace only in debug mode
            return  # Stop processing if schema generation/conversion failed.

        priority_keys = [
            "GENERATOR_VERSION",
            "NETWORK_OS",
            "RESOURCE",
            "XML_NAMESPACE",
            "XML_ROOT_KEY",
            "XML_ITEMS",
            "XML_ITEMS_KEY",
            "module",
            "short_description",
            "description",
            "type",
            "required",
            "elements",
            "choices",
            "suboptions",
        ]
        ordered_data = order_dict(converted_schema, priority_keys)
        final_data = reorder_required_first(ordered_data)

        try:
            # Use safe dumping to prevent arbitrary code execution
            yaml_data = yaml.dump(
                final_data,
                Dumper=CustomDumper,
                default_flow_style=False,
                width=140,
                indent=2,
                allow_unicode=True,
                sort_keys=False,  # Preserve order from OrderedDict
            )
            fd.write(yaml_data)
        except yaml.YAMLError as e:
            logging.error(f"Error writing YAML output: {e}")


def preprocess_string(s):
    """Cleans up description strings."""
    # Replace multiple spaces with single space and colons with semicolons.
    return re.sub(r"\s+", " ", s).replace(":", ";")


def find_stmt_by_path(module, path):
    """Finds a statement within the module by its path."""
    logging.debug(f"Finding statement by path: {path} in module {module.arg}")

    if not path:
        return None

    spath = path.split("/")
    if spath[0] == "":
        spath = spath[1:]  # Handle absolute paths

    children = [
        child
        for child in module.i_children
        if child.keyword in statements.data_definition_keywords
    ]

    current_node = None
    for i, segment in enumerate(spath):
        match = [child for child in children if child.arg == segment]
        if match:
            current_node = match[0]
            if i < len(spath) - 1:
                children = [
                    c
                    for c in current_node.i_children
                    if c.keyword in statements.data_definition_keywords
                ]
        else:
            logging.warning(f"Path segment not found: {segment} in path {path}")
            return None

    logging.debug(f"Found statement: {current_node.keyword} {current_node.arg}")
    return current_node


def produce_schema(root_stmt):
    """Produces the intermediate schema representation from the YANG module."""
    logging.debug(f"Producing schema for: {root_stmt.keyword} {root_stmt.arg}")
    result = {}

    for child in root_stmt.i_children:
        logging.debug(f"Processing child: {child.keyword} {child.arg}")
        if child.keyword in statements.data_definition_keywords:
            if child.keyword in producers:
                try:
                    result.update(producers[child.keyword](child))
                except Exception as e:
                    logging.error(
                        f"Error processing child {child.keyword} {child.arg}: {e}",
                        exc_info=True,
                    )
            else:
                logging.warning(f"Unsupported keyword: {child.keyword} {child.arg}")
        elif child.keyword in ("rpc", "notification"):
            logging.debug(
                f"Skipping non-data definition keyword: {child.keyword} {child.arg}"
            )
        else:
            logging.warning(f"Unexpected keyword: {child.keyword} {child.arg}")
    return result


def convert_schema_to_ansible(schema, xml_namespace, root_stmt, network_os):
    """Converts the schema to Ansible module documentation format."""

    if not schema:
        raise error.EmitError(f"Schema is empty: {xml_namespace}")

    if len(schema) > 1:
        raise error.EmitError(
            f"Multiple top-level keys found in schema. Expected only one: {xml_namespace}"
        )

    config = next(iter(schema.values()))

    resource = None
    xml_root_key = None
    xml_items = None
    xml_items_key = None
    module_name = None
    description = None
    short_description = None
    author = "Ciena"

    for child in root_stmt.i_children:
        if child.keyword == "module":
            module_name = child.arg
        elif child.keyword == "container":
            if not child.i_config:
                logging.debug(f"Skipping config false container: {child.arg}")
                continue

            resource = child.arg
            short_description = f"Manage {resource} on Ciena {network_os} devices"
            xml_root_key = child.arg
            module_name = f"{network_os}_{resource.replace('-', '_')}"

            for sub_child in child.i_children:
                if sub_child.keyword == "list":
                    xml_items = sub_child.arg
                    key_stmt = sub_child.search_one("key")
                    if key_stmt:
                        xml_items_key = key_stmt.arg
                    else:
                        xml_items_key = None

                    config = get_nested_schema(config, f"suboptions.{xml_items}")
                    break

            description_stmt = child.search_one("description")
            if description_stmt:
                description = preprocess_string(description_stmt.arg)

    result = {
        "GENERATOR_VERSION": "2.0",
        "ANSIBLE_METADATA": {
            "metadata_version": "2.0",
            "status": ["preview"],
            "supported_by": "network",
        },
        "NETWORK_OS": network_os,
        "RESOURCE": resource,
        "COPYRIGHT": "Copyright 2025 Ciena",
        "XML_NAMESPACE": xml_namespace,
        "XML_ROOT_KEY": xml_root_key,
        "XML_ITEMS": xml_items,
        "XML_ITEMS_KEY": xml_items_key,
        "DOCUMENTATION": {},
        "requirements": ["ncclient (>=v0.6.4)"],
        "notes": [
            "This module requires the netconf system service be enabled on the remote device being managed.",
            "This module works with connection C(netconf)",
        ],
        "EXAMPLES": ["merged_example_01.txt", "deleted_example_01.txt"],  # Placeholder
    }
    result["DOCUMENTATION"]["module"] = module_name
    result["DOCUMENTATION"]["short_description"] = short_description
    result["DOCUMENTATION"]["description"] = description
    result["DOCUMENTATION"]["author"] = author
    result["DOCUMENTATION"]["options"] = dict(config=config)
    result["DOCUMENTATION"]["options"]["state"] = {
        "choices": ["merged", "deleted"],
        "default": "merged",
        "description": "The state of the configuration after module completion.",
        "type": "str",
    }
    return result


def produce_type(type_stmt):
    """Produces the Ansible type information for a given YANG type."""
    logging.debug(f"Producing type for: {type_stmt.keyword} {type_stmt.arg}")
    type_id = type_stmt.arg

    while hasattr(type_stmt, "i_typedef") and type_stmt.i_typedef is not None:
        logging.debug(
            f"Following typedef chain for: {type_stmt.arg} (typedef: {type_stmt.i_typedef.arg})"
        )
        type_stmt = type_stmt.i_typedef.search_one("type")
        if not type_stmt:
            logging.error(f"Typedef {type_stmt.i_typedef.arg} does not define a type")
            return {"type": "str", "description": "Error: Invalid typedef"}
        type_id = type_stmt.arg

    if types.is_base_type(type_id):
        if type_id in _numeric_type_trans_tbl:
            type_info = numeric_type_trans(type_id)
        elif type_id in _other_type_trans_tbl:
            type_info = _other_type_trans_tbl[type_id](type_stmt)
        else:
            logging.warning(f"Missing mapping for base type: {type_id}")
            type_info = {
                "type": "str",
                "description": f"Missing mapping for type: {type_id}",
            }
    elif type_id in _other_type_trans_tbl:
        type_info = _other_type_trans_tbl[type_id](type_stmt)
    else:
        logging.warning(f"Missing mapping for type: {type_id}")
        type_info = {
            "type": "str",
            "description": f"Missing mapping for type: {type_id}",
        }

    return type_info


def produce_leaf(stmt):
    """Produces the Ansible option for a YANG leaf."""
    logging.debug(f"Producing leaf: {stmt.arg}")
    arg = qualify_name(stmt)

    if not hasattr(stmt, 'i_config') or not stmt.i_config:
        logging.debug(f"Skipping non-configurable leaf: {arg}")
        return {}

    type_stmt = stmt.search_one("type")
    if not type_stmt:
        logging.error(f"Leaf {stmt.arg} has no type defined.")
        return {arg: {"type": "str", "description": "Error: Missing type definition"}}
    type_info = produce_type(type_stmt)
    if not type_info:
        logging.error(f"Failed to produce type info for {stmt.arg}")
        return {arg: {"type": "str", "description": "Error: Could not determine type"}}

    mandatory = stmt.search_one("mandatory")
    is_mandatory = mandatory is not None and mandatory.arg == "true"

    is_key = (
        stmt.parent.keyword == "list"
        and stmt.arg in stmt.parent.search_one("key").arg.split()
    )

    required = is_mandatory or is_key

    description_stmt = stmt.search_one("description")
    description_str = (
        preprocess_string(description_stmt.arg)
        if description_stmt
        else "No description available"
    )

    if is_key:
        list_parent = stmt.parent.arg
        description_str += f" (Key for list: {list_parent})"

    result = {arg: {**type_info, "description": description_str, "required": required}}
    return result


def produce_list(stmt):
    """Produces the Ansible option for a YANG list."""
    logging.debug(f"Producing list: {stmt.arg}")
    arg = qualify_name(stmt)

    if not hasattr(stmt, 'i_config') or not stmt.i_config:
        logging.debug(f"Skipping non-configurable list: {arg}")
        return {}

    suboptions_dict = {}
    for child in stmt.i_children:
        if child.keyword in producers:
            try:
                child_data = producers[child.keyword](child)
                suboptions_dict.update(child_data)
            except Exception as e:
                logging.error(
                    f"Error processing child {child.keyword} {child.arg} in list {stmt.arg}: {e}",
                    exc_info=True,
                )
        else:
            logging.warning(f"Unsupported keyword in list: {child.keyword} {child.arg}")

    description_stmt = stmt.search_one("description")
    description_str = (
        preprocess_string(description_stmt.arg)
        if description_stmt
        else "No description available"
    )

    result = {
        arg: {
            "type": "list",
            "elements": "dict",
            "description": description_str,
            "suboptions": suboptions_dict,
        }
    }
    logging.debug(f"Result for list {stmt.arg}: {result}")
    return result


def produce_leaf_list(stmt):
    """Produces the Ansible option for a YANG leaf-list."""
    logging.debug(f"Producing leaf-list: {stmt.arg}")
    arg = qualify_name(stmt)

    if not stmt.i_config:
        logging.debug(f"Skipping non-configurable leaf-list: {arg}")
        return {}

    type_stmt = stmt.search_one("type")
    if not type_stmt:
        logging.error(f"Leaf-list {stmt.arg} has no type defined")
        return {arg: {"type": "str", "description": "Error, missing type definition."}}

    type_info = produce_type(type_stmt)
    if not type_info:
        logging.error(f"Failed to produce type info for {stmt.arg}")
        return {arg: {"type": "str", "description": "Error: Could not determine type"}}

    description_stmt = stmt.search_one("description")
    description_str = (
        preprocess_string(description_stmt.arg)
        if description_stmt
        else "No description available"
    )

    result = {
        arg: {
            "type": "list",
            "elements": type_info["type"],
            "description": description_str,
        }
    }

    if "choices" in type_info:
        result[arg]["choices"] = type_info["choices"]

    logging.debug(f"Result for leaf-list {stmt.arg}: {result}")
    return result


def produce_container(stmt):
    """Produces the Ansible option for a YANG container."""
    logging.debug(f"Producing container: {stmt.arg}")
    arg = qualify_name(stmt)

    if not hasattr(stmt, 'i_config') or not stmt.i_config:
        logging.debug(f"Skipping non-configurable container: {arg}")
        return {}

    suboptions_dict = {}
    for child in stmt.i_children:
        if child.keyword in producers:
            try:
                child_data = producers[child.keyword](child)
                suboptions_dict.update(child_data)
            except Exception as e:
                logging.error(
                    f"Error processing child {child.keyword} {child.arg} in container {stmt.arg}: {e}",
                    exc_info=True,
                )
        else:
            logging.warning(
                f"Unsupported keyword in container: {child.keyword} {child.arg}"
            )

    description_stmt = stmt.search_one("description")
    description_str = (
        preprocess_string(description_stmt.arg)
        if description_stmt
        else "No description available"
    )

    result = {
        arg: {
            "type": "dict",
            "description": description_str,
            "suboptions": suboptions_dict,
        }
    }
    logging.debug(f"Result for container {stmt.arg}: {result}")
    return result


def produce_choice(stmt):
    """Produces the Ansible option for a YANG choice."""
    logging.debug(f"Producing choice: {stmt.arg}")
    result = {}

    for case in stmt.search("case"):
        for child in case.i_children:
            if child.keyword in producers:
                try:
                    result.update(producers[child.keyword](child))
                except Exception as e:
                    logging.error(
                        f"Error processing child {child.keyword} {child.arg} in choice case {case.arg}: {e}",
                        exc_info=True,
                    )
            else:
                logging.warning(
                    f"Unsupported keyword in choice case: {child.keyword} {child.arg}"
                )

    for child in stmt.substmts:
        if child.keyword in ("container", "leaf", "list", "leaf-list"):
            if child.keyword in producers:
                try:
                    result.update(producers[child.keyword](child))
                except Exception as e:
                    logging.error(
                        f"Error processing shorthand child {child.keyword} {child.arg} in choice {stmt.arg}: {e}",
                        exc_info=True,
                    )
            else:
                logging.warning(
                    f"Unsupported keyword in shorthand choice: {child.keyword} {child.arg}"
                )

    logging.debug(f"Result for choice {stmt.arg}: {result}")
    return result


# Mapping of YANG keywords to producer functions
producers = {
    "container": produce_container,
    "list": produce_list,
    "leaf-list": produce_leaf_list,
    "leaf": produce_leaf,
    "choice": produce_choice,
}

# Mapping of numeric YANG types to Ansible types
_numeric_type_trans_tbl = {
    "int8": ("int", None),
    "int16": ("int", None),
    "int32": ("int", "int32"),
    "int64": ("int", "int64"),
    "uint8": ("int", None),
    "uint16": ("int", None),
    "uint32": ("int", "uint32"),
    "uint64": ("int", "uint64"),
    "decimal64": ("float", "float"),
}


def numeric_type_trans(type_id):
    """Translates numeric YANG types to Ansible types."""
    trans_type = _numeric_type_trans_tbl[type_id][0]
    return {"type": trans_type}


def string_trans(stmt):
    """Translates the YANG string type to Ansible."""
    logging.debug(f"Translating string type: {stmt.arg}")
    return {"type": "str"}


def enumeration_trans(stmt):
    """Translates the YANG enumeration type to Ansible."""
    logging.debug(f"Translating enumeration type: {stmt.arg}")
    choices = [enum.arg for enum in stmt.search("enum")]
    return {"type": "str", "choices": choices}


def bits_trans(stmt):
    """Translates the YANG bits type to Ansible."""
    logging.debug(f"Translating bits type: {stmt.arg}")
    choices = [bit.arg for bit in stmt.search("bit")]
    return {"type": "list", "elements": "str", "choices": choices}


def boolean_trans(stmt):
    """Translates the YANG boolean type to Ansible."""
    logging.debug(f"Translating boolean type: {stmt.arg}")
    return {"type": "bool"}


def empty_trans(stmt):
    """Translates the YANG empty type to Ansible."""
    logging.debug(f"Translating empty type: {stmt.arg}")
    return {"type": "list", "elements": "str", "choices": ["null"]}


def union_trans(stmt):
    """Translates the YANG union type to Ansible."""
    logging.debug(f"Translating union type: {stmt.arg}")
    return {"type": "str"}


def instance_identifier_trans(stmt):
    """Translates the YANG instance-identifier type to Ansible."""
    logging.debug(f"Translating instance-identifier type: {stmt.arg}")
    return {"type": "str"}


def leafref_trans(stmt):
    """Translates the YANG leafref type to Ansible."""
    logging.debug(f"Translating leafref type: {stmt.arg}")
    return {"type": "str"}


def find_identity(module, identity_name, searched_modules=None):
    """Finds an identity statement, preventing circular dependency loops.

    Args:
        module: The module to search in.
        identity_name: The name of the identity to find.
        searched_modules: A set of modules that have already been searched
                          to prevent infinite recursion.
    """

    logging.debug(f"Searching for identity '{identity_name}' in module '{module.arg}'")

    if searched_modules is None:
        searched_modules = set()

    if module in searched_modules:
        logging.debug(
            f"Module '{module.arg}' already searched for identity '{identity_name}'."
        )
        return None

    searched_modules.add(module)

    for identity in module.search("identity"):
        if identity.arg == identity_name:
            logging.debug(f"Found identity '{identity_name}' in module '{module.arg}'")
            return identity

    for imp in module.search("import"):
        imported_module = imp.i_module
        if imported_module:
            identity_stmt = find_identity(
                imported_module, identity_name, searched_modules
            )
            if identity_stmt:
                return identity_stmt

    logging.debug(f"Identity '{identity_name}' not found in module '{module.arg}'")
    return None


def collect_derived_identities(
    base_identity_stmt, collected_identities=None, searched_modules=None
):
    """Collects derived identities, preventing circular dependencies.

    Args:
      base_identity_stmt: The base identity statement.
      collected_identities:  Set of already collected identities (to avoid duplicates).
      searched_modules: Set of modules already searched (to avoid infinite loops).
    """

    logging.debug(f"Collecting derived identities for '{base_identity_stmt.arg}'")

    if collected_identities is None:
        collected_identities = set()
    if searched_modules is None:
        searched_modules = set()

    module = base_identity_stmt.i_module

    if module in searched_modules:
        logging.debug(
            f"Module '{module.arg}' already searched in collect_derived_identities."
        )
        return list(collected_identities)  # Return what we have so far

    searched_modules.add(module)

    def _collect_recursive(identity_stmt):
        if identity_stmt.arg in collected_identities:
            logging.debug(f"Identity '{identity_stmt.arg}' already collected.")
            return  # Avoid duplicates

        collected_identities.add(identity_stmt.arg)
        logging.debug(f"Collected identity: '{identity_stmt.arg}'")

        # Search in the current module
        for other_identity in module.search("identity"):
            base_stmt = other_identity.search_one("base")
            if base_stmt and base_stmt.arg == identity_stmt.arg:
                _collect_recursive(other_identity)

        # Search in imported modules
        for imp in module.search("import"):
            imported_module = imp.i_module
            if imported_module:
                for other_identity in imported_module.search("identity"):
                    base_stmt = other_identity.search_one("base")
                    if base_stmt and base_stmt.arg == identity_stmt.arg:
                        _collect_recursive(other_identity)

    _collect_recursive(base_identity_stmt)
    logging.debug(
        f"Derived identities for '{base_identity_stmt.arg}': {list(collected_identities)}"
    )
    return list(collected_identities)


def identityref_trans(stmt):
    """Translates the YANG identityref type to Ansible."""
    logging.debug(f"Translating identityref type: {stmt.arg}")
    base_stmt = stmt.search_one("base")
    if base_stmt:
        base_identity_stmt = find_identity(stmt.i_module, base_stmt.arg)
        if base_identity_stmt:
            derived_identities = collect_derived_identities(base_identity_stmt)
            return {"type": "str", "choices": derived_identities}
        else:
            logging.warning(f"Base identity not found: {base_stmt.arg}")
            return {
                "type": "str",
                "description": f"Base identity '{base_stmt.arg}' not found.",
            }
    else:
        logging.warning("identityref has no base.")
        return {"type": "str", "description": "Identityref with no base."}


def binary_trans(stmt):
    """Translates the YANG binary type to Ansible."""
    logging.debug(f"Translating binary type: {stmt.arg}")
    return {"type": "str"}


# Mapping of other YANG types to Ansible types
_other_type_trans_tbl = {
    "string": string_trans,
    "enumeration": enumeration_trans,
    "bits": bits_trans,
    "boolean": boolean_trans,
    "empty": empty_trans,
    "union": union_trans,
    "instance-identifier": instance_identifier_trans,
    "leafref": leafref_trans,
    "identityref": identityref_trans,
    "binary": binary_trans,  # Add this line
}


def other_type_trans(type_id, stmt):
    """Translates other YANG types to Ansible types using the lookup table."""
    return _other_type_trans_tbl[type_id](stmt)


def qualify_name(stmt):
    """Qualifies the name of a statement based on its namespace."""
    if stmt.parent.parent is None:
        prefix = stmt.i_module.arg
        qualified_name = stmt.arg
    elif stmt.top.arg != stmt.parent.top.arg:
        prefix = stmt.top.arg
        qualified_name = stmt.arg
    else:
        qualified_name = stmt.arg

    return qualified_name.replace("-", "_")


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
