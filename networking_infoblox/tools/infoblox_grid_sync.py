#!/usr/bin/env python
# Copyright (c) 2015 Infoblox Inc.
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

from neutron.agent.common import config as agent_conf
from neutron.common import config as common_config
from neutron import context

from networking_infoblox.neutron.common import config
from networking_infoblox.neutron.common import grid


def register_options():
    agent_conf.register_agent_state_opts_helper(cfg.CONF)
    config.register_infoblox_ipam_opts(cfg.CONF)
    config.register_infoblox_grid_opts(cfg.CONF,
                                       cfg.CONF.infoblox.cloud_data_center_id)


def main():
    common_config.init(sys.argv[1:])
    common_config.setup_logging()
    register_options()
    grid.GridManager(context.get_admin_context()).sync(force_sync=True)

if __name__ == "__main__":
    main()
