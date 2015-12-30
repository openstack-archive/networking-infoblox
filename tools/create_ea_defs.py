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

import getpass
import sys

from oslo_config import cfg
from oslo_log import log as logging

from neutron.common import config as common_config

from infoblox_client import object_manager
from infoblox_client import objects
from infoblox_client import utils as ib_utils
from networking_infoblox.neutron.common import config
from networking_infoblox.neutron.common import constants as const
from networking_infoblox.neutron.common import utils

LOG = logging.getLogger(__name__)


credentials = None
print("\n\n")
print("In order to create Extensible Attribute definitions,")
print("superuser privilege is required.\n")
print("If the preconfigured credentials already has superuser privilege,")
print("just hit <ENTER> when prompted for user name.\n")
print("Otherwise, please enter user name and password of a user that \
has superuser privilege.\n")
username = raw_input("Enter user name: ")
if len(username) > 0:
    password = getpass.getpass("Enter password: ")
    credentials = {'username': username, 'password': password}

cfg.CONF(args=sys.argv[1:], default_config_files=['/etc/neutron/neutron.conf'])
common_config.setup_logging()
config.register_infoblox_ipam_opts(cfg.CONF)
grid_id = cfg.CONF.infoblox.cloud_data_center_id
config.register_infoblox_grid_opts(cfg.CONF, grid_id)

conn = utils.get_connector(credentials)
if not (utils.get_features(conn).create_ea_def):
    LOG.error("WAPI Version '%s' is not supported - Script ABORTED!",
              conn.wapi_version)
    exit(1)

mgr = object_manager.InfobloxObjectManager(conn)
mgr.create_required_ea_definitions(const.REQUIRED_EA_DEFS)


host_ip = getattr(conn, 'host')
if ib_utils.determine_ip_version(host_ip) == 4:
    member = objects.Member.search(conn, ipv4_address=host_ip)
else:
    member = objects.Member.search(conn, ipv6_address=host_ip)

ea_exist = False
if member.extattrs:
    for ea, val in const.GRID_CONFIG_DEFAULTS.items():
        if member.extattrs.get(ea) is not None:
            ea_exist = True
            break

if not ea_exist:
    update_ea = {}
    for ea, val in const.GRID_CONFIG_DEFAULTS.items():
        if not (val is None or val == []):
            update_ea[ea] = val
    member.extattrs = objects.EA(update_ea)
    LOG.info("Adding Extensible Attributes for default Grid Configuration.")
    member.update()
else:
    LOG.info("Extensible Attributes for Grid Configuration already exists.")
