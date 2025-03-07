"""Ansible output plugin"""

# pylint: disable=C0111

from __future__ import print_function

import re
import yaml
import optparse
import logging
from collections import OrderedDict

from pyang import plugin
from pyang import statements
from pyang import types
from pyang import error


class CustomDumper(yaml.SafeDumper):
    pass


def represent_ordered_dict(dumper, data):
    return dumper.represent_dict(data.items())


CustomDumper.add_representer(OrderedDict, represent_ordered_dict)


def load_mappings(file_path):
    with open(file_path, "r") as file:
        return yaml.safe_load(file)


def pyang_plugin_init():
    plugin.register_plugin(AnsiblePlugin())


def order_dict(obj, priority_keys):
    """
    Order dictionary keys with specified keys first, followed by others alphabetically.
    """
    if isinstance(obj, dict):
        # Create an ordered dictionary with prioritized keys
        ordered = OrderedDict((k, obj[k]) for k in priority_keys if k in obj)

        # Add the remaining keys in alphabetical order
        for key in sorted(obj.keys()):
            if key not in ordered:
                ordered[key] = obj[key]

        # Recursively apply ordering to nested dictionaries
        return OrderedDict(
            (k, order_dict(v, priority_keys)) for k, v in ordered.items()
        )
    elif isinstance(obj, list):
        return [order_dict(element, priority_keys) for element in obj]
    else:
        return obj


def get_nested_schema(schema, sub_path):
    keys = sub_path.split(".")
    for key in keys:
        schema = schema.get(key, {})
        if not schema:
            break
    return schema


class AnsiblePlugin(plugin.PyangPlugin):
    def add_output_format(self, fmts):
        fmts["ansible"] = self

    def add_opts(self, optparser):
        optlist = [
            optparse.make_option(
                "--ansible-debug",
                dest="ansible_debug",
                action="store_true",
                help="ansible debug",
            ),
            optparse.make_option(
                "-n",
                "--network-os",
                dest="network_os",
                help="Specify the network OS",
                default="saos10",  # Default value
            ),
        ]

        group = optparser.add_option_group("ansible-specific options")
        group.add_options(optlist)

    def setup_ctx(self, ctx):
        ctx.opts.stmts = None

    def setup_fmt(self, ctx):
        ctx.implicit_errors = False

    def emit(self, ctx, modules, fd):
        root_stmt = modules[0]
        if ctx.opts.ansible_debug:
            logging.basicConfig(level=logging.DEBUG)
            print("")
        if ctx.opts.network_os:
            network_os = ctx.opts.network_os
            logging.debug("network_os: %s", ctx.opts.network_os)

        # Extract the namespace
        namespace = root_stmt.search_one("namespace")
        if namespace:
            xml_namespace = namespace.arg
        else:
            xml_namespace = "No namespace found"

        schema = produce_schema(root_stmt)
        converted_schema = convert_schema_to_ansible(
            schema, xml_namespace, root_stmt, network_os
        )

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

        yaml_data = yaml.dump(
            final_data,
            Dumper=CustomDumper,
            default_flow_style=False,
            width=140,
            indent=2,
            allow_unicode=True,
        )
        fd.write(yaml_data)


def preprocess_string(s):
    result = re.sub(r"\s+", " ", s)
    return result.replace(":", ";")


def find_stmt_by_path(module, path):
    logging.debug(
        "in find_stmt_by_path with: %s %s path: %s", module.keyword, module.arg, path
    )

    if path is not None:
        spath = path.split("/")
        if spath[0] == "":
            spath = spath[1:]

    children = [
        child
        for child in module.i_children
        if child.keyword in statements.data_definition_keywords
    ]

    while spath is not None and len(spath) > 0:
        match = [
            child
            for child in children
            if child.arg == spath[0]
            and child.keyword in statements.data_definition_keywords
        ]
        if len(match) > 0:
            logging.debug("Match on: %s, path: %s", match[0].arg, spath)
            spath = spath[1:]
            children = match[0].i_children
            logging.debug("Path is now: %s", spath)
        else:
            logging.warning("Miss at %s, path: %s", children, spath)
            raise error.EmitError("Path '%s' does not exist in module" % path)

    logging.debug("Ended up with %s %s", match[0].keyword, match[0].arg)
    return match[0]


