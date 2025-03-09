#!/bin/bash
export PYANG_PLUGINPATH=/home/jgroom/src/resource_module_builder/pyang-plugin

# SAOS 10
saos10_yangs=(
  ciena-bgp
  ciena-cfm
  ciena-dhcpv6-client
  # ciena-flexe           # multiple
  ciena-igmp-snooping
  ciena-isis
  # ciena-mef-access-flow # multiple
  ciena-mef-fp
  ciena-mef-logical-port
  ciena-ospf
  ciena-ospfv3
  ciena-packet-otn-port
  ciena-packet-ptp
  ciena-packet-xcvr
  ciena-pkix
  ciena-routing-policy
  ciena-sat
  ciena-sr-policy
  ciena-sync
  ietf-alarms
  ietf-snmp
  ietf-twamp
  # mef-cfm               # multiple
)
network_os=saos10
for yang in ${saos10_yangs[@]}; do
  echo ""
  echo "Processing $yang.yang..."
  pyang -f ansible -n $network_os -p yangs/$network_os yangs/$network_os/$yang.yang >rmb_models/$network_os/$yang.yml
  resource=$(yq -e .RESOURCE rmb_models/$network_os/$yang.yml)
  mkdir -p models/$network_os/$resource
  cp rmb_models/$network_os/$yang.yml models/$network_os/$resource/model.yml
  echo "Finished processing $yang.yang"
  echo ""
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
  echo "Processing $yang.yang..."
  pyang -f ansible -n $network_os -p yangs/$network_os yangs/$network_os/$yang.yang >rmb_models/$network_os/$yang.yml
  resource=$(yq -e .RESOURCE rmb_models/$network_os/$yang.yml)
  mkdir -p models/$network_os/$resource
  cp rmb_models/$network_os/$yang.yml models/$network_os/$resource/model.yml
  echo "Finished processing $yang.yang"
done
