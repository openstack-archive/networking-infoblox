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

from infoblox_client import object_manager
from networking_infoblox.neutron.common import config
from networking_infoblox.neutron.common import constants as const
from networking_infoblox.neutron.common import utils

LOG = logging.getLogger(__name__)

required_ea_defs = [
    # Cloud Property EAs
    {'name': const.EA_ACCOUNT, 'type': 'STRING', 'flags': 'C',
     'comment': 'User ID in OpenStack'},

    {'name': const.EA_CLOUD_API_OWNED, 'type': 'ENUM', 'flags': 'C',
     'list_values': [{'value': 'True'}, {'value': 'False'}],
     'comment': 'Is Cloud API owned'},

    {'name': const.EA_CMP_TYPE, 'type': 'STRING', 'flags': 'C',
     'comment': 'CMP Types (OpenStack)'},

    {'name': const.EA_IS_EXTERNAL, 'type': 'ENUM', 'flags': 'C',
     'list_values': [{'value': 'True'}, {'value': 'False'}],
     'comment': 'For networks and network containers only'},

    {'name': const.EA_IS_SHARED, 'type': 'ENUM', 'flags': 'C',
     'list_values': [{'value': 'True'}, {'value': 'False'}],
     'comment': 'For networks and network containers only'},

    {'name': const.EA_IP_TYPE, 'type': 'ENUM', 'flags': 'C',
     'list_values': [{'value': const.IP_TYPE_ELASTIC},
                     {'value': const.IP_TYPE_FIXED},
                     {'value': const.IP_TYPE_FLOATING},
                     {'value': const.IP_TYPE_PRIVATE},
                     {'value': const.IP_TYPE_PUBLIC}],
     'comment': 'Type of IP address'},

    {'name': const.EA_NETWORK_ENCAP, 'type': 'STRING', 'flags': 'C',
     'comment': 'Type of IP address'},

    {'name': const.EA_NETWORK_ID, 'type': 'STRING', 'flags': 'C',
     'comment': 'Network ID in OpenStack'},

    {'name': const.EA_NETWORK_NAME, 'type': 'STRING', 'flags': 'C',
     'comment': 'Network Name'},

    {'name': const.EA_PHYSICAL_NETWORK_NAME, 'type': 'STRING', 'flags': 'C',
     'comment': ''},

    {'name': const.EA_PORT_DEVICE_ID, 'type': 'STRING', 'flags': 'C',
     'comment': ''},

    {'name': const.EA_PORT_DEVICE_OWNER, 'type': 'STRING', 'flags': 'C',
     'comment': ''},

    {'name': const.EA_PORT_ID, 'type': 'STRING', 'flags': 'C',
     'comment': ''},

    {'name': const.EA_SEGMENTATION_ID, 'type': 'STRING', 'flags': 'C',
     'comment': ''},

    {'name': const.EA_SUBNET_ID, 'type': 'STRING', 'flags': 'C',
     'comment': 'Subnet ID in OpenStack'},

    {'name': const.EA_SUBNET_NAME, 'type': 'STRING', 'flags': 'C',
     'comment': 'Subnet Name in OpenStack'},

    {'name': const.EA_TENANT_ID, 'type': 'STRING', 'flags': 'C',
     'comment': 'Tenant ID in OpenStack'},

    {'name': const.EA_TENANT_NAME, 'type': 'STRING', 'flags': 'C',
     'comment': 'Tenant Name in OpenStack'},

    {'name': const.EA_VM_ID, 'type': 'STRING', 'flags': 'C',
     'comment': 'Instance ID in OpenStack'},

    {'name': const.EA_VM_NAME, 'type': 'STRING', 'flags': 'C',
     'comment': 'Instance Name in OpenStack'},

    # Grid Configuration EAs
    {'name': const.EA_GRID_CONFIG_GRID_SYNC_SUPPORT,
     'type': 'STRING', 'flags': '',
     'allowed_object_types': ['Member'],
     'comment': 'Grid Configuration'},

    {'name': const.EA_GRID_CONFIG_GRID_SYNC_MINIMUM_WAIT_TIME,
     'type': 'STRING', 'flags': '',
     'allowed_object_types': ['Member'],
     'comment': 'Grid Configuration'},

    {'name': const.EA_GRID_CONFIG_DEFAULT_NETWORK_VIEW_SCOPE,
     'type': 'STRING', 'flags': '',
     'allowed_object_types': ['Member'],
     'comment': 'Grid Configuration'},

    {'name': const.EA_GRID_CONFIG_DEFAULT_NETWORK_VIEW,
     'type': 'STRING', 'flags': '',
     'allowed_object_types': ['Member'],
     'comment': 'Grid Configuration'},

    {'name': const.EA_GRID_CONFIG_DEFAULT_HOST_NAME_PATTERN,
     'type': 'STRING', 'flags': '',
     'allowed_object_types': ['Member'],
     'comment': 'Grid Configuration'},

    {'name': const.EA_GRID_CONFIG_DEFAULT_DOMAIN_NAME_PATTERN,
     'type': 'STRING', 'flags': '',
     'allowed_object_types': ['Member'],
     'comment': 'Grid Configuration'},

    {'name': const.EA_GRID_CONFIG_NS_GROUP,
     'type': 'STRING', 'flags': '',
     'allowed_object_types': ['Member'],
     'comment': 'Grid Configuration'},

    {'name': const.EA_GRID_CONFIG_DNS_VIEW,
     'type': 'STRING', 'flags': '',
     'allowed_object_types': ['Member'],
     'comment': 'Grid Configuration'},

    {'name': const.EA_GRID_CONFIG_NETWORK_TEMPLATE,
     'type': 'STRING', 'flags': '',
     'allowed_object_types': ['Member'],
     'comment': 'Grid Configuration'},

    {'name': const.EA_GRID_CONFIG_ADMIN_NETWORK_DELETION,
     'type': 'STRING', 'flags': '',
     'allowed_object_types': ['Member'],
     'comment': 'Grid Configuration'},

    {'name': const.EA_GRID_CONFIG_IP_ALLOCATION_STRATEGY,
     'type': 'STRING', 'flags': '',
     'allowed_object_types': ['Member'],
     'comment': 'Grid Configuration'},

    {'name': const.EA_GRID_CONFIG_DNS_RECORD_BINDING_TYPES,
     'type': 'STRING', 'flags': '',
     'allowed_object_types': ['Member'],
     'comment': 'Grid Configuration'},

    {'name': const.EA_GRID_CONFIG_DNS_RECORD_UNBINDING_TYPES,
     'type': 'STRING', 'flags': '',
     'allowed_object_types': ['Member'],
     'comment': 'Grid Configuration'},

    {'name': const.EA_GRID_CONFIG_DNS_RECORD_REMOVABLE_TYPES,
     'type': 'STRING', 'flags': '',
     'allowed_object_types': ['Member'],
     'comment': 'Grid Configuration'},

    {'name': const.EA_GRID_CONFIG_DHCP_RELAY_MANAGEMENT_NETWORK_VIEW,
     'type': 'STRING', 'flags': '',
     'allowed_object_types': ['Member'],
     'comment': 'Grid Configuration'},

    {'name': const.EA_GRID_CONFIG_DHCP_RELAY_MANAGEMENT_NETWORK,
     'type': 'STRING', 'flags': '',
     'allowed_object_types': ['Member'],
     'comment': 'Grid Configuration'},

    {'name': const.EA_GRID_CONFIG_DHCP_SUPPORT,
     'type': 'STRING', 'flags': '',
     'allowed_object_types': ['Member'],
     'comment': 'Grid Configuration'},

    # Mapping EAs
    {'name': const.EA_MAPPING_ADDRESS_SCOPE_ID,
     'type': 'STRING', 'flags': 'CGV',
     'allowed_object_types': ['NetworkView'],
     'comment': 'Mapping'},

    {'name': const.EA_MAPPING_ADDRESS_SCOPE_NAME,
     'type': 'STRING', 'flags': 'CGV',
     'allowed_object_types': ['NetworkView'],
     'comment': 'Mapping'},

    {'name': const.EA_MAPPING_TENANT_ID,
     'type': 'STRING', 'flags': 'CGV',
     'allowed_object_types': ['NetworkView'],
     'comment': 'Mapping'},

    {'name': const.EA_MAPPING_TENANT_NAME,
     'type': 'STRING', 'flags': 'CGV',
     'allowed_object_types': ['NetworkView'],
     'comment': 'Mapping'},

    {'name': const.EA_MAPPING_TENANT_CIDR,
     'type': 'STRING', 'flags': 'CGV',
     'allowed_object_types': ['NetworkView'],
     'comment': 'Mapping'},

    {'name': const.EA_MAPPING_NETWORK_ID,
     'type': 'STRING', 'flags': 'CGV',
     'allowed_object_types': ['NetworkView'],
     'comment': 'Mapping'},

    {'name': const.EA_MAPPING_NETWORK_NAME,
     'type': 'STRING', 'flags': 'CGV',
     'allowed_object_types': ['NetworkView'],
     'comment': 'Mapping'},

    {'name': const.EA_MAPPING_SUBNET_ID,
     'type': 'STRING', 'flags': 'CGV',
     'allowed_object_types': ['NetworkView'],
     'comment': 'Mapping'},

    {'name': const.EA_MAPPING_SUBNET_CIDR,
     'type': 'STRING', 'flags': 'CGV',
     'allowed_object_types': ['NetworkView'],
     'comment': 'Mapping'}]


cfg.CONF(args=sys.argv[1:], default_config_files=['/etc/neutron/neutron.conf'])
common_config.setup_logging()
config.register_infoblox_ipam_opts(cfg.CONF)
config.register_infoblox_grid_opts(
    cfg.CONF, cfg.CONF.infoblox.cloud_data_center_id)

conn = utils.get_connector()

mgr = object_manager.InfobloxObjectManager(conn)
mgr.create_required_ea_definitions(required_ea_defs)
