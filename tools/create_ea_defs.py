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
import os
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

ENV_SUPERUSER_USERNAME = 'NETWORKING_INFOBLOX_SUPERUSER_USERNAME'
ENV_SUPERUSER_PASSWORD = 'NETWORKING_INFOBLOX_SUPERUSER_PASSWORD'

LOG = logging.getLogger(__name__)

cli_opts = [
    cfg.BoolOpt('script',
                short='s',
                default=False,
                help='scripting mode'),
    cfg.StrOpt('username',
               short='u',
               help='username of superuser'),
    cfg.StrOpt('password',
               short='p',
               help='password of superuser')
]
cfg.CONF.register_cli_opts(cli_opts)
cfg.CONF(args=sys.argv[1:])

credentials = None
# User command line arguments if specified
if cfg.CONF.username and cfg.CONF.password:
    credentials = {'username': cfg.CONF.username,
                   'password': cfg.CONF.password}

# Use environment variable if found
if not credentials:
    if (ENV_SUPERUSER_USERNAME in os.environ and
            ENV_SUPERUSER_PASSWORD in os.environ):
        username = os.environ[ENV_SUPERUSER_USERNAME]
        password = os.environ[ENV_SUPERUSER_PASSWORD]
        if username and password:
            credentials = {'username': username, 'password': password}

if not credentials and not cfg.CONF.script:
    print("\n\n")
    print("In order to create Extensible Attribute definitions,")
    print("superuser privilege is required.\n")
    print("If the preconfigured credentials already has superuser privilege,")
    print("just hit <ENTER> when prompted for user name.\n")
    print("Otherwise, please enter user name and password of a user that "
          "has superuser privilege.\n")
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
ea_defs_created = mgr.create_required_ea_definitions(const.REQUIRED_EA_DEFS)
LOG.info("The following EA Definitions have been created: '%s'" %
         [ea_def['name'] for ea_def in ea_defs_created])

host_ip = getattr(conn, 'host')
if ib_utils.determine_ip_version(host_ip) == 4:
    member = objects.Member.search(conn, ipv4_address=host_ip)
else:
    member = objects.Member.search(conn, ipv6_address=host_ip)

if member is None:
    LOG.error("Cannot retrieve member information at host_ip='%s'" % host_ip)
    exit(1)

ea_set = {}
if member.extattrs is None:
    member.extattrs = objects.EA({})
for ea, val in const.GRID_CONFIG_DEFAULTS.items():
    if (member.extattrs.get(ea) is None and
            not (val is None or val == [])):
        ea_set[ea] = val
        member.extattrs.set(ea, val)

if ea_set:
    LOG.info("Adding the following EA values to Grid Member: '%s'" % ea_set)
    member.update()