def produce_schema(root_stmt):
    logging.debug("in produce_schema: %s %s", root_stmt.keyword, root_stmt.arg)
    result = {}

    for child in root_stmt.i_children:
        if child.keyword in statements.data_definition_keywords:
            if child.keyword in producers:
                logging.debug("keyword hit on: %s %s", child.keyword, child.arg)
                add = producers[child.keyword](child)
                result.update(add)
            else:
                logging.warning("keyword miss on: %s %s", child.keyword, child.arg)
        else:
            if child.keyword == "rpc":
                logging.debug(
                    "skipping rpc. keyword not in data_definition_keywords: %s %s",
                    child.keyword,
                    child.arg,
                )
            else:
                logging.warning(
                    "keyword not in data_definition_keywords: %s %s",
                    child.keyword,
                    child.arg,
                )
    return result


def convert_schema_to_ansible(schema, xml_namespace, root_stmt, network_os):
    logging.warning(f"xml_namespace: {xml_namespace}")
    if len(schema) == 1:
        config = next(iter(schema.values()))

        resource = None
        xml_root_key = None
        xml_items = None
        xml_items_key = None
        module_name = None
        description = None
        short_description = None
        author = "Ciena"

        # Attempt to derive values from the YANG model
        for child in root_stmt.i_children:
            if child.keyword == "module":
                module_name = child.arg
            elif child.keyword == "container":
                # Skip config false containers
                if not child.i_config:
                    logging.debug(
                        "Skipping config false container: %s %s",
                        child.keyword,
                        child.arg,
                    )
                    continue
                resource = child.arg
                short_description = f"Manage {resource} on Ciena {network_os} devices"
                xml_root_key = child.arg
                module_name = f"{network_os}_{resource}"
                # Derive XML_ITEMS from the items in the container
                for sub_child in child.i_children:
                    if sub_child.keyword == "list":
                        xml_items = sub_child.arg
                        # check which key is used for the list
                        xml_items_key = sub_child.search_one("key").arg
                        config = get_nested_schema(config, f"suboptions.{xml_items}")
                        break
                # Extract short_description from the container description
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
            # TODO: Derive file list
            "EXAMPLES": ["merged_example_01.txt", "deleted_example_01.txt"],
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
    elif len(schema) > 1:
        logging.error(f"too many top level keys in schema: {schema.keys()}")
        raise error.EmitError(
            "Multiple top-level keys found in the schema. Expected only one."
        )
    else:
        raise error.EmitError("No top-level keys found in the schema.")


def produce_type(type_stmt):
    logging.debug("In produce_type with: %s %s", type_stmt.keyword, type_stmt.arg)
    type_id = type_stmt.arg

    # Follow typedef chain to resolve the base type
    while hasattr(type_stmt, "i_typedef") and type_stmt.i_typedef is not None:
        logging.debug(
            "Following typedef chain for: %s %s (typedef) %s",
            type_stmt.keyword,
            type_stmt.arg,
            type_stmt.i_typedef,
        )
        type_stmt = type_stmt.i_typedef.search_one("type")
        type_id = type_stmt.arg

    if types.is_base_type(type_id):
        if type_id in _numeric_type_trans_tbl:
            type_str = numeric_type_trans(type_id)
        elif type_id in _other_type_trans_tbl:
            type_str = other_type_trans(type_id, type_stmt)
        else:
            logging.warning(
                "Missing mapping of base type: %s %s", type_stmt.keyword, type_stmt.arg
            )
            type_str = {"type": "str", "description": "Missing description for: %s %s"}
    elif type_id in _other_type_trans_tbl:
        type_str = other_type_trans(type_id, type_stmt)
    else:
        logging.warning(
            "Missing mapping of: %s %s",
            type_stmt.keyword,
            type_stmt.arg,
            type_stmt.i_typedef,
        )
        type_str = {"type": "str"}
    return type_str


def produce_leaf(stmt):
    logging.debug("in produce_leaf: %s %s", stmt.keyword, stmt.arg)
    arg = qualify_name(stmt)

    # Check if the leaf is configurable
    if not stmt.i_config:
        logging.debug("Skipping non-configurable leaf: %s", arg)
        return {}

    type_stmt = stmt.search_one("type")
    type_str = produce_type(type_stmt)

    mandatory = stmt.search_one("mandatory")
    is_mandatory = mandatory is not None and mandatory.arg == "true"

    # Check if the leaf is a key in a list
    is_key = (
        stmt.parent.keyword == "list"
        and arg in stmt.parent.search_one("key").arg.split()
    )

    if not is_mandatory and not is_key:
        required = False
    else:
        required = True

    description = stmt.search_one("description")
    if description is not None:
        description_str = preprocess_string(description.arg)
        if is_key:
            list_parent = stmt.parent.arg
            description_str += f" ({list_parent} list key)"
    else:
        logging.warning("No description found for: %s %s", stmt.keyword, stmt.arg)
        description_str = "No description available"
        if is_key:
            list_parent = stmt.parent.arg
            description_str += f" ({list_parent} list key)"

    return {arg: {**type_str, "description": description_str, "required": required}}


