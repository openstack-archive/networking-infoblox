#!/usr/bin/env python
# Copyright 2015 Infoblox Inc.
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

import sys

from oslo_config import cfg
from oslo_log import log as logging

from neutron.common import config as common_config

from networking_infoblox.neutron.common import config
from networking_infoblox.neutron.common import ea_def_manager

LOG = logging.getLogger(__name__)

required_ea_defs = [
    {'name': 'Account', 'type': 'STRING',
     'comment': 'User ID in OpenStack'},
    {'name': 'CMP Type', 'type': 'STRING',
     'comment': 'CMP Types (OpenStack)'},
    {'name': 'Is External', 'type': 'STRING',
     'comment': 'For networks and network containers only'},
    {'name': 'Is Shared', 'type': 'STRING',
     'comment': 'For networks and network containers only'},
    {'name': 'IP Type', 'type': 'STRING',
     'comment': 'Type of IP address'},
    {'name': 'Network Encap', 'type': 'STRING',
     'comment': 'Type of IP address'},
    {'name': 'Network ID', 'type': 'STRING',
     'comment': 'Network ID in OpenStack'},
    {'name': 'Network Name', 'type': 'STRING',
     'comment': 'Network Name'},
    {'name': 'Physical Network Name', 'type': 'STRING',
     'comment': ''},
    {'name': 'Port Attached Device - Device ID', 'type': 'STRING',
     'comment': ''},
    {'name': 'Port Attached Device - Device Owner', 'type': 'STRING',
     'comment': ''},
    {'name': 'Port ID', 'type': 'STRING',
     'comment': ''},
    {'name': 'Segmentation ID', 'type': 'STRING',
     'comment': ''},
    {'name': 'Subnet ID', 'type': 'STRING',
     'comment': 'Subnet ID in OpenStack'},
    {'name': 'Subnet Name', 'type': 'STRING',
     'comment': 'Subnet Name in OpenStack'},
    {'name': 'Tenant ID', 'type': 'STRING',
     'comment': 'Tenant ID in OpenStack'},
    {'name': 'Tenant Name', 'type': 'STRING',
     'comment': 'Tenant Name in OpenStack'},
    {'name': 'VLAN ID', 'type': 'STRING',
     'comment': 'VLAN ID in OpenStack'},
    {'name': 'VM ID', 'type': 'STRING',
     'comment': 'Instance ID in OpenStack'},
    {'name': 'VM Name', 'type': 'STRING',
     'comment': 'Instance Name in OpenStack'}]


cfg.CONF(args=sys.argv[1:], default_config_files=['/etc/neutron/neutron.conf'])
common_config.setup_logging()
config.register_infoblox_ipam_opts(cfg.CONF)
config.register_infoblox_grid_opts(
    cfg.CONF, cfg.CONF.infoblox.cloud_data_center_id)
grid_info = config.get_infoblox_grid_opts(
    cfg.CONF.infoblox.cloud_data_center_id)

mgr = ea_def_manager.EA_Def_Manager(grid_info)

mgr.get_existing_ea_defs()

print("Missing EA Definitions:")
missing_ea_defs = mgr.find_missing_ea_defs(required_ea_defs)
if not missing_ea_defs:
    print("    None")
else:
    for ea_def in missing_ea_defs:
        print("    \"%s\"" % ea_def['name'])

print("")
ea_defs_created = mgr.create_missing_ea_defs()
print("EA Definitions created:")
if not ea_defs_created:
    print("    None")
else:
    for ea_def in ea_defs_created:
        print("    \"%s\"" % ea_def['name'])
print("")
