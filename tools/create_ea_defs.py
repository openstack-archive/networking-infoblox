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


cfg.CONF(args=sys.argv[1:], default_config_files=['/etc/neutron/neutron.conf'])
common_config.setup_logging()
config.register_infoblox_ipam_opts(cfg.CONF)
grid_id = cfg.CONF.infoblox.cloud_data_center_id
config.register_infoblox_grid_opts(cfg.CONF, grid_id)

grid_opts = config.get_infoblox_grid_opts(grid_id)
wapi_version = grid_opts['wapi_version']
if not (utils.get_features(wapi_version).create_ea_def):
    LOG.error("WAPI Version '%s' is not supported - Script ABORTED!")
    exit(1)
conn = utils.get_connector()

mgr = object_manager.InfobloxObjectManager(conn)
mgr.create_required_ea_definitions(const.REQUIRED_EA_DEFS)
