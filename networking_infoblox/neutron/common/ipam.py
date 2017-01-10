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

import netaddr
from neutron_lib import constants as n_const
from oslo_log import log as logging
from oslo_utils import uuidutils

from neutron.ipam import exceptions as ipam_exc
from neutron.ipam import utils as ipam_utils

from infoblox_client import objects as ib_objects

from networking_infoblox._i18n import _LI
from networking_infoblox.neutron.common import constants as const
from networking_infoblox.neutron.common import context
from networking_infoblox.neutron.common import dns
from networking_infoblox.neutron.common import ea_manager as eam
from networking_infoblox.neutron.common import exceptions as exc
from networking_infoblox.neutron.common import pattern
from networking_infoblox.neutron.common import utils
from networking_infoblox.neutron.db import infoblox_db as dbi


LOG = logging.getLogger(__name__)


class IpamSyncController(object):

    def __init__(self, ib_context):
        self.ib_cxt = ib_context
        self.grid_config = self.ib_cxt.grid_config
        self.grid_id = self.grid_config.grid_id
        self.pattern_builder = pattern.PatternBuilder(self.ib_cxt)

    def get_subnet(self):
        return self.ib_cxt.ibom.get_network(self.ib_cxt.mapping.network_view,
                                            self.ib_cxt.subnet.get('cidr'))

    def create_subnet(self, rollback_list):
        """Creates subnet equivalent NIOS objects.

        infoblox context contains subnet dictionary from ipam driver and
        network from db query because only subnet data is passed

        The following NIOS objects are created.
        - network view
        - network
        - ip range
        """
        session = self.ib_cxt.context.session
        network = self.ib_cxt.network
        subnet = self.ib_cxt.subnet

        network_id = network.get('id')
        subnet_id = subnet.get('id')

        network_view_exists = (True if self.ib_cxt.mapping.network_view_id
                               else False)

        if self.ib_cxt.mapping.authority_member is None:
            # after authority member reservation, ib_cxt.mapping is updated and
            # its connector and managers are loaded for the new member.
            self.ib_cxt.reserve_authority_member()

        # create a network view if it does not exist
        if not network_view_exists:
            ib_network_view = self._create_ib_network_view()
            rollback_list.append(ib_network_view)

        ib_network, created = self._create_ib_network()
        if ib_network:
            if created:
                rollback_list.append(ib_network)
            self._create_ib_ip_range(rollback_list)

        # tenats available only with wapi 2.0+
        features = utils.get_features(self.grid_config.wapi_version)
        if features.tenants:
            ib_tenant = ib_objects.Tenant.search(self.ib_cxt.connector,
                                                 id=self.ib_cxt.tenant_id)
            if (ib_tenant and self.ib_cxt.tenant_name and
                    ib_tenant.name != self.ib_cxt.tenant_name):
                ib_tenant.name = self.ib_cxt.tenant_name
                ib_tenant.update()

        # associate the network view to neutron
        dbi.associate_network_view(session,
                                   self.ib_cxt.mapping.network_view_id,
                                   network_id,
                                   subnet_id)
        return ib_network

    def _create_ib_network_view(self):
        session = self.ib_cxt.context.session

        ea_network_view = eam.get_ea_for_network_view(
            self.ib_cxt.tenant_id,
            self.ib_cxt.tenant_name,
            self.grid_id)

        ib_network_view = self.ib_cxt.ibom.create_network_view(
            self.ib_cxt.mapping.network_view,
            ea_network_view)

        network_view_id = utils.get_network_view_id(self.grid_id,
                                                    ib_network_view._ref)
        dbi.update_network_view_id(session,
                                   self.ib_cxt.mapping.network_view_id,
                                   network_view_id)
        self.ib_cxt.mapping.network_view_id = network_view_id

        LOG.info(_LI("Created a network view: %s"), ib_network_view)
        return ib_network_view

    def _create_ib_network(self):
        network_view = self.ib_cxt.mapping.network_view
        network = self.ib_cxt.network
        subnet = self.ib_cxt.subnet
        cidr = subnet.get('cidr')
        gateway_ip = subnet.get('gateway_ip')

        ea_network = eam.get_ea_for_network(self.ib_cxt.user_id,
                                            self.ib_cxt.tenant_id,
                                            self.ib_cxt.tenant_name,
                                            network,
                                            subnet)
        network_template = self.grid_config.network_template

        # check if network already exists
        ib_network = ib_objects.Network.search(self.ib_cxt.connector,
                                               network_view=network_view,
                                               cidr=cidr)
        if ib_network:
            if self.ib_cxt.network_is_shared_or_external:
                self.ib_cxt.reserve_service_members(ib_network)
                self.ib_cxt.ibom.update_network_options(ib_network, ea_network)
                LOG.info("ib network already exists so updated options: %s",
                         ib_network)
                return ib_network, False
            raise exc.InfobloxPrivateSubnetAlreadyExist()

        # network creation using template
        if network_template:
            ib_network = self.ib_cxt.ibom.create_network_from_template(
                self.ib_cxt.mapping.network_view, cidr, network_template,
                ea_network)
            self._register_mapping_member()
            self.ib_cxt.reserve_service_members(ib_network)
            self.ib_cxt.ibom.update_network_options(ib_network, ea_network)
            LOG.info("ib network created from template %s: %s",
                     network_template, ib_network)
            return ib_network, True

        # network creation starts
        self.ib_cxt.reserve_service_members()

        relay_trel_ip = None
        ib_network = self.ib_cxt.ibom.create_network(
            self.ib_cxt.mapping.network_view,
            cidr,
            self.ib_cxt.mapping.ib_nameservers,
            self.ib_cxt.mapping.ib_dhcp_members,
            gateway_ip,
            relay_trel_ip,
            ea_network)
        self._register_mapping_member()
        LOG.info("ib network has been created: %s", ib_network)

        self._restart_services()
        return ib_network, True

    def _get_service_members(self, field='member_id'):
        dhcp_members = [m.get(field) for m in self.ib_cxt.mapping.dhcp_members]
        dns_members = [m.get(field) for m in self.ib_cxt.mapping.dns_members]
        service_member_set = set(dhcp_members + dns_members)
        return list(service_member_set)

    def _restart_services(self):
        if self.grid_config.allow_service_restart is False or (
                self.grid_config.dhcp_support is False and
                self.grid_config.dns_support is False):
            return

        member_names = self._get_service_members('member_name')
        for member_name in member_names:
            ib_member = ib_objects.Member.search(self.ib_cxt.connector,
                                                 host_name=member_name,
                                                 return_fields=['host_name'])
            if ib_member:
                self.ib_cxt.ibom.restart_all_services(ib_member)

    def _register_mapping_member(self):
        session = self.ib_cxt.context.session
        mapping_relation = utils.get_mapping_relation(
            self.ib_cxt.mapping.authority_member.member_type)
        mapping_members = dbi.get_mapping_members(
            session,
            self.ib_cxt.mapping.network_view_id,
            self.ib_cxt.mapping.authority_member.member_id,
            self.grid_id,
            mapping_relation)
        if not mapping_members:
            dbi.add_mapping_member(
                session,
                self.ib_cxt.mapping.network_view_id,
                self.ib_cxt.mapping.authority_member.member_id,
                mapping_relation)

    def _create_ib_ip_range(self, rollback_list):
        subnet = self.ib_cxt.subnet
        cidr = subnet.get('cidr')
        ip_version = subnet.get('ip_version')
        gateway_ip = subnet.get('gateway_ip')
        allocation_pools = subnet.get('allocation_pools')
        if not allocation_pools:
            allocation_pools = ipam_utils.generate_pools(cidr, gateway_ip)
        self._allocate_pools(rollback_list, allocation_pools, cidr,
                             ip_version, True)

    def _allocate_pools(self, rollback_list, pools, cidr, ip_version,
                        check_if_exists=False):
        ea_range = eam.get_ea_for_range(self.ib_cxt.user_id,
                                        self.ib_cxt.tenant_id,
                                        self.ib_cxt.tenant_name,
                                        self.ib_cxt.network)
        is_shared = self.ib_cxt.network_is_shared_or_external

        for pool in pools:
            disable = True

            # db_base_plugin uses netaddr but neutronclient uses dict for
            # ip range
            if isinstance(pool, dict) and pool.get('start'):
                start_ip = pool.get('start')
            else:
                start_ip = netaddr.IPAddress(pool.first, ip_version).format()

            if isinstance(pool, dict) and pool.get('end'):
                end_ip = pool.get('end')
            else:
                end_ip = netaddr.IPAddress(pool.last, ip_version).format()

            if check_if_exists:
                ib_ip_range = ib_objects.IPRange.search(
                    self.ib_cxt.connector,
                    network_view=self.ib_cxt.mapping.network_view,
                    network=cidr,
                    start_addr=start_ip,
                    end_addr=end_ip)
                if ib_ip_range:
                    managed = "Unmanaged"  # Not managed by OpenStack
                    if not is_shared or self._range_is_managed(ib_ip_range):
                        managed = "Managed"  # Managed by OpenStack
                        eas = ib_ip_range.extattrs
                        if eas:
                            ea_dict = ib_ip_range.extattrs.ea_dict
                            ea_dict.update(ea_range.ea_dict)
                            ib_ip_range.extattrs = ib_objects.EA(ea_dict)
                        else:
                            ib_ip_range.extattrs = ea_range
                        ib_ip_range.update()
                    LOG.info("%s ip range already existed: %s" %
                             (managed, ib_ip_range))
                    continue

            ib_ip_range = self.ib_cxt.ibom.create_ip_range(
                self.ib_cxt.mapping.network_view,
                start_ip,
                end_ip,
                cidr,
                disable,
                ea_range)
            LOG.info("ip range has been created: %s", ib_ip_range)
            rollback_list.append(ib_ip_range)

    def update_subnet_allocation_pools(self, rollback_list):
        cidr = self.ib_cxt.subnet.get('cidr')
        ip_version = self.ib_cxt.subnet.get('ip_version')
        allocation_pools = self.ib_cxt.subnet.get('allocation_pools')

        # take care of allocation pools
        ib_pools = ib_objects.IPRange.search_all(
            self.ib_cxt.connector,
            network_view=self.ib_cxt.mapping.network_view,
            network=str(cidr))

        added_pool, removed_pool = self._get_changed_pools(
            ib_pools,
            allocation_pools,
            ip_version)

        is_shared = self.ib_cxt.network_is_shared_or_external
        for pool in removed_pool:
            if not is_shared or self._range_is_managed(pool):
                pool.delete()
            else:
                LOG.warning(("Allocation range %s-%s is not managed by " +
                             "OpenStack and is therefore not removed from " +
                             "Infoblox") % (pool.start_addr, pool.end_addr))

        self._allocate_pools(rollback_list, added_pool, cidr, ip_version)
        self._restart_services()

    def update_subnet_details(self, ib_network):
        ea_network = eam.get_ea_for_network(self.ib_cxt.user_id,
                                            self.ib_cxt.tenant_id,
                                            self.ib_cxt.tenant_name,
                                            self.ib_cxt.network,
                                            self.ib_cxt.subnet)

        nameservers = self.ib_cxt.mapping.ib_nameservers
        if nameservers:
            nameservers_option_val = ','.join(nameservers)
            opt_dns = [opt for opt in ib_network.options
                       if opt.name == 'domain-name-servers']
            if opt_dns:
                opt_dns[0].value = nameservers_option_val
            else:
                ib_network.options.append(
                    ib_objects.DhcpOption(name='domain-name-servers',
                                          value=nameservers_option_val))
        else:
            ib_network.options = [opt for opt in ib_network.options
                                  if opt.name != 'domain-name-servers']

        self.ib_cxt.ibom.update_network_options(ib_network, ea_network)
        self._restart_services()

    @staticmethod
    def _get_changed_pools(ib_pools, pools_from_request, ip_version):
        """Calculates difference between nios and neutron ranges.

        :param nios_pools: list of objects.IPRange returned by NIOS
        :param pools_from_request: list of netaddr.IPRange from subnet request
        :return: tuple with two elements:
            - add_list with netaddr.IPRange objects;
            - remove_list with objects.IPRange objects;
        """
        if pools_from_request is None:
            pools_from_request = []

        ib_pool_map = {'%s-%s' % (pool.start_addr, pool.end_addr): pool
                       for pool in ib_pools}

        request_pool_map = {}
        for pool in pools_from_request:
            first_ip = netaddr.IPAddress(pool.first, ip_version).format()
            last_ip = netaddr.IPAddress(pool.last, ip_version).format()
            pool_str = '%s-%s' % (first_ip, last_ip)
            request_pool_map[pool_str] = pool

        old_pools = set(ib_pool_map.keys())
        new_pools = set(request_pool_map.keys())

        added_pools = new_pools - old_pools
        removed_pools = old_pools - new_pools

        added_list = [request_pool_map[pool] for pool in added_pools]
        removed_list = [ib_pool_map[pool] for pool in removed_pools]
        return added_list, removed_list

    def delete_subnet(self, ib_network=None):
        """Frees up resources taken by the subnet and removes the subnet.

        Resources to be released are
        - DHCP/DNS members are freed if not shared by other subnet(s).
        - Network view mapping is removed.
        - Authority member is not freed up for GM but taken care by the agent
          since it is hard to determine at the subnet scope.
        """
        session = self.ib_cxt.context.session
        subnet = self.ib_cxt.subnet
        network = self.ib_cxt.network
        network_view = self.ib_cxt.mapping.network_view

        network_id = network.get('id')
        subnet_id = subnet.get('id')
        cidr = subnet.get('cidr')

        # subnet id is already gone since community plugin already called
        # subnet delete in db level by the time ipam driver reaches here.
        dbi.dissociate_network_view(session, network_id, subnet_id)

        subnet_deletable = (not self.ib_cxt.network_is_shared_or_external or
                            self.grid_config.admin_network_deletion)
        if subnet_deletable:
            ib_ipv4_networks = ib_objects.NetworkV4.search_all(
                self.ib_cxt.connector, network_view=network_view)
            ib_ipv6_networks = ib_objects.NetworkV6.search_all(
                self.ib_cxt.connector, network_view=network_view)
            is_last_subnet_in_netview = (len(ib_ipv4_networks) +
                                         len(ib_ipv6_networks)) == 1

            self._release_service_members(is_last_subnet_in_netview)

            # delete ib network
            self.ib_cxt.ibom.delete_network(network_view, cidr)

            # if no more network exists, remove network view
            if is_last_subnet_in_netview:
                self._remove_network_view()

            self._restart_services()
        else:
            eam.reset_ea_for_network(ib_network)
            ib_network.update()

            ib_ranges = ib_objects.IPRange.search_all(
                self.ib_cxt.connector,
                network_view=network_view,
                network=cidr)
            for ib_range in ib_ranges:
                eam.reset_ea_for_range(ib_range)
                ib_range.update()

    def _release_service_members(self, is_last_subnet_in_netview):
        """Frees up service members

        For CPM, only one subnet should remain in a given network view
        scope since other subnet(s) could use the same dhcp/dns member.

        For GM, dhcp/dns could be GM itself or another member. it is hard
        to determine whether the same member is used in multiple subnets or
        not since we store service members per network view level only.
        for dhcp/dns members, we can release them when only one subnet remains.
        """
        if self.grid_config.dhcp_support is False:
            return

        session = self.ib_cxt.context.session

        if (self.ib_cxt.mapping.authority_member.member_type ==
                const.MEMBER_TYPE_CP_MEMBER):
            if self._is_member_releasable():
                # release service members
                service_member_ids = self._get_service_members('member_id')
                if service_member_ids:
                    dbi.remove_service_members(
                        session,
                        self.ib_cxt.mapping.network_view_id,
                        service_member_ids)
        else:
            # to release dhcp/dns members, only one subnet should remain in the
            # current network view.
            if is_last_subnet_in_netview:
                dhcp_member_ids = [m.member_id
                                   for m in self.ib_cxt.mapping.dhcp_members]
                for member_id in dhcp_member_ids:
                    dbi.remove_service_member(
                        session,
                        self.ib_cxt.mapping.network_view_id,
                        member_id,
                        const.SERVICE_TYPE_DHCP)

                dns_member_ids = [m.member_id
                                  for m in self.ib_cxt.mapping.dns_members]
                for member_id in dns_member_ids:
                    dbi.remove_service_member(
                        session,
                        self.ib_cxt.mapping.network_view_id,
                        member_id,
                        const.SERVICE_TYPE_DNS)

    def _is_member_releasable(self):
        """Determine if service members can be released."""
        session = self.ib_cxt.context.session

        subnet_id = self.ib_cxt.subnet.get('id')
        network_id = self.ib_cxt.subnet.get('network_id')
        tenant_id = self.ib_cxt.subnet.get('tenant_id')

        netview_scope = self.ib_cxt.grid_config.default_network_view_scope

        if netview_scope == const.NETWORK_VIEW_SCOPE_ADDRESS_SCOPE:
            return dbi.is_last_subnet_in_address_scope(session, subnet_id)
        if netview_scope == const.NETWORK_VIEW_SCOPE_TENANT:
            return dbi.is_last_subnet_in_tenant(session, subnet_id, tenant_id)
        if netview_scope == const.NETWORK_VIEW_SCOPE_NETWORK:
            return dbi.is_last_subnet_in_network(session, subnet_id,
                                                 network_id)
        if netview_scope == const.NETWORK_VIEW_SCOPE_SUBNET:
            return True
        return dbi.is_last_subnet(session, subnet_id)

    def _remove_network_view(self):
        session = self.ib_cxt.context.session
        network_view = self.ib_cxt.mapping.network_view

        if (self.grid_config.default_network_view_scope ==
                const.NETWORK_VIEW_SCOPE_SINGLE and
                network_view == self.grid_config.default_network_view):
            return

        # remove ib network view
        self.ib_cxt.ibom.delete_network_view(network_view)

        # release authority member
        dbi.remove_mapping_member(
            session,
            self.ib_cxt.mapping.network_view,
            self.ib_cxt.mapping.authority_member.member_id)

        # remove network view
        dbi.remove_network_views(session,
                                 [self.ib_cxt.mapping.network_view_id])

    def allocate_specific_ip(self, ip_address, mac, port_id=None,
                             port_tenant_id=None, device_id=None,
                             device_owner=None):
        hostname = uuidutils.generate_uuid()

        port_tenant_name = self.ib_cxt.get_tenant_name(port_tenant_id)
        ea_ip_address = eam.get_ea_for_ip(self.ib_cxt.user_id,
                                          port_tenant_id,
                                          port_tenant_name,
                                          self.ib_cxt.network,
                                          port_id,
                                          device_id,
                                          device_owner)
        dns_view = self.ib_cxt.mapping.dns_view
        zone_auth = self.pattern_builder.get_zone_name(
            is_external=self.ib_cxt.network_is_external)

        ip_alloc = (self.ib_cxt.dhcp_port_ip_alloc
                    if device_owner == n_const.DEVICE_OWNER_DHCP
                    else self.ib_cxt.ip_alloc)

        allocated_ip = ip_alloc.allocate_given_ip(
            self.ib_cxt.mapping.network_view,
            dns_view,
            zone_auth,
            hostname,
            mac,
            ip_address,
            ea_ip_address)
        if allocated_ip:
            LOG.info('IP address allocated on Infoblox NIOS: %s',
                     allocated_ip)
            if device_owner == n_const.DEVICE_OWNER_DHCP:
                self.ib_cxt.update_nameservers(allocated_ip)

        return allocated_ip

    def allocate_ip_from_pool(self, subnet_id, allocation_pools, mac,
                              port_id=None, port_tenant_id=None,
                              device_id=None, device_owner=None):
        hostname = uuidutils.generate_uuid()

        port_tenant_name = self.ib_cxt.get_tenant_name(port_tenant_id)
        ea_ip_address = eam.get_ea_for_ip(self.ib_cxt.user_id,
                                          port_tenant_id,
                                          port_tenant_name,
                                          self.ib_cxt.network,
                                          port_id,
                                          device_id,
                                          device_owner)

        dns_view = self.ib_cxt.mapping.dns_view
        zone_auth = self.pattern_builder.get_zone_name(
            is_external=self.ib_cxt.network_is_external)
        allocated_ip = None

        ip_alloc = (self.ib_cxt.dhcp_port_ip_alloc
                    if device_owner == n_const.DEVICE_OWNER_DHCP
                    else self.ib_cxt.ip_alloc)
        for pool in allocation_pools:
            first_ip = pool['start']
            last_ip = pool['end']
            try:
                allocated_ip = ip_alloc.allocate_ip_from_range(
                    self.ib_cxt.mapping.network_view,
                    dns_view,
                    zone_auth,
                    hostname,
                    mac,
                    first_ip,
                    last_ip,
                    ea_ip_address)
                if allocated_ip:
                    break
            except exc.InfobloxCannotAllocateIp:
                LOG.info("Failed to allocate IP from range (%s-%s)." %
                         (first_ip, last_ip))
                continue

        if allocated_ip:
            LOG.info('IP address allocated on Infoblox NIOS: %s',
                     allocated_ip)
            if device_owner == n_const.DEVICE_OWNER_DHCP:
                self.ib_cxt.update_nameservers(allocated_ip)
        else:
            LOG.info("All IPs from subnet %(subnet_id)s allocated",
                     {'subnet_id': subnet_id})
            raise ipam_exc.IpAddressGenerationFailure(subnet_id=subnet_id)

        return allocated_ip

    def deallocate_ip(self, ip_address):
        dns_view = self.ib_cxt.mapping.dns_view
        self.ib_cxt.ip_alloc.deallocate_ip(self.ib_cxt.mapping.network_view,
                                           dns_view,
                                           ip_address)

    @staticmethod
    def _range_is_managed(ib_range):
        """Determine if an ib_range is managed by OpenStack"""
        return (ib_range and ib_range.extattrs and
                ib_range.extattrs.get(const.EA_CMP_TYPE, "") ==
                const.CLOUD_PLATFORM_NAME)


