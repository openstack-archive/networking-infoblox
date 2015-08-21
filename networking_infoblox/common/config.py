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
    cfg.StrOpt('network_view_scope',
               default='single',
               help=_("Network view scope that determines where neutron "
                      "subnets should belong to in NIOS. A valid scope is "
                      "single, address_scope, tenant, or network.")),
    cfg.StrOpt('default_network_view',
               default='default',
               help=_("Name of a network view to use when "
                      "network_view_scope is set to 'single' or no mapping "
                      "is found.")),
    cfg.StrOpt('default_host_name_pattern',
               default='host-{ip_address}',
               help=_("Pattern to generate a DNS record.")),
    cfg.StrOpt('default_domain_name_pattern',
               default='{subnet_id}.cloud.global.com',
               help=_("Pattern to generate a zone name.")),
    cfg.StrOpt('default_ns_group',
               help=_("Name of Name server group to use for all DNS zones.")),
    cfg.IntOpt('cloud_data_center_id',
               help=_("ID used for selecting a particular grid from one or "
                      "more grids to serve networks in Infoblox backend.")),
    cfg.BoolOpt('allow_admin_network_deletion',
                default=False,
                help=_("Allow admin network which is global, "
                       "external, or shared to be deleted.")),
    cfg.BoolOpt('use_host_records_for_ip_allocation',
                default=True,
                help=_("Use host records for IP allocation. "                
                       "If False, then DNS records associated with a fixed "
                       "address are controlled by the following configs: "
                       "bind_dns_records_to_fixed_address, "
                       "unbind_dns_records_from_fixed_address, "
                       "delete_dns_records_associated_with_fixed_address.")),
    cfg.ListOpt('bind_dns_records_to_fixed_address',
                default=[],
                help=_("List of DNS records to generate and bind "
                       "to a fixed address during IP allocation. "
                       "Supported DNS record types are record:a, "
                       "record:aaaa, and record:ptr")),
    cfg.ListOpt('unbind_dns_records_from_fixed_address',
                default=[],
                help=_("List of DNS records to unbind from "
                       "a fixed address during IP deallocation. "
                       "Supported DNS record types are record:a, "
                       "record:aaaa, and record:ptr")),
    cfg.ListOpt('delete_dns_records_associated_with_fixed_address',
                default=[],
                help=_("List of associated DNS records to delete "
                       "when a fixed address is deleted. This is "
                       "typically a list of DNS records created "
                       "independent of the Infoblox Openstack "
                       "Adaptor (IOA). Supported DNS record types are "
                       "record:a, record:aaaa, record:ptr, record:txt, and "
                       "record:cname."))
]

cfg.CONF.register_opts(ipam_opts, group='infoblox')
CONF = cfg.CONF
CONF_IPAM = CONF['infoblox']


DATA_CENTER_SECTION = 'infoblox-dc:%s' % CONF_IPAM.cloud_data_center_id

dc_opts = [
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
               help=_("WAPI version.")),
    cfg.BoolOpt('wapi_ssl_verify',
                default=False,
                help=_("Ensure whether WAPI requests require SSL "
                       "verification.")),
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