def produce_list(stmt):
    logging.debug("in produce_list: %s %s", stmt.keyword, stmt.arg)
    arg = qualify_name(stmt)

    # Check if the leaf is configurable
    if not stmt.i_config:
        logging.debug("Skipping non-configurable leaf: %s", arg)
        return {}

    suboptions_dict = {}
    if hasattr(stmt, "i_children"):
        for child in stmt.i_children:
            if child.keyword in producers:
                logging.debug("keyword hit on: %s %s", child.keyword, child.arg)
                child_data = producers[child.keyword](child)
                for key, value in child_data.items():
                    suboptions_dict[key] = value
            else:
                logging.warning("keyword miss on: %s %s", child.keyword, child.arg)

    description = stmt.search_one("description")
    if description is not None:
        description_str = preprocess_string(description.arg)
    else:
        description_str = "No description available"

    result = {
        arg: {
            "type": "list",
            "elements": "dict",
            "description": description_str,
            "suboptions": suboptions_dict,
        }
    }
    logging.debug("In produce_list for %s, returning %s", stmt.arg, result)
    return result


def produce_leaf_list(stmt):
    logging.debug("in produce_leaf_list: %s %s", stmt.keyword, stmt.arg)
    arg = qualify_name(stmt)

    # Check if the leaf is configurable
    if not stmt.i_config:
        logging.debug("Skipping non-configurable leaf: %s", arg)
        return {}

    type_stmt = stmt.search_one("type")
    type_str = produce_type(type_stmt)

    description = stmt.search_one("description")
    if description is not None:
        description_str = preprocess_string(description.arg)
    else:
        logging.warning("No description found for: %s %s", stmt.keyword, stmt.arg)
        description_str = "No description available"

    result = {
        arg: {
            "type": "list",
            "elements": type_str["type"],
            "description": description_str,
        }
    }

    if "choices" in type_str:
        result[arg]["choices"] = type_str["choices"]

    logging.debug("In produce_leaf_list for %s, returning %s", stmt.arg, result)
    return result

def produce_container(stmt):
    logging.debug("in produce_container: %s %s", stmt.keyword, stmt.arg)
    arg = qualify_name(stmt)

    # Check if the leaf is configurable
    if not stmt.i_config:
        logging.debug("Skipping non-configurable leaf: %s", arg)
        return {}

    suboptions_dict = {}
    if hasattr(stmt, "i_children"):
        for child in stmt.i_children:
            if child.keyword in producers:
                logging.debug("keyword hit on: %s %s", child.keyword, child.arg)
                child_data = producers[child.keyword](child)
                suboptions_dict.update(child_data)
            else:
                logging.warning("keyword miss on: %s %s", child.keyword, child.arg)
    description = stmt.search_one("description")
    if description is not None:
        description_str = preprocess_string(description.arg)
    else:
        description_str = "No description available"

    result = {
        arg: {
            "type": "dict",
            "description": description_str,
            "suboptions": suboptions_dict,
        }
    }
    logging.debug("In produce_container, returning %s", result)
    return result


def produce_choice(stmt):
    logging.debug("in produce_choice: %s %s", stmt.keyword, stmt.arg)

    result = {}

    # https://tools.ietf.org/html/rfc6020#section-7.9.2
    for case in stmt.search("case"):
        if hasattr(case, "i_children"):
            for child in case.i_children:
                if child.keyword in producers:
                    logging.debug(
                        "keyword hit on (long version): %s %s", child.keyword, child.arg
                    )
                    result.update(producers[child.keyword](child))
                else:
                    logging.warning("keyword miss on: %s %s", child.keyword, child.arg)

    # Short ("case-less") version
    #  https://tools.ietf.org/html/rfc6020#section-7.9.2
    for child in stmt.substmts:
        logging.debug("checking on keywords with: %s %s", child.keyword, child.arg)
        if child.keyword in ["container", "leaf", "list", "leaf-list"]:
            logging.debug(
                "keyword hit on (short version): %s %s", child.keyword, child.arg
            )
            result.update(producers[child.keyword](child))

    logging.debug("In produce_choice, returning %s", result)
    return result


