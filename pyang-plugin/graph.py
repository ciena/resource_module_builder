"""YANG Graph Plugin for list-to-list key relationships"""

from __future__ import print_function
import yaml
import optparse
import logging
import sys
import re
from collections import defaultdict

from pyang import plugin
from pyang import statements
from pyang import error

sys.setrecursionlimit(10000)
logging.basicConfig(level=logging.DEBUG)


class YangGraphData:
    def __init__(self):
        self.nodes = {}
        self.edges = defaultdict(dict)
        self.modules = set()

    def add_node(self, name, node_type, module, metadata=None):
        full_name = f"{module}:{name}"
        if full_name not in self.nodes:
            self.nodes[full_name] = {
                "type": node_type,
                "module": module,
                **(metadata or {}),
            }

    def add_edge(self, source, target, relationship_type):
        if source in self.nodes and target in self.nodes:
            self.edges[source][target] = relationship_type

    def to_cytoscape(self):
        elements = []
        for node_id, data in self.nodes.items():
            elements.append({"data": {"id": node_id, **data}})
        for source, targets in self.edges.items():
            for target, rel in targets.items():
                elements.append(
                    {"data": {"source": source, "target": target, "relationship": rel}}
                )
        return elements


class YangGraph(plugin.PyangPlugin):
    def add_output_format(self, fmts):
        fmts["yang-graph"] = self

    def add_opts(self, optparser):
        optlist = [
            optparse.make_option(
                "--config-only",
                action="store_true",
                dest="config_only",
                help="Only include config true statements in the graph.",
            ),
        ]
        group = optparser.add_option_group("YangGraph options")
        group.add_options(optlist)

    def setup_ctx(self, ctx):
        ctx.opts.stmts = None
        logging.debug("Context setup complete")

    def setup_fmt(self, ctx):
        ctx.implicit_errors = False
        logging.debug("Format setup complete")

    def emit(self, ctx, modules, fd):
        logging.debug(
            f"Entering emit with {len(modules)} modules: {[m.arg for m in modules]}"
        )
        if not modules:
            raise error.EmitError("No modules provided to emit.")
        if len(modules) > 1:
            logging.warning(
                "Multiple modules provided; using only the first one as the entry point"
            )

        main_module = modules[0]  # Use the first module as the entry point
        graph = YangGraphData()
        all_modules = set()

        try:
            logging.debug(f"Starting with main module: {main_module.arg}")
            self._process_module(main_module, all_modules, graph, ctx.opts.config_only)

            unprocessed = all_modules - {main_module}
            logging.debug(f"Unprocessed dependent modules: {len(unprocessed)}")
            while unprocessed:
                module = unprocessed.pop()
                logging.debug(f"Processing dependent module: {module.arg}")
                self._process_module(module, all_modules, graph, ctx.opts.config_only)

            logging.debug(
                f"Graph contains {len(graph.nodes)} nodes and {sum(len(targets) for targets in graph.edges.values())} edges"
            )
        except Exception as e:
            logging.error(f"Error during module processing: {e}", exc_info=True)
            raise error.EmitError(f"Module processing failed: {e}")

        result = {"graph": graph.to_cytoscape()}
        try:
            yaml_data = yaml.dump(
                result,
                default_flow_style=False,
                width=140,
                indent=2,
                allow_unicode=True,
                sort_keys=False,
            )
            fd.write(yaml_data)
            logging.info("Graph output written successfully")
        except yaml.YAMLError as e:
            logging.error(f"Error writing YAML: {e}")
            raise

    def _process_module(self, module, all_modules, graph, config_only):
        if module in all_modules:
            logging.debug(f"Skipping already processed module: {module.arg}")
            return
        all_modules.add(module)
        logging.debug(f"Processing module: {module.arg}")
        if config_only:
            module = prune_statements(module)

        try:
            self._build_graph(module, graph)
        except Exception as e:
            logging.error(f"Error building graph for {module.arg}: {e}", exc_info=True)

        # Add dependencies to the processing queue
        for imp in module.search("import"):
            if imp.i_module:
                all_modules.add(imp.i_module)
                logging.debug(f"Added imported module: {imp.i_module.arg}")
        for inc in module.search("include"):
            if inc.i_module:
                all_modules.add(inc.i_module)
                logging.debug(f"Added included module: {inc.i_module.arg}")

    def _build_graph(self, stmt, graph, module=None):
        if not module:
            module = stmt.i_module

        if stmt.keyword == "list":
            list_name = qualify_name(stmt, module)
            description = stmt.search_one("description")
            description_str = (
                preprocess_string(description.arg)
                if description
                else "No description available"
            )
            key_stmt = stmt.search_one("key")
            key = key_stmt.arg if key_stmt else None
            graph.add_node(
                list_name,
                "list",
                module.arg,
                {"description": description_str, "key": key},
            )

            for child in stmt.i_children:
                if (
                    child.keyword == "leaf"
                    and child.search_one("type")
                    and child.search_one("type").arg == "leafref"
                ):
                    path_stmt = child.search_one("type").search_one("path")
                    if path_stmt:
                        try:
                            target_module, target_list, target_key = (
                                self._resolve_leafref_path(path_stmt.arg, module)
                            )
                            if target_list and target_key:
                                target_full_name = f"{target_module.arg}:{target_list}"
                                if list_name != target_full_name:
                                    graph.add_node(
                                        list_name,
                                        "list",
                                        module.arg,
                                        {"description": description_str, "key": key},
                                    )
                                    graph.add_node(
                                        target_full_name,
                                        "list",
                                        target_module.arg,
                                        {"description": "Referenced list"},
                                    )
                                    graph.add_edge(
                                        list_name,
                                        target_full_name,
                                        f"references_key:{target_key}",
                                    )
                                    logging.debug(
                                        f"Added edge: {list_name} -> {target_full_name}"
                                    )
                        except Exception as e:
                            logging.warning(
                                f"Failed to resolve leafref {path_stmt.arg}: {e}"
                            )

        for child in getattr(stmt, "i_children", []):
            self._build_graph(child, graph, module)

    def _resolve_leafref_path(self, path, source_module):
        parts = path.strip("/").split("/")
        target_module = source_module
        target_list = None
        target_key = None

        for i, part in enumerate(parts):
            if ":" in part:
                prefix, name = part.split(":", 1)
                target_module = next(
                    (
                        m
                        for m in source_module.i_ctx.modules.values()
                        if m.search_one("prefix")
                        and m.search_one("prefix").arg == prefix
                    ),
                    source_module,
                )
                if i == len(parts) - 1:
                    target_key = name.replace("-", "_")
                elif i == len(parts) - 2:
                    target_list = name.replace("-", "_")
            elif part:
                if i == len(parts) - 1:
                    target_key = part.replace("-", "_")
                elif i == len(parts) - 2:
                    target_list = part.replace("-", "_")

        if target_module and target_list and target_key:
            target_stmt = self._find_list_stmt(target_module, target_list)
            if (
                target_stmt
                and target_stmt.keyword == "list"
                and target_stmt.search_one("key")
                and target_key in target_stmt.search_one("key").arg.split()
            ):
                return target_module, target_list, target_key
        return target_module, None, None

    def _find_list_stmt(self, module, list_name):
        for stmt in module.i_children:
            if stmt.keyword == "list" and stmt.arg.replace("-", "_") == list_name:
                return stmt
            for child in getattr(stmt, "i_children", []):
                found = self._find_list_stmt_recursive(child, list_name)
                if found:
                    return found
        return None

    def _find_list_stmt_recursive(self, stmt, list_name):
        if stmt.keyword == "list" and stmt.arg.replace("-", "_") == list_name:
            return stmt
        for child in getattr(stmt, "i_children", []):
            found = self._find_list_stmt_recursive(child, list_name)
            if found:
                return found
        return None


def prune_statements(stmt):
    pruned_children = []
    for child in stmt.i_children:
        if child.keyword in ("notification", "rpc", "augment", "deviation"):
            continue
        if (
            child.keyword in ("container", "leaf", "leaf-list", "list")
            and not child.i_config
        ):
            continue
        if hasattr(child, "i_children"):
            prune_statements(child)
        pruned_children.append(child)
    stmt.i_children = pruned_children
    return stmt


def preprocess_string(s):
    return re.sub(r"\s+", " ", s).replace(":", ";")


def qualify_name(stmt, module):
    if stmt.parent and stmt.parent.parent is None:
        return f"{module.arg}:{stmt.arg.replace('-', '_')}"
    return stmt.arg.replace("-", "_")


def pyang_plugin_init():
    plugin.register_plugin(YangGraph())
