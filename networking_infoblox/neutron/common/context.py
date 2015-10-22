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

from oslo_log import log as logging

from neutron.i18n import _LI
from neutron import manager

from infoblox_client import connector
from infoblox_client import object_manager as obj_mgr

from networking_infoblox.neutron.common import constants as const
from networking_infoblox.neutron.common import exceptions as exc
from networking_infoblox.neutron.common import ip_allocator
from networking_infoblox.neutron.common import utils
from networking_infoblox.neutron.db import infoblox_db as dbi


LOG = logging.getLogger(__name__)


class InfobloxContext(object):

    def __init__(self, neutron_context, user_id, network, subnet, grid_config,
                 plugin=None, grid_members=None, network_views=None,
                 mapping_conditions=None):
        self.context = neutron_context
        self.user_id = user_id
        self.plugin = plugin if plugin else manager.NeutronManager.get_plugin()
        self.network = network if network else {}
        self.subnet = subnet if subnet else {}

        self.grid_config = grid_config
        self.connector = None
        self.ibom = None
        self.ip_alloc = None

        self.grid_id = self.grid_config.grid_id
        self.mapping = utils.json_to_obj(
            'Mapping',
            {'network_view_id': None,
             'network_view': None,
             'authority_member': None,
             'mapping_scope': None})

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
            authority_member = dbi.get_next_authority_member_for_dhcp(
                session, self.grid_id)

        if not authority_member:
            raise exc.InfobloxCannotReserveAuthorityMember(
                network_view=network_view)

        # create network view mapping and update mapping properties
        db_network_view = dbi.add_network_view(session, network_view,
                                               self.grid_id,
                                               authority_member.member_id)
        self.mapping.network_view_id = db_network_view.id
        self.mapping.authority_member = authority_member

        # change connector if authority member is CPM because currently
        # gm_connector is used
        if authority_member.member_type == const.MEMBER_TYPE_CP_MEMBER:
            self._load_managers()

    def _update(self):
        """Finds mapping and load managers that can interact with NIOS grid."""
        if not self.network and self.subnet:
            network_id = self.subnet.get('network_id')
            self.network = self.plugin.get_network(self.context, network_id)

        if self.network:
            if self.subnet:
                self._find_mapping()
            self._load_managers()

    def _load_managers(self):
        self.connector = self._get_connector()
        self.ibom = obj_mgr.InfobloxObjectManager(self.connector)
        self.ip_alloc = self._get_ip_allocator()

    def _get_ip_allocator(self):
        options = dict()
        if (self.grid_config.ip_allocation_strategy ==
                const.IP_ALLOCATION_STRATEGY_HOST_RECORD):
            options['use_host_record'] = True
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

        grid_connection = self.grid_config.get_grid_connection()
        if grid_connection.get('cloud_user') is None:
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

        cloud_user = grid_connection['cloud_user'].get('name')
        cloud_pwd = grid_connection['cloud_user'].get('password')
        opts = {
            'host': cpm_member_ip,
            'wapi_version': grid_connection['wapi_version'],
            'username': cloud_user,
            'password': cloud_pwd,
            'ssl_verify': grid_connection['ssl_verify'],
            'http_pool_connections':
                grid_connection['http_pool_connections'],
            'http_pool_maxsize': grid_connection['http_pool_maxsize'],
            'http_request_timeout': grid_connection['http_request_timeout']
        }
        return connector.Connector(opts)

    @staticmethod
    def _get_tenant_name(tenant_id):
        # TODO(hhwang): We need to store tenant names and retrieve here.
        return 'test-tenant-name'

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

        # First check if mapping already exists
        network_id = self.subnet.get('network_id')
        subnet_id = self.subnet.get('id')
        netview_mapping = dbi.get_network_view_mapping(
            session, network_id=network_id, subnet_id=subnet_id)
        if netview_mapping:
            netview_id = netview_mapping[0].network_view_id
            netview_row = utils.find_one_in_list(
                'id', netview_id, self.discovered_network_views)
            self.mapping.network_view_id = netview_id
            self.mapping.network_view = netview_row.network_view
            self.mapping.authority_member = self._get_authority_member(
                netview_row.authority_member_id)
            LOG.info(_LI("Network view %(netview)s mapping found for "
                         "network %(network)s and subnet %(subnet)s"),
                     dict(netview=netview_row.network_view, network=network_id,
                          subnet=subnet_id))
            return

        # No mapping so find mapping
        mapping_attrs = self._get_mapping_attributes()
        matching_netviews = []

        # find mapping matches on common cases
        mapping_filters = self._get_scalar_mapping_filters(mapping_attrs)
        for mf in mapping_filters:
            if mf.values()[0] is None:
                continue
            matches = utils.find_in_list_by_condition(
                mf, self.discovered_mapping_conditions)
            if matches:
                netview_ids = [m.network_view_id for m in matches]
                matching_netviews.append(set(netview_ids))

        # find matches for tenant cidrs
        mapping_filters = self._get_tenant_cidr_mapping_filters()
        for mf in mapping_filters:
            matches = utils.find_in_list_by_condition(
                mf, self.discovered_mapping_conditions)
            if matches:
                netview_ids = [m.network_view_id for m in matches]
                matching_netviews.append(set(netview_ids))

        # find network view id and name pair
        if matching_netviews:
            matching_netview_ids = list(set.intersection(*matching_netviews))
            # if multiple netview ids return, pick the first one
            netview_id = matching_netview_ids[0]
            netview_row = utils.find_one_in_list('id', netview_id,
                                                 self.discovered_network_views)
            netview_name = netview_row.network_view
        else:
            # no matching found; use default network view scope
            netview_scope = self.grid_config.default_network_view_scope
            netview_name = self._get_network_view_by_scope(netview_scope,
                                                           mapping_attrs)
            netview_row = utils.find_one_in_list('network_view', netview_name,
                                                 self.discovered_network_views)
            if netview_row:
                netview_id = netview_row.id

        self.mapping.network_view_id = netview_id
        self.mapping.network_view = netview_name
        if self.mapping.network_view_id:
            self.mapping.authority_member = self._get_authority_member()

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
        tenant_id = self.network.get('tenant_id')
        tenant_name = self._get_tenant_name(tenant_id)
        address_scope_id, address_scope_name = self._get_address_scope(
            subnetpool_id)
        return {'subnet_id': self.subnet.get('id'),
                'subnet_name': self.subnet.get('name'),
                'subnet_cidr': self.subnet.get('cidr'),
                'subnetpool_id': self.subnet.get('subnetpool_id'),
                'network_id': self.network.get('id'),
                'network_name': self.network.get('name'),
                'tenant_id': tenant_id,
                'tenant_name': tenant_name,
                'address_scope_id': address_scope_id,
                'address_scope_name': address_scope_name}

    @staticmethod
    def _get_scalar_mapping_filters(attrs):
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

    def _get_tenant_cidr_mapping_filters(self):
        session = self.context.session
        tenant_id = self.network.get('tenant_id')

        db_tenant_subnets = dbi.get_subnets_by_tenant_id(session, tenant_id)
        tenant_subent_cidrs = utils.get_values_from_records('cidr',
                                                            db_tenant_subnets)
        return [
            {const.MAPPING_CONDITION_KEY_NAME: const.EA_MAPPING_TENANT_CIDR,
             const.MAPPING_CONDITION_VALUE_NAME: cidr}
            for cidr in tenant_subent_cidrs]

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
