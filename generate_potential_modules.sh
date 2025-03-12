#!/bin/bash
export PYANG_PLUGINPATH=/home/jgroom/src/resource_module_builder/pyang-plugin

# SAOS 10
saos10_yangs=(
  ciena-bgp
  ciena-mef-fp
  ciena-packet-ptp
  ciena-isis
  ciena-packet-xcvr
  ciena-cfm
  ciena-flexe            # multiple lists
  ciena-itut-g8032-draft # 1 list + props
  ciena-dhcpv6-client
  ciena-mef-logical-port
  ciena-igmp-snooping
  ciena-ospf
  ciena-ospfv3
  ciena-packet-otn-port
  ciena-routing-policy

  ciena-sat
  ciena-sr-policy
  ciena-sync
  ietf-alarms
  ietf-snmp
  ietf-twamp
  ciena-mef-access-flow  # multiple
  mef-cfm                # multiple
)
network_os=saos10
for yang in ${saos10_yangs[@]}; do
  pyang -f ansible -n $network_os -p yangs/$network_os yangs/$network_os/$yang.yang > schemas/$network_os/$yang.yml
  # resource=$(yq -e .RESOURCE rmb_models/$network_os/$yang.yml)
  # mkdir -p models/$network_os/$resource
  # cp rmb_models/$network_os/$yang.yml models/$network_os/$resource/model.yml
done

# WAVESERVERAi
waveserverai_yangs=(
  ciena-waveserver-aaa
  ciena-waveserver-application-auto-fiber-discovery
  ciena-waveserver-application-otdr
  ciena-waveserver-chassis
  ciena-waveserver-configuration
  ciena-waveserver-interfaces
  ciena-waveserver-license
  ciena-waveserver-lldp
  ciena-waveserver-module
  ciena-waveserver-ndp
  ciena-waveserver-pkix
  ciena-waveserver-pm
  ciena-waveserver-pm-tca
  ciena-waveserver-port
  ciena-waveserver-protection
  ciena-waveserver-ptp
  ciena-waveserver-snmp
  ciena-waveserver-software
  ciena-waveserver-spli
  ciena-waveserver-system
  ciena-waveserver-xcvr
)
network_os=waveserverai
for yang in ${waveserverai_yangs[@]}; do
  pyang -f ansible -n $network_os -p yangs/$network_os yangs/$network_os/$yang.yang > schemas/$network_os/$yang.yml
  # resource=$(yq -e .RESOURCE rmb_models/$network_os/$yang.yml)
  # mkdir -p models/$network_os/$resource
  # cp rmb_models/$network_os/$yang.yml models/$network_os/$resource/model.yml
done
