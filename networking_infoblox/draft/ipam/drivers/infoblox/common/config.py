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
    name='ipam_driver:infoblox',
    title="Configuration for Infoblox IPAM Driver"))

OPTS = [
    # NIOS grid members and member mapping
    cfg.StrOpt('condition_config',
               default=None,
               help=_("Path to conditional config file")),
    cfg.StrOpt('member_config',
               default=None,
               help=_("Path to grid members config file.")),
    # IPAM
    cfg.BoolOpt('allow_admin_network_deletion',
                default=False,
                help=_("Allow admin network which is global, "
                       "external, or shared to be deleted")),
    cfg.BoolOpt('use_host_records_for_ip_allocation',
                default=True,
                help=_("Use host records for IP allocation. "
                       "If False then Fixed IP + A + PTR record "
                       "are used.")),
    cfg.BoolOpt('use_dhcp_for_ip_allocation_record',
                default=True,
                help=_("Used to set 'configure_for_dhcp' option to enable "
                       " or disable dhcp for host or fixed record")),
    # DNS
    cfg.ListOpt('bind_dns_records_to_fixed_address',
                default=[],
                help=_("List of DNS records to bind to "
                       "Fixed Address during create_port")),
    cfg.ListOpt('unbind_dns_records_from_fixed_address',
                default=[],
                help=_("List of DNS records to unbind from "
                       "Fixed Address during delete_port. "
                       "This is typically the same list as "
                       "that for "
                       "bind_resource_records_to_fixedaddress")),
    cfg.ListOpt('delete_dns_records_associated_with_fixed_address',
                default=[],
                help=_("List of associated DNS records to delete "
                       "when a Fixed Address is deleted. This is "
                       "typically a list of DNS records created "
                       "independent of the Infoblox Openstack "
                       "Adaptor (IOA)")),
    # RELAY
    cfg.StrOpt('dhcp_relay_management_network_view',
               default="default",
               help=_("NIOS network view to be used for DHCP inside "
                      "management network")),
    cfg.StrOpt('dhcp_relay_management_network',
               default=None,
               help=_("CIDR for the management network served by "
                      "Infoblox DHCP member"))
]

cfg.CONF.register_opts(OPTS, group='ipam_driver:infoblox')

CONF = cfg.CONF
CONF_IPAM = CONF['ipam_driver:infoblox']
