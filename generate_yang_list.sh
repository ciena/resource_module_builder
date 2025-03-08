#!/bin/bash

# SAOS 10
network_os=saos10
# Function to check if a YANG file contains useful definitions
contains_useful_definitions() {
  local yang_file=$1
  if pyang -f tree -p yangs/$network_os "$yang_file" | grep -q -E 'container|list|leaf|leaf-list'; then
    return 0
  else
    return 1
  fi
}

saos10_yangs=()
for yang in yangs/saos10/*.yang; do
  if contains_useful_definitions "$yang"; then
    saos10_yangs+=("$(basename "$yang" .yang)")
  fi
done

printf "%s\n" "${saos10_yangs[@]}"