class IpamAsyncController(object):

    def __init__(self, ib_context):
        self.ib_cxt = ib_context
        self.grid_config = self.ib_cxt.grid_config
        self.grid_id = self.grid_config.grid_id

    def update_network_sync(self, need_new_zones=False):
        """Updates EAs for each subnet that belongs to the updated network."""
        session = self.ib_cxt.context.session
        network = self.ib_cxt.network
        network_id = network.get('id')

        subnets = dbi.get_subnets_by_network_id(session, network_id)
        for subnet in subnets:
            network_view = None
            cidr = subnet.get('cidr')
            subnet_id = subnet.get('id')

            netview_mappings = dbi.get_network_view_mappings(
                session, network_id=network_id, subnet_id=subnet_id)
            if netview_mappings:
                netview_row = utils.find_one_in_list(
                    'id', netview_mappings[0].network_view_id,
                    self.ib_cxt.discovered_network_views)
                network_view = netview_row.network_view

            ib_network = None
            if network_view:
                ib_network = self.ib_cxt.ibom.get_network(network_view, cidr)
                ea_network = eam.get_ea_for_network(self.ib_cxt.user_id,
                                                    self.ib_cxt.tenant_id,
                                                    self.ib_cxt.tenant_name,
                                                    network,
                                                    subnet)
                self.ib_cxt.ibom.update_network_options(ib_network, ea_network)

            if need_new_zones:
                # Need context with ib_network to create zones
                ib_cxt = context.InfobloxContext(
                    self.ib_cxt.context, self.ib_cxt.user_id,
                    network, subnet, self.grid_config,
                    self.ib_cxt.plugin, ib_network=ib_network)
                dns_controller = dns.DnsController(ib_cxt)
                rollback_list = []
                dns_controller.create_dns_zones(rollback_list)
            else:
                self.ib_cxt.subnet = subnet
                dns_controller = dns.DnsController(self.ib_cxt)
                dns_controller.update_dns_zones()

    def update_port_sync(self, port):
        if not port or not port.get('fixed_ips'):
            return

        session = self.ib_cxt.context.session

        for fip in port['fixed_ips']:
            subnet_id = fip['subnet_id']
            ip_address = fip['ip_address']

            netview_mappings = dbi.get_network_view_mappings(
                session,
                network_id=port['network_id'],
                subnet_id=subnet_id)
            if netview_mappings:
                netview_row = utils.find_one_in_list(
                    'id', netview_mappings[0].network_view_id,
                    self.ib_cxt.discovered_network_views)
                network_view = netview_row.network_view

                port_tenant_name = self.ib_cxt.get_tenant_name(
                    port['tenant_id'])
                ea_ip_address = eam.get_ea_for_ip(self.ib_cxt.user_id,
                                                  port['tenant_id'],
                                                  port_tenant_name,
                                                  network_view,
                                                  port['id'],
                                                  port['device_id'],
                                                  port['device_owner'])
                self.ib_cxt.ibom.update_fixed_address_eas(network_view,
                                                          ip_address,
                                                          ea_ip_address)
