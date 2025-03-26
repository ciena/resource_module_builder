#!/bin/bash
export PYANG_PLUGINPATH=/home/jgroom/src/resource_module_builder/pyang-plugin

# Function to display help
show_help() {
  echo "Usage: $0 [OPTIONS] <network_os>"
  echo ""
  echo "Options:"
  echo "  --help    Show this help message and exit"
  echo ""
  echo "Example:"
  echo "  $0 saos10"
}

# Function to check if a YANG file contains useful definitions
contains_useful_definitions() {
  local yang_file=$1
  if pyang -f tree -p yangs/$network_os "$yang_file" | grep -q -E 'container|list|leaf|leaf-list'; then
    return 0
  else
    return 1
  fi
}

# Check for --help option
if [[ "$1" == "--help" ]]; then
  show_help
  exit 0
fi

# Check for network_os argument
if [[ -z "$1" ]]; then
  echo "Error: network_os argument is required"
  show_help
  exit 1
fi

network_os=$1

yang_files=()
for yang in yangs/$network_os/*.yang; do
  if contains_useful_definitions "$yang"; then
    yang_files+=("$(basename "$yang" .yang)")
  fi
done

printf "%s\n" "${yang_files[@]}"