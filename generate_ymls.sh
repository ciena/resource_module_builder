#!/bin/bash
export PYANG_PLUGINPATH=~/src/resource_module_builder/pyang-plugin
# WAVESERVER5
pyang -f ansible -p yangs/waveserver5 -i models/waveserver5/system/input.yml ciena-waveserver-system.yang > models/waveserver5/system/model.yml
pyang -f ansible -p yangs/waveserver5 -i models/waveserver5/xcvrs/input.yml ciena-waveserver-xcvr.yang > models/waveserver5/xcvrs/model.yml
pyang -f ansible -p yangs/waveserver5 -i models/waveserver5/interfaces/input.yml ciena-waveserver-interfaces.yang > models/waveserver5/interfaces/model.yml
pyang -f ansible -p yangs/waveserver5 -i models/waveserver5/aaa/input.yml ciena-waveserver-aaa.yang > models/waveserver5/aaa/model.yml
pyang -f ansible -p yangs/waveserver5 -i models/waveserver5/modules/input.yml ciena-waveserver-module.yang > models/waveserver5/modules/model.yml
pyang -f ansible -p yangs/waveserver5 -i models/waveserver5/ports/input.yml ciena-waveserver-port.yang > models/waveserver5/ports/model.yml
pyang -f ansible -p yangs/waveserver5 -i models/waveserver5/snmp/input.yml ciena-waveserver-snmp.yang > models/waveserver5/snmp/model.yml
pyang -f ansible -p yangs/waveserver5 -i models/waveserver5/chassis/input.yml ciena-waveserver-chassis.yang > models/waveserver5/chassis/model.yml
pyang -f ansible -p yangs/waveserver5 -i models/waveserver5/ptps/input.yml ciena-waveserver-ptp.yang > models/waveserver5/ptps/model.yml
pyang -f ansible -p yangs/waveserver5 -i models/waveserver5/pm/input.yml ciena-waveserver-pm.yang > models/waveserver5/pm/model.yml
pyang -f ansible -p yangs/waveserver5 -i models/waveserver5/snmp/input.yml ciena-waveserver-snmp.yang > models/waveserver5/snmp/model.yml
# SAOS10
pyang -f ansible -p yangs/saos10 -i models/saos10/classifiers/input.yml yangs/saos10/ciena-mef-classifier.yang > models/saos10/classifiers/model.yml
pyang -f ansible -p yangs/saos10 -i models/saos10/fds/input.yml yangs/saos10/ciena-mef-fd.yang > models/saos10/fds/model.yml
pyang -f ansible -p yangs/saos10 -i models/saos10/fps/input.yml yangs/saos10/ciena-mef-fp.yang > models/saos10/fps/model.yml
