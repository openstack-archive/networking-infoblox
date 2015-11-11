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
from networking_infoblox.neutron.common import constants as const
from infoblox_client import connector
from infoblox_client import object_manager

LOG = logging.getLogger(__name__)

required_ea_defs = [
    {'name': const.EA_ACCOUNT, 'type': 'STRING',
     'comment': 'User ID in OpenStack'},

    {'name': const.EA_CLOUD_API_OWNED, 'type': 'ENUM',
     'list_values': [{'value': 'True'}, {'value': 'False'}],
     'comment': 'Is Cloud API owned'},

    {'name': const.EA_CMP_TYPE, 'type': 'STRING',
     'comment': 'CMP Types (OpenStack)'},

    {'name': const.EA_IS_EXTERNAL, 'type': 'ENUM',
     'list_values': [{'value': 'True'}, {'value': 'False'}],
     'comment': 'For networks and network containers only'},

    {'name': const.EA_IS_SHARED, 'type': 'ENUM',
     'list_values': [{'value': 'True'}, {'value': 'False'}],
     'comment': 'For networks and network containers only'},

    {'name': const.EA_IP_TYPE, 'type': 'ENUM',
     'list_values': [{'value': const.IP_TYPE_ELASTIC},
                     {'value': const.IP_TYPE_FIXED},
                     {'value': const.IP_TYPE_FLOATING},
                     {'value': const.IP_TYPE_PRIVATE},
                     {'value': const.IP_TYPE_PUBLIC}],
     'comment': 'Type of IP address'},

    {'name': const.EA_NETWORK_ENCAP, 'type': 'STRING',
     'comment': 'Type of IP address'},

    {'name': const.EA_NETWORK_ID, 'type': 'STRING',
     'comment': 'Network ID in OpenStack'},

    {'name': const.EA_NETWORK_NAME, 'type': 'STRING',
     'comment': 'Network Name'},

    {'name': const.EA_PHYSICAL_NETWORK_NAME, 'type': 'STRING',
     'comment': ''},

    {'name': const.EA_PORT_DEVICE_ID, 'type': 'STRING',
     'comment': ''},

    {'name': const.EA_PORT_DEVICE_OWNER, 'type': 'STRING',
     'comment': ''},

    {'name': const.EA_PORT_ID, 'type': 'STRING',
     'comment': ''},

    {'name': const.EA_SEGMENTATION_ID, 'type': 'STRING',
     'comment': ''},

    {'name': const.EA_SUBNET_ID, 'type': 'STRING',
     'comment': 'Subnet ID in OpenStack'},

    {'name': const.EA_SUBNET_NAME, 'type': 'STRING',
     'comment': 'Subnet Name in OpenStack'},

    {'name': const.EA_TENANT_ID, 'type': 'STRING',
     'comment': 'Tenant ID in OpenStack'},

    {'name': const.EA_TENANT_NAME, 'type': 'STRING',
     'comment': 'Tenant Name in OpenStack'},

    {'name': const.EA_VM_ID, 'type': 'STRING',
     'comment': 'Instance ID in OpenStack'},

    {'name': const.EA_VM_NAME, 'type': 'STRING',
     'comment': 'Instance Name in OpenStack'}]


cfg.CONF(args=sys.argv[1:], default_config_files=['/etc/neutron/neutron.conf'])
common_config.setup_logging()
config.register_infoblox_ipam_opts(cfg.CONF)
config.register_infoblox_grid_opts(
    cfg.CONF, cfg.CONF.infoblox.cloud_data_center_id)
grid_info = config.get_infoblox_grid_opts(
    cfg.CONF.infoblox.cloud_data_center_id)

conn_info = {}
conn_info['host'] = grid_info['grid_master_host']
conn_info['username'] = grid_info['admin_user_name']
conn_info['password'] = grid_info['admin_password']
conn_info['wapi_version'] = grid_info['wapi_version']
conn_info['ssl_verify'] = grid_info['ssl_verify']
conn_info['http_pool_connections'] = grid_info['http_pool_connections']
conn_info['http_pool_maxsize'] = grid_info['http_pool_maxsize']
conn_info['http_request_timeout'] = grid_info['http_request_timeout']
conn = connector.Connector(conn_info)

mgr = object_manager.InfobloxObjectManager(conn)
mgr.create_required_ea_definitions(required_ea_defs)
