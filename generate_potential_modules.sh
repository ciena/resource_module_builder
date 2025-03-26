#!/bin/bash
export PYANG_PLUGINPATH=./pyang-plugin

# SAOS 10
saos10_yangs=(
  ciena-bgp
  ciena-cfm
  ciena-dhcpv6-client
  ciena-evpn
  ciena-flexe            # multiple lists
  ciena-igmp-snooping
  ciena-isis
  ciena-itut-g8032-draft # 1 list + props
  ciena-l2vpn
  ciena-ldp
  ciena-mef-access-flow  # multiple
  ciena-mef-classifier
  ciena-mef-fd
  ciena-mef-fp
  ciena-mef-logical-port
  ciena-mpls
  # ciena-openconfig-interfaces  # Empty
  ciena-ospf
  ciena-ospfv3
  ciena-packet-otn-port
  ciena-packet-ptp
  ciena-packet-xcvr
  ciena-platform
  ciena-rib
  ciena-routing-policy
  ciena-sat
  ciena-sr
  ciena-sr-policy
  ciena-sync
  # ciena-system          # Empty
  # ciena-vrf             # Not Handled yet. Top level list
  ietf-snmp
  ietf-twamp
  # mef-cfm               # Not Handled yet. Top level list
  openconfig-system
)
network_os=saos10
for yang in ${saos10_yangs[@]}; do
  pyang -f ansible -n $network_os -p yangs/$network_os yangs/$network_os/$yang.yang > schemas/$network_os/$yang.yml
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
done