producers = {
    # "module":     produce_module,
    "container": produce_container,
    "list": produce_list,
    "leaf-list": produce_leaf_list,
    "leaf": produce_leaf,
    "choice": produce_choice,
}

_numeric_type_trans_tbl = {
    # https://tools.ietf.org/html/draft-ietf-netmod-yang-json-02#section-6
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
    trans_type = _numeric_type_trans_tbl[type_id][0]
    # Should include format string in return value
    # tformat = _numeric_type_trans_tbl[dtype][1]
    return {
        "type": trans_type,
    }


def string_trans(stmt):
    logging.debug("in string_trans with stmt %s %s", stmt.keyword, stmt.arg)
    result = {"type": "str"}
    return result


def enumeration_trans(stmt):
    logging.debug("in enumeration_trans with stmt %s %s", stmt.keyword, stmt.arg)
    result = {"type": "str", "choices": []}
    for enum in stmt.search("enum"):
        result["choices"].append(enum.arg)
    logging.debug("In enumeration_trans for %s, returning %s", stmt.arg, result)
    return result


def bits_trans(stmt):
    logging.debug("in bits_trans with stmt %s %s", stmt.keyword, stmt.arg)
    result = {"type": "list", "elements": "str", "choices": []}
    for bit in stmt.search("bit"):
        result["choices"].append(bit.arg)
    logging.debug("In bits_trans for %s, returning %s", stmt.arg, result)
    return result


def boolean_trans(stmt):
    logging.debug("in boolean_trans with stmt %s %s", stmt.keyword, stmt.arg)
    result = {"type": "bool"}
    return result


def empty_trans(stmt):
    logging.debug("in empty_trans with stmt %s %s", stmt.keyword, stmt.arg)
    result = {"type": "list", "suboptions": [{"type": "null"}]}
    # Likely needs more/other work per:
    #  https://tools.ietf.org/html/draft-ietf-netmod-yang-json-10#section-6.9
    return result


def union_trans(stmt):
    logging.debug("in union_trans with stmt %s %s", stmt.keyword, stmt.arg)
    result = {"type": "str"}
    return result


def instance_identifier_trans(stmt):
    logging.debug(
        "in instance_identifier_trans with stmt %s %s", stmt.keyword, stmt.arg
    )
    result = {"type": "str"}
    return result


def leafref_trans(stmt):
    logging.debug("in leafref_trans with stmt %s %s", stmt.keyword, stmt.arg)
    # TODO: Need to resolve i_leafref_ptr here
    result = {"type": "str"}
    return result


_other_type_trans_tbl = {
    # https://tools.ietf.org/html/draft-ietf-netmod-yang-json-02#section-6
    "string": string_trans,
    "enumeration": enumeration_trans,
    "bits": bits_trans,
    "boolean": boolean_trans,
    "empty": empty_trans,
    "union": union_trans,
    "instance-identifier": instance_identifier_trans,
    "leafref": leafref_trans,
    "empty": string_trans,
}


def other_type_trans(dtype, stmt):
    return _other_type_trans_tbl[dtype](stmt)


def qualify_name(stmt):
    # From: draft-ietf-netmod-yang-json
    # A namespace-qualified member name MUST be used for all members of a
    # top-level JSON object, and then also whenever the namespaces of the
    # data node and its parent node are different.  In all other cases, the
    # simple form of the member name MUST be used.
    if stmt.parent.parent is None:  # We're on top
        pfx = stmt.i_module.arg
        logging.debug("In qualify_name with: %s %s on top", stmt.keyword, stmt.arg)
        qualified_name = stmt.arg
        return qualified_name.replace("-", "_")
    if stmt.top.arg != stmt.parent.top.arg:  # Parent node is different
        pfx = stmt.top.arg
        logging.debug(
            "In qualify_name with: %s %s and parent is different",
            stmt.keyword,
            stmt.arg,
        )
        qualified_name = stmt.arg
        return qualified_name.replace("-", "_")
    return stmt.arg.replace("-", "_")


# New post-processing function to reorder suboptions
def reorder_required_first(data):
    """
    Post-process the schema to ensure required suboptions appear first.
    """
    if isinstance(data, dict):
        # Process suboptions if present
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

        # Recursively process all dictionary values
        return OrderedDict((k, reorder_required_first(v)) for k, v in data.items())
    elif isinstance(data, list):
        return [reorder_required_first(item) for item in data]
    else:
        return data
