#!/bin/bash
export PYANG_PLUGINPATH=/home/jgroom/src/resource_module_builder/pyang-plugin
# SAOS 10
saos10_yangs=(
  ciena-mef-classifier
  ciena-mef-fd
  ciena-mef-fp
  ciena-mef-logical-port
  openconfig-system
  ciena-system
  ciena-rib
)
network_os=saos10
for yang in ${saos10_yangs[@]}; do
  pyang -f ansible -n $network_os -p yangs/$network_os yangs/$network_os/$yang.yang > rmb_models/$network_os/$yang.yml
  mkdir -p models/$network_os/$yang
  cp rmb_models/$network_os/$yang.yml models/$network_os/$yang/model.yml
done

# WAVESERVERAi
waveserverai_yangs=(
  # ciena-waveserver-aaa
  # ciena-waveserver-application-auto-fiber-discovery
  # ciena-waveserver-application-otdr
  # ciena-waveserver-chassis
  # ciena-waveserver-configuration
  # ciena-waveserver-interfaces
  # ciena-waveserver-license
  # ciena-waveserver-link-data-telemetry
  # ciena-waveserver-lldp
  # ciena-wavesever-logging
  # ciena-waveserver-module
  # ciena-waveserver-ndp
  # ciena-waveserver-pkix
  # ciena-waveserver-pm
  # ciena-waveserver-pm-tca
  # ciena-waveserver-port
  # ciena-waveserver-protection
  # ciena-waveserver-ptp
  # ciena-waveserver-snmp
  # ciena-waveserver-software
  # ciena-waveserver-spli
  ciena-waveserver-system
  # ciena-waveserver-topology
  ciena-waveserver-xcvr
)
network_os=waveserverai
for yang in ${waveserverai_yangs[@]}; do
  pyang -f ansible -n $network_os -p yangs/$network_os yangs/$network_os/$yang.yang > rmb_models/$network_os/$yang.yml
  mkdir -p models/$network_os/$yang
  cp rmb_models/$network_os/$yang.yml models/$network_os/$yang/model.yml
done
