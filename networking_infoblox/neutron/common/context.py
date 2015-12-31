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

from collections import Counter
from oslo_log import log as logging

from neutron.i18n import _LI
from neutron import manager

from infoblox_client import connector

from infoblox_client import object_manager as obj_mgr
from infoblox_client import objects as ib_objects

from networking_infoblox.neutron.common import constants as const
from networking_infoblox.neutron.common import exceptions as exc
from networking_infoblox.neutron.common import ip_allocator
from networking_infoblox.neutron.common import utils
from networking_infoblox.neutron.db import infoblox_db as dbi


LOG = logging.getLogger(__name__)


class InfobloxContext(object):

    def __init__(self, neutron_context, user_id, network, subnet, grid_config,
                 plugin=None, grid_members=None, network_views=None,
                 mapping_conditions=None, ib_network=None):
        self.context = neutron_context
        self.user_id = user_id
        self.plugin = plugin if plugin else manager.NeutronManager.get_plugin()
        self.network = network if network else {}
        self.subnet = subnet if subnet else {}
        self.ib_network = ib_network

        self.grid_config = grid_config
        self.connector = None
        self.ibom = None
        self.ip_alloc = None
        self.dhcp_port_ip_alloc = None

        self.grid_id = self.grid_config.grid_id
        self.mapping = utils.json_to_obj(
            'Mapping',
            {'network_view_id': None,
             'network_view': None,
             'authority_member': None,
             'shared': False,
             'dns_view': None,
             'dhcp_members': [],
             'dns_members': [],
             'ib_dhcp_members': [],
             'ib_nameservers': None})

        self._discovered_grid_members = grid_members
        self._discovered_network_views = network_views
        self._discovered_mapping_conditions = mapping_conditions

        self._update()

    @property
    def discovered_grid_members(self):
        if self._discovered_grid_members is None:
            self._discovered_grid_members = dbi.get_members(
                self.context.session, grid_id=self.grid_id)
        return self._discovered_grid_members

    @property
    def discovered_network_views(self):
        if self._discovered_network_views is None:
            self._discovered_network_views = dbi.get_network_views(
                self.context.session, grid_id=self.grid_id)
        return self._discovered_network_views

    @property
    def discovered_mapping_conditions(self):
        if self._discovered_mapping_conditions is None:
            self._discovered_mapping_conditions = dbi.get_mapping_conditions(
                self.context.session, grid_id=self.grid_id)
        return self._discovered_mapping_conditions

    def reserve_authority_member(self):
        """Reserves the next available authority member.

        Find the next available authority member and reserve it, then
        update mapping metadata and load managers if the authority member is
        CPM.
        :return: None
        """
        session = self.context.session
        network_view = self.mapping.network_view
        authority_member = None

        # get next available member
        if self.grid_config.dhcp_support is False:
            authority_member = dbi.get_next_authority_member_for_ipam(
                session, self.grid_id)
        else:
            # as default, authority member is 'GM'
            gm_member = utils.find_one_in_list('member_type',
                                               const.MEMBER_TYPE_GRID_MASTER,
                                               self.discovered_grid_members)
            authority_member = gm_member

            cp_member = utils.find_one_in_list('member_type',
                                               const.MEMBER_TYPE_CP_MEMBER,
                                               self.discovered_grid_members)
            if self.grid_config.is_cloud_wapi and cp_member:
                authority_member = dbi.get_next_authority_member_for_dhcp(
                    session, self.grid_id)
                if not authority_member:
                    # if no CPM available, use GM
                    authority_member = gm_member

        if not authority_member:
            raise exc.InfobloxCannotReserveAuthorityMember(
                network_view=network_view)

        # create network view mapping and update mapping
        db_network_view = dbi.add_network_view(session,
                                               network_view,
                                               self.grid_id,
                                               authority_member.member_id,
                                               False)
        self.mapping.network_view_id = db_network_view.id
        self.mapping.authority_member = authority_member
        self.mapping.dns_view = self._get_dns_view()

        # change connector if authority member is changed.
        if (self.connector.host not in
                [self.mapping.authority_member.member_ip,
                 self.mapping.authority_member.member_ipv6]):
            self._load_managers()

    def reserve_service_members(self, ib_network=None):
        """Reserve DHCP and DNS service members.

        For the predefined network, dhcp member(s) may be assigned.
        If assigned, then we need to get them from ib_network.members.
        For dns member(s), ib_network.options may contain them.
        If no dhcp member is assigned, then we will pick an available member.
        If no dns member is assigned, the dhcp member will serve dns as well.

        If network is not predefined, we need to assign service members.
        If the authority member is CPM, dhcp/dns members are the same as
        the authority member.
        If the authority member is GM, we need to pick an available dhcp
        member. For simplicity, we will use the dhcp member to serve dns as
        well. More detailed reason for such dns member assignment logic is
        explained below.

        For a host record, a primary dns member must be the same as dhcp member
        because both dhcp and dns record must be created under the same parent
        which is the network view. To simplify dns member assignment logic, we
        will always pick the dns member to be the same as dhcp member.
        Only exception to this would be the predefined networks that are
        created from NIOS side.
        """
        if self.grid_config.dhcp_support is False:
            return

        if self.mapping.authority_member is None:
            raise exc.InfobloxAuthorityMemberNotReserved(
                network_view=self.mapping.network_view)

        session = self.context.session
        dhcp_members = []
        dns_members = []
        nameservers = []

        cidr = self.subnet.get('cidr')
        user_nameservers = self.subnet.get('dns_nameservers', [])
        ip_version = self.subnet.get('ip_version')

        if ib_network is None:
            # service member assignment for a new network
            if (self.mapping.authority_member.member_type ==
                    const.MEMBER_TYPE_CP_MEMBER):
                # for CPM, dhcp member is always the authority member.
                dhcp_member = self.mapping.authority_member
            else:
                # for GM,
                # check if a network view is already serving dhcp.
                #   if true, then use the same dhcp member.
                #   if false, see if gm itself is serving dhcp for other
                #   network view.
                #     if true, then try to get the next available dhcp member.
                #     if false, use gm for dhcp
                dhcp_service_members = dbi.get_service_members(
                    session,
                    network_view_id=self.mapping.network_view_id,
                    service=const.SERVICE_TYPE_DHCP)
                if dhcp_service_members:
                    dhcp_member = utils.find_one_in_list(
                        'member_id',
                        dhcp_service_members[0].member_id,
                        self.discovered_grid_members)
                else:
                    dhcp_service_members = dbi.get_service_members(
                        session,
                        member_id=self.mapping.authority_member.member_id,
                        service=const.SERVICE_TYPE_DHCP)
                    if dhcp_service_members:
                        # authority is GM, a dhcp member needs to be selected.
                        dhcp_member = dbi.get_next_dhcp_member(session,
                                                               self.grid_id)
                        if not dhcp_member:
                            raise exc.InfobloxDHCPMemberNotReserved(
                                network_view=self.mapping.network_view,
                                cidr=cidr)
                    else:
                        dhcp_member = self.mapping.authority_member

            dhcp_members = [dhcp_member]
            dns_members = dhcp_members
            nameservers = utils.get_nameservers(user_nameservers,
                                                dns_members,
                                                ip_version)
        else:
            # service member assignment for the predefined network
            # - first set dhcp servers option
            dhcp_members = self._get_dhcp_members(ib_network)
            if not dhcp_members:
                dhcp_member = dbi.get_next_dhcp_member(session, self.grid_id)
                if not dhcp_member:
                    raise exc.InfobloxDHCPMemberNotReserved(
                        network_view=self.mapping.network_view, cidr=cidr)
                dhcp_members = [dhcp_member]

                # assign dncp member
                ib_network.members = [ib_objects.AnyMember(
                    _struct='dhcpmember',
                    name=dhcp_member.member_name)]

            # - then set dns servers option
            dns_members = self._get_dns_members(ib_network)
            if not dns_members:
                # for CPM as authority member, only one dhcp member can be
                # assigned and dns member needs to be the same as dhcp member
                # for host record.
                # for GM as authority member, multiple dhcp members can be
                # assigned but the first dhcp member will serve as the grid
                # primary and the rest will serve as the grid secondaries.
                dns_members = dhcp_members

            nameservers = utils.get_nameservers(user_nameservers,
                                                dns_members,
                                                ip_version)
            nameservers_option_val = ','.join(nameservers)

            opt_dns = [opt for opt in ib_network.options
                       if opt.name == 'domain-name-servers']
            if not opt_dns:
                ib_network.options.append(
                    ib_objects.DhcpOption(name='domain-name-servers',
                                          value=nameservers_option_val))
            else:
                opt_dns[0].value = nameservers_option_val

            # - lastly set routers option
            gateway_ip_str = str(self.subnet.get('gateway_ip'))
            opt_routers = [opt for opt in ib_network.options
                           if opt.name == 'routers']
            if not opt_routers:
                ib_network.options.append(
                    ib_objects.DhcpOption(name='routers',
                                          value=gateway_ip_str))
            else:
                router_ips = opt_routers[0].value.split(',')
                router_ips_all = [gateway_ip_str] + [ip for ip in router_ips
                                                     if ip != gateway_ip_str]
                opt_routers[0].value = ','.join(router_ips_all)

        ib_dhcp_members = []
        for m in dhcp_members:
            ib_dhcp_members.append(ib_objects.AnyMember(_struct='dhcpmember',
                                                        name=m.member_name))

        self.mapping.dhcp_members = dhcp_members
        self.mapping.dns_members = dns_members
        self.mapping.ib_dhcp_members = ib_dhcp_members
        self.mapping.ib_nameservers = nameservers

        self._register_services()

    def get_dns_members(self):
        """Gets the primary and secondary DNS members that serve DNS.

        DNS has primary DNS member(s) and secondary DNS member(s). A primary
        DNS member serves both WAPI and DNS protocol so a GM or CP member can
        be served as primary. A REGULAR member is used as the primary then
        only DNS protocol is served. A secondary DNS member serves only
        DNS protocol.

        For a host record, a primary DNS member must be the same as DHCP member
        because both DHCP and DNS record writes require that they are under the
        same parent which is the network view. Secondary DNS member can be any
        members as long as they are not listed as a primary DNS member since
        any member can serve DNS protocols.

        DHCP and DNS member assignments are performed by
        reserve_service_members already.

        Here we just need to pick the first member from mapping dns members
        as the primary and the rest as the secondary if multiple dns members
        are assigned. If only one dns member is assigned, then no secondary
        dns server.
        """
        if self.mapping.authority_member is None:
            raise exc.InfobloxAuthorityMemberNotReserved(
                network_view=self.mapping.network_view)

        if self.grid_config.dhcp_support and not self.mapping.dns_members:
            raise exc.InfobloxDNSMemberNotReserved(
                network_view=self.mapping.network_view,
                cidr=self.subnet.get('cidr'))

        primary_members = None
        secondary_members = None

        if self.grid_config.dhcp_support is False:
            member_name = self.mapping.authority_member.member_name
            primary_members = [ib_objects.AnyMember(_struct='memberserver',
                                                    name=member_name)]
        else:
            member_name = self.mapping.dns_members[0].member_name
            primary_members = [ib_objects.AnyMember(_struct='memberserver',
                                                    name=member_name)]
            if len(self.mapping.dns_members) > 1:
                secondary_members = []
                secondary_dns_members = self.mapping.dns_members[1:]
                for m in secondary_dns_members:
                    secondary_members.append(
                        ib_objects.AnyMember(_struct='memberserver',
                                             name=m.member_name))

        return primary_members, secondary_members

    def _get_dhcp_members(self, ib_network):
        dhcp_members = []
        member_ips = utils.get_dhcp_member_ips(ib_network)
        for member_ip in member_ips:
            dhcp_member = utils.find_in_list_by_value(
                member_ip, self.discovered_grid_members)
            if not dhcp_member:
                raise exc.InfobloxCannotFindMember(member=member_ip)
            dhcp_members.append(dhcp_member)
        return dhcp_members

    def _get_dns_members(self, ib_network):
        # multiple dns members can be assigned to a network
        dns_members = []
        member_ips = utils.get_dns_member_ips(ib_network)
        for member_ip in member_ips:
            dns_member = utils.find_in_list_by_value(
                member_ip, self.discovered_grid_members)
            if not dns_member:
                raise exc.InfobloxCannotFindMember(member=member_ip)
            dns_members.append(dns_member)
        return dns_members

    def _register_services(self):
        session = self.context.session

        service = const.SERVICE_TYPE_DHCP
        for member in self.mapping.dhcp_members:
            service_members = dbi.get_service_members(
                session,
                network_view_id=self.mapping.network_view_id,
                member_id=member.member_id,
                grid_id=self.grid_id,
                service=service)
            if not service_members:
                dbi.add_service_member(session, self.mapping.network_view_id,
                                       member.member_id, service)

        service = const.SERVICE_TYPE_DNS
        for member in self.mapping.dns_members:
            service_members = dbi.get_service_members(
                session,
                network_view_id=self.mapping.network_view_id,
                member_id=member.member_id,
                grid_id=self.grid_id,
                service=service)
            if not service_members:
                dbi.add_service_member(session, self.mapping.network_view_id,
                                       member.member_id, service)

    def _update(self):
        """Finds mapping and load managers that can interact with NIOS grid."""
        if not self.network and self.subnet:
            network_id = self.subnet.get('network_id')
            if not network_id:
                # update_subnet does not pass network_id
                db_subnet = dbi.get_subnet_by_id(self.context.session,
                                                 self.subnet['id'])
                network_id = db_subnet.network_id
                self.subnet['network_id'] = network_id
            self.network = self.plugin.get_network(self.context, network_id)

        self.tenant_id = (self.network.get('tenant_id') or
                          self.subnet.get('tenant_id') or
                          self.context.tenant_id)
        self.tenant_name = self._get_tenant_name()

        if self.network:
            if self.subnet:
                self._find_mapping()

        self._load_managers()

    def _load_managers(self):
        self.connector = self._get_connector()
        self.ibom = obj_mgr.InfobloxObjectManager(self.connector)
        self.ip_alloc = self._get_ip_allocator()
        self.dhcp_port_ip_alloc = self._get_ip_allocator(True)

    def _get_ip_allocator(self, for_dhcp_port=False):
        options = dict()
        if (for_dhcp_port or self.grid_config.ip_allocation_strategy ==
                const.IP_ALLOCATION_STRATEGY_HOST_RECORD):
            options['use_host_record'] = True
            if for_dhcp_port:
                options['configure_for_dhcp'] = False
        else:
            options['use_host_record'] = False
            options['dns_record_binding_types'] = (
                self.grid_config.dns_record_binding_types)
            options['dns_record_unbinding_types'] = (
                self.grid_config.dns_record_unbinding_types)
            options['dns_record_removable_types'] = (
                self.grid_config.dns_record_removable_types)
        return ip_allocator.IPAllocator(self.ibom, options)

    def _get_connector(self):
        if self.grid_config.is_cloud_wapi is False:
            return self.grid_config.gm_connector

        # if mapping network view does not exist yet, connect to GM
        if self.mapping.network_view_id is None:
            return self.grid_config.gm_connector

        # use gm_connector in the following cases:
        # 1. authority member is not set
        # 2. authority member type is GM
        # 3. authority member status is OFF
        if (self.mapping.authority_member is None or
                self.mapping.authority_member.member_type ==
                const.MEMBER_TYPE_GRID_MASTER or
                self.mapping.authority_member.member_status !=
                const.MEMBER_STATUS_ON):
            return self.grid_config.gm_connector

        cpm_member_ip = (self.mapping.authority_member.member_ip
                         if self.mapping.authority_member.member_ip
                         else self.mapping.authority_member.member_ipv6)

        grid_connection = self.grid_config.get_grid_connection()
        wapi_user = grid_connection['admin_user'].get('name')
        wapi_pwd = grid_connection['admin_user'].get('password')
        opts = {
            'host': cpm_member_ip,
            'wapi_version': grid_connection['wapi_version'],
            'username': wapi_user,
            'password': wapi_pwd,
            'ssl_verify': grid_connection['ssl_verify'],
            'log_api_calls_as_info': True,
            'http_pool_connections':
                grid_connection['http_pool_connections'],
            'http_pool_maxsize': grid_connection['http_pool_maxsize'],
            'http_request_timeout': grid_connection['http_request_timeout']
        }
        # Silent ssl warnings, if certificate verification is not enabled
        if not opts['ssl_verify']:
            opts['silent_ssl_warnings'] = True
        return connector.Connector(opts)

    def _get_tenant_name(self):
        if self.context.tenant_name:
            return self.context.tenant_name

        session = self.context.session
        db_tenant = dbi.get_tenant(session, self.tenant_id)
        if db_tenant:
            return db_tenant.tenant_name
        return None

    def _get_address_scope(self, subnetpool_id):
        session = self.context.session
        address_scope_id = None
        address_scope_name = None

        db_address_scope = dbi.get_address_scope_by_subnetpool_id(
            session, subnetpool_id)
        if db_address_scope:
            address_scope_id = db_address_scope.id
            address_scope_name = db_address_scope.name

        return address_scope_id, address_scope_name

    def _find_mapping(self):
        session = self.context.session
        netview_id = None
        netview_name = None
        netview_shared = False

        # First check if mapping already exists
        network_id = self.subnet.get('network_id')
        subnet_id = self.subnet.get('id')
        netview_mapping = dbi.get_network_view_mappings(
            session, network_id=network_id, subnet_id=subnet_id)
        if netview_mapping:
            netview_id = netview_mapping[0].network_view_id
            netview_row = utils.find_one_in_list(
                'id', netview_id, self.discovered_network_views)
            self.mapping.network_view_id = netview_id
            self.mapping.network_view = netview_row.network_view
            self.mapping.authority_member = self._get_authority_member(
                netview_row.authority_member_id)
            self.mapping.shared = netview_row.shared
            self.mapping.dns_view = self._get_dns_view()
            self._update_service_member_mapping()
            LOG.info(_LI("Network view %(netview)s mapping found for "
                         "network %(network)s and subnet %(subnet)s"),
                     dict(netview=netview_row.network_view, network=network_id,
                          subnet=subnet_id))
            return

        # No mapping so find mapping
        mapping_attrs = self._get_mapping_attributes()
        matching_netviews = []

        # find mapping matches on common cases
        mapping_filters = self._get_mapping_filters(mapping_attrs)
        for mf in mapping_filters:
            if mf.values()[0] is None:
                continue
            matches = utils.find_in_list_by_condition(
                mf, self.discovered_mapping_conditions)
            if matches:
                netview_ids = [m.network_view_id for m in matches]
                matching_netviews += netview_ids

        # find network view id and name pair
        if matching_netviews:
            # get most matched network view id
            netview_id = Counter(matching_netviews).most_common(1)[0][0]
            netview_row = utils.find_one_in_list('id', netview_id,
                                                 self.discovered_network_views)
            netview_name = netview_row.network_view
            netview_shared = netview_row.shared
        else:
            # no matching found; use default network view scope
            netview_scope = self.grid_config.default_network_view_scope
            netview_name = self._get_network_view_by_scope(netview_scope,
                                                           mapping_attrs)
            netview_row = utils.find_one_in_list('network_view', netview_name,
                                                 self.discovered_network_views)
            if netview_row:
                netview_id = netview_row.id
                netview_shared = netview_row.shared

        self.mapping.network_view_id = netview_id
        self.mapping.network_view = netview_name
        if self.mapping.network_view_id:
            self.mapping.authority_member = self._get_authority_member()
            self.mapping.shared = netview_shared
        self.mapping.dns_view = self._get_dns_view()

    def _get_authority_member(self, authority_member_id=None):
        if authority_member_id is None:
            netview_row = utils.find_one_in_list('id',
                                                 self.mapping.network_view_id,
                                                 self.discovered_network_views)
            authority_member_id = netview_row.authority_member_id
        member = utils.find_one_in_list('member_id',
                                        authority_member_id,
                                        self.discovered_grid_members)
        return member

    def _get_mapping_attributes(self):
        subnetpool_id = self.subnet.get('subnetpool_id')
        address_scope_id, address_scope_name = self._get_address_scope(
            subnetpool_id)
        return {'subnet_id': self.subnet.get('id'),
                'subnet_name': self.subnet.get('name'),
                'subnet_cidr': self.subnet.get('cidr'),
                'subnetpool_id': self.subnet.get('subnetpool_id'),
                'network_id': self.network.get('id'),
                'network_name': self.network.get('name'),
                'tenant_id': self.tenant_id,
                'tenant_name': self.tenant_name,
                'address_scope_id': address_scope_id,
                'address_scope_name': address_scope_name}

    @staticmethod
    def _get_mapping_filters(attrs):
        mappings = {
            'address_scope_name': const.EA_MAPPING_ADDRESS_SCOPE_NAME,
            'address_scope_id': const.EA_MAPPING_ADDRESS_SCOPE_ID,
            'tenant_name': const.EA_MAPPING_TENANT_NAME,
            'tenant_id': const.EA_MAPPING_TENANT_ID,
            'network_name': const.EA_MAPPING_NETWORK_NAME,
            'network_id': const.EA_MAPPING_NETWORK_ID,
            'subnet_id': const.EA_MAPPING_SUBNET_ID,
            'subnet_cidr': const.EA_MAPPING_SUBNET_CIDR}
        return [{const.MAPPING_CONDITION_KEY_NAME: mappings[field],
                 const.MAPPING_CONDITION_VALUE_NAME: attrs[field]}
                for field in mappings]

    def _get_network_view_by_scope(self, netview_scope, neutron_objs):
        netview_name = 'default'

        if netview_scope == const.NETWORK_VIEW_SCOPE_SINGLE:
            netview_name = self.grid_config.default_network_view
        else:
            object_id = None
            object_name = None

            if netview_scope == const.NETWORK_VIEW_SCOPE_SUBNET:
                object_id = neutron_objs['subnet_id']
                object_name = neutron_objs['subnet_name']
            elif netview_scope == const.NETWORK_VIEW_SCOPE_NETWORK:
                object_id = neutron_objs['network_id']
                object_name = neutron_objs['network_name']
            elif netview_scope == const.NETWORK_VIEW_SCOPE_TENANT:
                object_id = neutron_objs['tenant_id']
                object_name = neutron_objs['tenant_name']
            elif netview_scope == const.NETWORK_VIEW_SCOPE_ADDRESS_SCOPE:
                object_id = neutron_objs['address_scope_id']
                object_name = neutron_objs['address_scope_name']

            if object_id:
                netview_name = utils.generate_network_view_name(object_id,
                                                                object_name)
        return netview_name

    def _get_dns_view(self):
        """Return dns view name.

        The following matrix describes all the dns view naming rule.
        | Network View Name | Grid Config DNS View Name | Final DNS View Name |
        | default           | default                   | default             |
        | default           | test_view                 | test_view           |
        | net_view_1        | default                   | default.net_view_1  |
        | net_view_2        | dns_view_2                | dns_view_2          |
        """
        if (self.grid_config.dns_view == const.DEFAULT_DNS_VIEW and
                self.mapping.network_view != const.DEFAULT_NETWORK_VIEW):
            return '.'.join(
                [self.grid_config.dns_view, self.mapping.network_view])
        return self.grid_config.dns_view

    def _update_service_member_mapping(self):
        if not self.ib_network:
            return

        # dhcp members
        dhcp_members = self._get_dhcp_members(self.ib_network)
        ib_dhcp_members = []
        for m in dhcp_members:
            ib_dhcp_members.append(ib_objects.AnyMember(_struct='dhcpmember',
                                                        name=m.member_name))

        # dns members
        dns_members = self._get_dns_members(self.ib_network)
        nameservers = utils.get_nameservers(
            self.subnet.get('dns_nameservers', []),
            dns_members,
            self.subnet.get('ip_version'))

        self.mapping.dhcp_members = dhcp_members
        self.mapping.dns_members = dns_members
        self.mapping.ib_dhcp_members = ib_dhcp_members
        self.mapping.ib_nameservers = nameservers
