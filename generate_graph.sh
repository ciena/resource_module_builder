#!/bin/bash
export PYANG_PLUGINPATH=/home/jgroom/src/resource_module_builder/pyang-plugin

saos10_yangs=(
  ciena-bgp
  ciena-mef-classifier
  ciena-mef-fd
  ciena-mef-fp
  ciena-mef-logical-port
  ciena-mpls
)

network_os=saos10
yang_dir="yangs/$network_os"

# Ensure the directory exists
if [ ! -d "$yang_dir" ]; then
  echo "Error: Directory $yang_dir does not exist."
  exit 1
fi

# Pick the first module as the main entry point
main_module="${saos10_yangs[0]}"
main_file="$yang_dir/$main_module.yang"

if [ ! -f "$main_file" ]; then
  echo "Error: Main module $main_file not found."
  exit 1
fi

# Run pyang with one main module and the path to find dependencies
pyang -f yang-graph -p "$yang_dir" "$main_file" --verbose > graph.yml 2> error.log

if [ $? -ne 0 ]; then
  echo "Pyang failed. Check error.log for details."
  cat error.log
  exit 1
fi

echo "Graph generated successfully in graph.yml"
