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


cfg.CONF.register_group(cfg.OptGroup(
    name='infoblox',
    title="Configuration for Infoblox IPAM Driver"))

ipam_opts = [
    cfg.IntOpt('cloud_data_center_id',
               help=_("ID used for selecting a particular grid from one or "
                      "more grids to serve networks in Infoblox backend."))
]

cfg.CONF.register_opts(ipam_opts, group='infoblox')
CONF = cfg.CONF
CONF_IPAM = CONF['infoblox']


DATA_CENTER_SECTION = 'infoblox-dc:%s' % CONF_IPAM.cloud_data_center_id

dc_opts = [
    cfg.StrOpt('data_center_name ',
               help=_('The name of data center to identify.')),
    cfg.StrOpt('grid_master_host',
               help=_('Host IP or name of the grid master.')),
    cfg.StrOpt('admin_user_name',
               help=_("Admin user name to access grid master.")),
    cfg.StrOpt('admin_password',
               help=_("Admin user password to access grid master.")),
    cfg.StrOpt('cloud_user_name',
               help=_("Cloud user name to access cloud platform members.")),
    cfg.StrOpt('cloud_user_password',
               help=_("Cloud user password to access cloud platform "
                      "members.")),
    cfg.StrOpt('wapi_version',
               help=_("WAPI (Web API) version.")),
    cfg.BoolOpt('ssl_verify',
                default=False,
                help=_("Ensure whether WAPI requests sent over HTTPS require"
                       " SSL verification.")),
    cfg.IntOpt('http_pool_connections',
               default=100,
               help=_("HTTP pool connection.")),
    cfg.IntOpt('http_pool_maxsize',
               default=100,
               help=_("HTTP pool max size.")),
    cfg.IntOpt('http_request_timeout',
               default=120,
               help=_("HTTP request timeout."))
]

cfg.CONF.register_opts(dc_opts, group=DATA_CENTER_SECTION)
CONF_DC = CONF[DATA_CENTER_SECTION]
