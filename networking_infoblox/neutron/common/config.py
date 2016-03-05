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

from oslo_config import cfg


ipam_opts = [
    cfg.IntOpt('cloud_data_center_id',
               default=0,
               help=_("ID used for selecting a particular grid from one or "
                      "more grids to serve networks in Infoblox backend.")),
    cfg.IntOpt('ipam_agent_workers',
               default=1,
               help=_("Number of Infoblox IPAM agent workers to run"))
]

data_center_opts = [
    cfg.StrOpt('data_center_name',
               default='',
               help=_('The name of data center to identify.')),
    cfg.StrOpt('grid_master_host',
               default='',
               help=_('Host IP or name of the grid master.')),
    cfg.StrOpt('grid_master_name',
               default='',
               help=_('Name of the grid master.')),
    cfg.StrOpt('admin_user_name',
               default='',
               help=_("Admin user name to access the grid master or "
                      "cloud platform appliance.")),
    cfg.StrOpt('admin_password',
               default='', secret=True,
               help=_("Admin user password to access the grid master or "
                      "cloud platform appliance.")),
    cfg.StrOpt('wapi_version',
               default='',
               help=_("WAPI (Web API) version.")),
    cfg.StrOpt('ssl_verify',
               default='False',
               help=_("Ensure whether WAPI requests sent over HTTPS require "
                      "SSL verification.")),
    cfg.IntOpt('http_pool_connections',
               default=100,
               help=_("HTTP pool connection.")),
    cfg.IntOpt('http_pool_maxsize',
               default=100,
               help=_("HTTP pool max size.")),
    cfg.IntOpt('http_request_timeout',
               default=120,
               help=_("HTTP request timeout.")),
    cfg.IntOpt('wapi_max_results',
               default=-1000,
               help=_("Maximum number of objects to be returned. If set to a "
                      "negative number the appliance will return an error "
                      "when the number of returned objects would exceed the "
                      "setting. If this is set to a positive number, the "
                      "results will be truncated when necessary."))
]

CONF = cfg.CONF


def register_infoblox_ipam_opts(conf):
    conf.register_group(cfg.OptGroup(
        name='infoblox',
        title="Configuration for Infoblox IPAM Driver"))
    conf.register_opts(ipam_opts, group='infoblox')


def register_infoblox_grid_opts(conf, data_center_id):
    data_center = 'infoblox-dc:%s' % data_center_id
    conf.register_group(cfg.OptGroup(
        name=data_center,
        title="Configuration for Infoblox data center %s" % data_center_id))
    conf.register_opts(data_center_opts, group=data_center)


def get_infoblox_grid_opts(data_center_id):
    grid_info = dict()
    data_center = 'infoblox-dc:%s' % data_center_id
    for opt in data_center_opts:
        grid_info[opt.name] = CONF[data_center][opt.name]
    return grid_info

register_infoblox_ipam_opts(cfg.CONF)
register_infoblox_grid_opts(cfg.CONF, cfg.CONF.infoblox.cloud_data_center_id)
