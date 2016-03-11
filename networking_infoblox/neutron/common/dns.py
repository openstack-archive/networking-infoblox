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

from oslo_log import log as logging
from oslo_utils import excutils

from neutron.common import constants as n_const

from infoblox_client import exceptions as ibc_exc

from networking_infoblox.neutron.common import ea_manager as eam
from networking_infoblox.neutron.common import pattern
from networking_infoblox.neutron.common import utils
from networking_infoblox.neutron.db import infoblox_db as dbi


LOG = logging.getLogger(__name__)


class DnsController(object):

    def __init__(self, ib_context):
        self.ib_cxt = ib_context
        self.grid_config = self.ib_cxt.grid_config
        self.grid_id = self.grid_config.grid_id
        self.pattern_builder = pattern.PatternBuilder(self.ib_cxt)
        self.dns_zone = self.pattern_builder.get_zone_name()

    def create_dns_zones(self, rollback_list):
        if self.grid_config.dns_support is False:
            return

        ea_zone = eam.get_ea_for_zone(self.ib_cxt.user_id,
                                      self.ib_cxt.tenant_id,
                                      self.ib_cxt.tenant_name,
                                      self.ib_cxt.network)
        cidr = self.ib_cxt.subnet['cidr']
        subnet_name = self.ib_cxt.subnet['name']
        dns_view = self.ib_cxt.mapping.dns_view
        ns_group = self.grid_config.ns_group
        zone_format = "IPV%s" % self.ib_cxt.subnet['ip_version']
        prefix = utils.get_ipv4_network_prefix(cidr, subnet_name)

        grid_primaries, grid_secondaries = self.ib_cxt.get_dns_members()

        if ns_group:
            ib_zone = self.ib_cxt.ibom.create_dns_zone(
                dns_view,
                self.dns_zone,
                ns_group=ns_group,
                extattrs=ea_zone)
            rollback_list.append(ib_zone)
            ib_zone_cidr = self.ib_cxt.ibom.create_dns_zone(
                dns_view,
                cidr,
                prefix=prefix,
                zone_format=zone_format,
                extattrs=ea_zone)
            rollback_list.append(ib_zone_cidr)
        else:
            ib_zone = self.ib_cxt.ibom.create_dns_zone(
                dns_view,
                self.dns_zone,
                grid_primary=grid_primaries,
                grid_secondaries=grid_secondaries,
                extattrs=ea_zone)
            rollback_list.append(ib_zone)
            ib_zone_cidr = self.ib_cxt.ibom.create_dns_zone(
                dns_view,
                cidr,
                grid_primary=grid_primaries,
                prefix=prefix,
                zone_format=zone_format,
                extattrs=ea_zone)
            rollback_list.append(ib_zone_cidr)

    def delete_dns_zones(self, dns_zone=None, ib_network=None):
        if self.grid_config.dns_support is False:
            return

        session = self.ib_cxt.context.session
        dns_view = self.ib_cxt.mapping.dns_view
        cidr = self.ib_cxt.subnet['cidr']
        dns_zone = dns_zone if dns_zone else self.dns_zone

        db_network_views = dbi.get_network_views(
            session,
            network_view_id=self.ib_cxt.mapping.network_view_id,
            participated=True)
        if not db_network_views:
            LOG.info("Network view has been removed so dns zone is already"
                     "removed.")
            return

        zone_removable = (not self.ib_cxt.network_is_shared or
                          self.grid_config.admin_network_deletion)
        if zone_removable:
            # delete forward zone
            if self._is_forward_zone_removable():
                self.ib_cxt.ibom.delete_dns_zone(dns_view, dns_zone)

            # delete reverse zone
            self.ib_cxt.ibom.delete_dns_zone(dns_view, cidr)

        # for external/shared network
        # the zone could be fixed at "cloud.infoblox.com" and so just deleting
        # a network that used that zone causing the EAs to clear on the zone
        # wouldn't be right.

    def _is_forward_zone_removable(self):
        session = self.ib_cxt.context.session
        pattern = self.grid_config.default_domain_name_pattern

        subnet_id = self.ib_cxt.subnet['id']
        network_id = self.ib_cxt.subnet['network_id']
        tenant_id = self.ib_cxt.subnet['tenant_id']

        # check all dynamic patterns from bottom to top hierarchy
        subnet_used = '{subnet_name}' in pattern or '{subnet_id}' in pattern
        if subnet_used:
            return True

        network_used = '{network_name}' in pattern or '{network_id}' in pattern
        if network_used:
            if dbi.is_last_subnet_in_network(session, subnet_id, network_id):
                return True

        tenant_used = '{tenant_name}' in pattern or '{tenant_id}' in pattern
        if tenant_used:
            if dbi.is_last_subnet_in_tenant(session, subnet_id, tenant_id):
                return True

        address_scope_used = ('{address_scope_name}' in pattern or
                              '{address_scope_id}' in pattern)
        if address_scope_used:
            if dbi.is_last_subnet_in_address_scope(session, subnet_id):
                return True

        # now check for static zone
        return dbi.is_last_subnet_in_private_networks(session, subnet_id)

    def bind_names(self, ip_address, instance_name=None, port_id=None,
                   port_tenant_id=None, device_id=None, device_owner=None,
                   is_floating_ip=False):
        if not device_owner:
            return

        tenant_id = port_tenant_id or self.ib_cxt.context.tenant_id
        tenant_name = self.ib_cxt.get_tenant_name(tenant_id)
        ea_ip_address = eam.get_ea_for_ip(self.ib_cxt.user_id,
                                          tenant_id,
                                          tenant_name,
                                          self.ib_cxt.network,
                                          port_id,
                                          device_id,
                                          device_owner,
                                          is_floating_ip,
                                          instance_name)

        ip_alloc = (self.ib_cxt.dhcp_port_ip_alloc
                    if device_owner == n_const.DEVICE_OWNER_DHCP
                    else self.ib_cxt.ip_alloc)
        try:
            self._bind_names(ip_alloc.bind_names, ip_address,
                             instance_name, port_id, port_tenant_id, device_id,
                             device_owner, ea_ip_address)
        except ibc_exc.InfobloxCannotCreateObject:
            with excutils.save_and_reraise_exception():
                self.unbind_names(ip_address, instance_name, port_id,
                                  port_tenant_id, device_id, device_owner)

    def unbind_names(self, ip_address, instance_name=None, port_id=None,
                     port_tenant_id=None, device_id=None, device_owner=None):
        if not device_owner:
            return

        ip_alloc = (self.ib_cxt.dhcp_port_ip_alloc
                    if device_owner == n_const.DEVICE_OWNER_DHCP
                    else self.ib_cxt.ip_alloc)
        self._bind_names(ip_alloc.unbind_names, ip_address,
                         instance_name, port_id, port_tenant_id, device_id,
                         device_owner)

    def _bind_names(self, binding_func, ip_address, instance_name=None,
                    port_id=None, port_tenant_id=None, device_id=None,
                    device_owner=None, ea_ip_address=None):
        network_view = self.ib_cxt.mapping.network_view
        dns_view = self.ib_cxt.mapping.dns_view

        fqdn = self.pattern_builder.get_hostname(ip_address, instance_name,
                                                 port_id, device_owner,
                                                 device_id)

        binding_func(network_view, dns_view, ip_address, fqdn, ea_ip_address)
