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

import oslo_config.types as types

from networking_infoblox.neutron.common import constants as const
from networking_infoblox.neutron.common import exceptions as exc
from networking_infoblox.neutron.common import utils
from networking_infoblox.neutron.db import infoblox_db as dbi


DELIMITER = '^'


class GridMappingManager(object):

    # network view mapping order listed hierarchically from bottom to top
    mapping_neutron_object_names = [const.EA_MAPPING_SUBNET_ID,
                                    const.EA_MAPPING_SUBNET_CIDR,
                                    const.EA_MAPPING_NETWORK_NAME,
                                    const.EA_MAPPING_NETWORK_ID,
                                    const.EA_MAPPING_TENANT_NAME,
                                    const.EA_MAPPING_TENANT_ID,
                                    const.EA_MAPPING_ADDRESS_SCOPE_NAME,
                                    const.EA_MAPPING_ADDRESS_SCOPE_ID]

    def __init__(self, grid_config):
        self._grid_config = grid_config
        self._connector = self._grid_config.gm_connector
        self._context = self._grid_config.context
        self._grid_id = self._grid_config.grid_id

    def sync(self):
        """Discovers and syncs networks between Neutron and Infoblox backend.

        The following information is discovered and synchronized.
        1. network views
        2. neutron network mapping conditions to NIOS network
        3. authority members that owns network views by either GM ownership or
           delegation to Cloud Platform Members (CPM).

        :return: None
        """
        session = self._context.session
        self.db_members = dbi.get_members(session, grid_id=self._grid_id)

        discovered_network_views = self._discover_network_views()
        if not discovered_network_views:
            return

        discovered_dns_views = self._discover_dns_views()
        dns_views = self.get_dns_views(discovered_dns_views)

        discovered_delegations = self._sync_network_views(
            discovered_network_views, dns_views)

        discovered_networks = self._discover_networks()
        self._sync_network_mapping(discovered_networks, discovered_delegations)

    def _load_persisted_mappings(self):
        session = self._context.session
        self.db_network_views = dbi.get_network_views(
            session, grid_id=self._grid_id)
        self.db_mapping_conditions = dbi.get_mapping_conditions(
            session, grid_id=self._grid_id)
        self.db_authority_members = dbi.get_mapping_members(
            session, grid_id=self._grid_id)
        self.db_service_members = dbi.get_service_members(
            session, grid_id=self._grid_id)

    def get_dns_views(self, discovered_dns_views):
        dns_views = dict()
        for dns_view in discovered_dns_views:
            netview_name = dns_view['network_view']
            dnsview_name = dns_view['name']
            if netview_name not in dns_views:
                dns_views[netview_name] = dnsview_name
        return dns_views

    def _sync_network_views(self, discovered_netviews, dns_views):
        """Discover network views and sync with db.

        The discovered network view json contains the following data:
        - network view
        - cloud_info for delegated member if cloud platform is supported
        - mapping conditional EAs

        So discovered information will be updated in tables such as
        infoblox_network_views and infoblox_mapping_conditions.

        :param discovered_netviews: discovered network view json
        :return: None
        """
        session = self._context.session
        self._load_persisted_mappings()
        discovered_delegations = dict()

        persisted_netview_ids = utils.get_values_from_records(
            'id', self.db_network_views)
        discovered_netview_ids = []

        for netview in discovered_netviews:
            netview_name = netview['name']
            is_default = netview[const.IS_DEFAULT]
            netview_id = utils.get_network_view_id(self._grid_id,
                                                   netview['_ref'])

            cloud_adapter_id_vals = utils.get_ea_value(
                const.EA_CLOUD_ADAPTER_ID, netview, True)
            if cloud_adapter_id_vals is None:
                participated = False
            else:
                cloud_adapter_ids = [gid for gid in cloud_adapter_id_vals
                                     if int(gid) == self._grid_id]
                participated = True if cloud_adapter_ids else False

            if not participated:
                continue

            shared_val = utils.get_ea_value(const.EA_IS_SHARED, netview)
            is_shared = types.Boolean()(shared_val) if shared_val else False

            # authority member is default to GM
            gm_row = utils.find_one_in_list('member_type',
                                            const.MEMBER_TYPE_GRID_MASTER,
                                            self.db_members)
            authority_member_id = gm_row.member_id

            # get delegation member if cloud platform is supported
            delegated_member = self._get_delegated_member(netview)
            if delegated_member:
                authority_member_id = delegated_member.member_id
                discovered_delegations[netview_name] = (
                    delegated_member.member_id)

            dns_view = (dns_views[netview_name] if dns_views.get(netview_name)
                        else None)

            # see if the network view already exists in db
            netview_row = utils.find_one_in_list('id',
                                                 netview_id,
                                                 self.db_network_views)
            if netview_row:
                dbi.update_network_view(session, netview_id, netview_name,
                                        authority_member_id, is_shared,
                                        dns_view, participated, is_default)
            else:
                internal_netview = (const.DEFAULT_NETWORK_VIEW if is_default
                                    else netview_name)
                internal_dnsview = (const.DEFAULT_DNS_VIEW if is_default
                                    else dns_view)
                dbi.add_network_view(session,
                                     netview_id,
                                     netview_name,
                                     self._grid_id,
                                     authority_member_id,
                                     is_shared,
                                     dns_view,
                                     internal_netview,
                                     internal_dnsview,
                                     participated,
                                     is_default)

            discovered_netview_ids.append(netview_id)

            # update mapping conditions for the current network view
            self._update_mapping_conditions(netview, netview_id, participated)

        # we have added new network views. now let's remove persisted
        # network views not found from discovery
        persisted_set = set(persisted_netview_ids)
        removable_set = persisted_set.difference(discovered_netview_ids)
        removable_netviews = list(removable_set)
        if removable_netviews:
            dbi.remove_network_views(session, removable_netviews)
        session.flush()
        return discovered_delegations

    def _sync_network_mapping(self, discovered_networks,
                              discovered_delegations):
        """Discover networks and sync with db.

        The discovered network json contains the following data:
        - network view
        - network
        - cloud_info for delegated member if cloud platform is supported
        - dhcp members

        :param discovered_networks: discovered network json
        :param discovered_delegations: discovered delegation members
        :return: None
        """
        session = self._context.session
        self._load_persisted_mappings()

        discovered_mapping = self._get_member_mapping(discovered_networks,
                                                      discovered_delegations)

        # add or remove authority mapping members
        persisted_authority_members = utils.get_composite_values_from_records(
            ['network_view_id', 'member_id', 'mapping_relation'],
            self.db_authority_members,
            DELIMITER)
        persisted_set = set(persisted_authority_members)
        discovered_set = set(discovered_mapping['authority_members'])
        addable_set = discovered_set.difference(persisted_set)
        removable_set = persisted_set.difference(discovered_set)

        for authority_member_info in addable_set:
            authority_member = authority_member_info.split(DELIMITER)
            network_view_id = authority_member[0]
            member_id = authority_member[1]
            mapping_relation = authority_member[2]
            dbi.add_mapping_member(session, network_view_id, member_id,
                                   mapping_relation)

        for authority_member_info in removable_set:
            authority_member = authority_member_info.split(DELIMITER)
            network_view_id = authority_member[0]
            member_id = authority_member[1]
            dbi.remove_mapping_member(session, network_view_id, member_id)

        # add or remove service members
        persisted_service_members = utils.get_composite_values_from_records(
            ['network_view_id', 'member_id', 'service'],
            self.db_service_members,
            DELIMITER)
        persisted_set = set(persisted_service_members)
        discovered_set = set(discovered_mapping['service_members'])
        addable_set = discovered_set.difference(persisted_set)
        removable_set = persisted_set.difference(discovered_set)

        for service_member_info in addable_set:
            service_member = service_member_info.split(DELIMITER)
            network_view_id = service_member[0]
            member_id = service_member[1]
            service = service_member[2]
            dbi.add_service_member(session, network_view_id, member_id,
                                   service)

        for service_member_info in removable_set:
            service_member = service_member_info.split(DELIMITER)
            network_view_id = service_member[0]
            member_id = service_member[1]
            service = service_member[2]
            dbi.remove_service_member(session, network_view_id,
                                      member_id=member_id, service=service)

    def _discover_network_views(self):
        return_fields = ['name', 'is_default', 'extattrs']
        if self._grid_config.is_cloud_wapi:
            return_fields.append('cloud_info')

        netviews = self._connector.get_object('networkview',
                                              return_fields=return_fields)
        if not netviews:
            return []
        return netviews

    def _discover_networks(self):
        return_fields = ['members', 'network_view', 'network', 'options']
        if self._grid_config.is_cloud_wapi:
            return_fields.append('cloud_info')

        # TODO(pbondar): Consider using NetworkV4 and NetworkV6 objects
        #                from infoblox-client to interact with NIOS
        ipv4networks = self._connector.get_object('network',
                                                  return_fields=return_fields)
        ipv6networks = self._connector.get_object('ipv6network',
                                                  return_fields=return_fields)
        # get_object returns None if nothing was found, so convert results
        if not ipv4networks:
            ipv4networks = []
        if not ipv6networks:
            ipv6networks = []
        return ipv4networks + ipv6networks

    def _discover_dns_views(self):
        return_fields = ['name', 'network_view']
        dns_views = self._connector.get_object('view',
                                               return_fields=return_fields)
        if not dns_views:
            return []
        return dns_views

    def _get_member_mapping(self, discovered_networks, discovered_delegations):
        """Returns members that are used for authority and dhcp.

        Authority members own network views because they are either GM who owns
        non delegated network views or Cloud Platform Member(CPM) who owns
        delegated network views.

        DHCP members are the members who serve DHCP protocols.
        """
        gm_row = utils.find_one_in_list('member_type',
                                        const.MEMBER_TYPE_GRID_MASTER,
                                        self.db_members)
        gm_member_id = gm_row.member_id
        mapping_authority_members = []
        mapping_service_members = []

        # first get delegated authority members from Infoblox network views
        for netview in discovered_delegations:
            netview_row = utils.find_one_in_list('network_view', netview,
                                                 self.db_network_views)
            if not netview_row:
                continue
            netview_id = netview_row.id
            authority_member = discovered_delegations[netview]
            mapping_relation = const.MAPPING_RELATION_DELEGATED
            mapping_row_info = (netview_id + DELIMITER +
                                authority_member + DELIMITER +
                                mapping_relation)
            mapping_authority_members.append(mapping_row_info)

        # then get authority and dhcp members from Infoblox networks
        for network in discovered_networks:
            netview = network['network_view']
            netview_row = utils.find_one_in_list('network_view', netview,
                                                 self.db_network_views)
            if not netview_row or not netview_row.participated:
                continue

            netview_id = netview_row.id

            # get authority member
            mapping_relation = const.MAPPING_RELATION_GM_OWNED
            authority_member = gm_member_id
            delegated_member = self._get_delegated_member(network)

            if netview in discovered_delegations:
                authority_member = discovered_delegations[netview]
                mapping_relation = const.MAPPING_RELATION_DELEGATED
            elif delegated_member:
                authority_member = delegated_member.member_id
                mapping_relation = const.MAPPING_RELATION_DELEGATED

            mapping_member_info = (netview_id + DELIMITER +
                                   authority_member + DELIMITER +
                                   mapping_relation)
            if mapping_member_info not in mapping_authority_members:
                mapping_authority_members.append(mapping_member_info)

            # get dhcp member
            dhcp_members = self._get_dhcp_members(network)
            for member in dhcp_members:
                mapping_member_info = (netview_id + DELIMITER +
                                       member.member_id + DELIMITER +
                                       const.SERVICE_TYPE_DHCP)
                if mapping_member_info not in mapping_service_members:
                    mapping_service_members.append(mapping_member_info)

            # get dns member
            dns_members = self._get_dns_members(network)
            for member in dns_members:
                mapping_member_info = (netview_id + DELIMITER +
                                       member.member_id + DELIMITER +
                                       const.SERVICE_TYPE_DNS)
                if mapping_member_info not in mapping_service_members:
                    mapping_service_members.append(mapping_member_info)

        return {'authority_members': mapping_authority_members,
                'service_members': mapping_service_members}

    def _get_mapping_conditions(self, netview_dict):
        conditions = dict()
        for object_name in self.mapping_neutron_object_names:
            object_value = utils.get_ea_value(object_name, netview_dict, True)
            if object_value:
                conditions[object_name] = object_value
        return conditions

    def _get_delegated_member(self, network_dict):
        delegated_member = None
        if (network_dict.get('cloud_info') and
                network_dict['cloud_info'].get('delegated_member')):
            delegated_member_name = (
                network_dict['cloud_info']['delegated_member']['name'])
            delegated_member = utils.find_one_in_list(
                'member_name', delegated_member_name, self.db_members)
            if not delegated_member:
                raise exc.InfobloxCannotFindMember(
                    member=delegated_member_name)
        return delegated_member

    def _get_dhcp_members(self, network_dict):
        # multiple dhcp members can be assigned to a network
        dhcp_members = []
        member_ips = utils.get_dhcp_member_ips(network_dict)
        for member_ip in member_ips:
            dhcp_member = utils.find_in_list_by_value(member_ip,
                                                      self.db_members)
            if not dhcp_member:
                raise exc.InfobloxCannotFindMember(
                    member=member_ip)
            dhcp_members.append(dhcp_member)
        return dhcp_members

    def _get_dns_members(self, network_dict):
        # multiple dns members can be assigned to a network
        dns_members = []
        member_ips = utils.get_dns_member_ips(network_dict)
        for member_ip in member_ips:
            dns_member = utils.find_in_list_by_value(member_ip,
                                                     self.db_members)
            if dns_member:
                dns_members.append(dns_member)
        return dns_members

    def _update_mapping_conditions(self, discovered_netview, netview_id,
                                   participated):
        session = self._context.session
        mapping_conditions = dict()
        if participated:
            mapping_conditions = self._get_mapping_conditions(
                discovered_netview)
        discovered_condition_rows = []
        for condition_name in mapping_conditions:
            conditions = [netview_id + DELIMITER + condition_name + DELIMITER +
                          value for value in
                          mapping_conditions[condition_name]]
            discovered_condition_rows += conditions

        mapping_condition_rows = utils.find_in_list(
            'network_view_id', [netview_id], self.db_mapping_conditions)
        condition_rows = utils.get_composite_values_from_records(
            ['network_view_id', 'neutron_object_name', 'neutron_object_value'],
            mapping_condition_rows,
            DELIMITER)
        persisted_set = set(condition_rows)
        discovered_set = set(discovered_condition_rows)
        addable_set = discovered_set.difference(persisted_set)
        removable_set = persisted_set.difference(discovered_set)

        for condition_attr in addable_set:
            condition = condition_attr.split(DELIMITER)
            network_view_id = condition[0]
            neutron_object_name = condition[1]
            neutron_object_value = condition[2]
            dbi.add_mapping_condition(session,
                                      network_view_id,
                                      neutron_object_name,
                                      neutron_object_value)

        for condition_attr in removable_set:
            condition = condition_attr.split(DELIMITER)
            network_view_id = condition[0]
            neutron_object_name = condition[1]
            neutron_object_value = condition[2]
            dbi.remove_mapping_condition(session,
                                         network_view_id,
                                         neutron_object_name,
                                         neutron_object_value)
