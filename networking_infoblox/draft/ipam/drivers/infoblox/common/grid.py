# Copyright 2015 OpenStack LLC.
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

import io
import re
import six

from oslo_log import log as logging
from oslo_serialization import jsonutils

from neutron.common import constants as n_const
from neutron.i18n import _LE
from neutron.ipam.drivers.infoblox.common import config as ib_conf
from neutron.ipam.drivers.infoblox.common import constants as ib_const
from neutron.ipam.drivers.infoblox.common import exceptions as ib_ex
from neutron.ipam.drivers.infoblox.common import utils as ib_utils
from neutron.ipam.drivers.infoblox.db import db_api as ib_dbi


LOG = logging.getLogger(__name__)


class GridManager(object):
    member = None
    config = None

    context = None
    is_grid_synced = False

    grid_members = dict()

    def __init__(self, context, member_config_stream=None,
                 condition_config_stream=None):
        self.context = context
        self.member = GridMemberManager(context, member_config_stream)
        self.config = GridConfigManager(context, condition_config_stream)

    def sync(self):
        self.is_grid_synced = False
        self.grid_members.clear()

        self.member.sync()
        self.config.sync()

        session = self.context.session
        db_grids = ib_dbi.get_grids(session)
        grids = ib_utils.db_records_to_obj('Grid', db_grids)

        for grid in grids:
            grid.grid_connection = ib_utils.json_to_obj('Connection',
                                                        grid.grid_connection)
            db_members = ib_dbi.get_members(session, grid_id=grid.grid_id)
            members = ib_utils.db_records_to_obj('Member', db_members)
            self.grid_members[grid.grid_id] = {'grid': grid,
                                               'members': members}
        self.is_grid_synced = True

    def get_infoblox_condition(self, network, subnet=None):
        session = self.context.session
        network_id = network.get('id')
        self._check_grid_sync()

        condition = self.config.get_condition(network, subnet)
        self._set_grid_connection(condition)
        conf_grid_id = condition.grid_id
        conf_network_view = condition.network_view
        conf_authority_member = condition.authority_member
        conf_dns_members = condition.dns_members
        grid_members = self.grid_members[conf_grid_id]['members']

        network_members = self.member.get_network_members(conf_network_view)
        if not network_members:
            return condition

        service_members = self.member.get_service_members(network_id)
        if not service_members:
            return condition

        network_member_ids = ib_utils.get_values_from_records('member_id',
                                                              network_members)
        service_member_ids = ib_utils.get_values_from_records('member_id',
                                                              service_members)
        member_ids = list(set(network_member_ids + service_member_ids))

        db_reserved_members = ib_dbi.search_members(session,
                                                    member_ids=member_ids)
        if len(db_reserved_members) != len(member_ids):
            db_member_ids = ib_utils.get_values_from_records(
                'member_id', db_reserved_members)
            raise ib_ex.InfobloxMemberReservationError(
                msg="Expected to find member (%s) but found reserved "
                    "members (%s)." % (member_ids, db_member_ids))

        is_dynamic = conf_authority_member == ib_const.NEXT_AVAILABLE_MEMBER

        # get authority member and mapping relation
        search_member_id = (network_members[0].member_id if is_dynamic
                            else conf_authority_member)
        authority_member = ib_utils.find_one_in_list('member_id',
                                                     search_member_id,
                                                     grid_members)
        condition.authority_member = authority_member
        condition.authority_member_type = authority_member.member_type
        condition.mapping_relation = self._get_mapping_relation(condition)

        # get dhcp network members
        condition.network_members = ib_utils.find_in_list('member_id',
                                                          network_member_ids,
                                                          grid_members)

        # get dhcp service members
        dhcp_members = ib_utils.find_in_list('service',
                                             [ib_const.SERVICE_TYPE_DHCP],
                                             service_members)
        dhcp_member_ids = ib_utils.get_values_from_records('member_id',
                                                           dhcp_members)
        condition.dhcp_members = ib_utils.find_in_list('member_id',
                                                       dhcp_member_ids,
                                                       grid_members)

        # get dns service members
        condition.dns_members = dict()
        dns_members = ib_utils.find_in_list('service',
                                            [ib_const.SERVICE_TYPE_DNS],
                                            service_members)
        dns_member_ids = ib_utils.get_values_from_records('member_id',
                                                          dns_members)
        if conf_dns_members == ib_const.NEXT_AVAILABLE_MEMBER:
            dns_primary = ib_utils.find_in_list('member_id',
                                                dns_member_ids,
                                                grid_members)
            dns_secondary = []
        else:
            conf_dns_primary_members = condition.dns_members['primary']
            dns_primary = ib_utils.find_in_list('member_id',
                                                conf_dns_primary_members,
                                                grid_members)
            conf_dns_secondary_members = condition.dns_members['secondary']
            dns_secondary = ib_utils.find_in_list('member_id',
                                                  conf_dns_secondary_members,
                                                  grid_members)
        condition.dns_members['primary'] = dns_primary
        condition.dns_members['secondary'] = dns_secondary

    def reserve_members_for_subnet(self, network, subnet):
        """Reserves authority member, dhcp network member, dns members and
        dhcp members.

        The following condition properties are updated:
        - condition.authority_member
        - condition.authority_member_type
        - condition.dhcp_members
        - condition.dns_members

        an authority member is a member that owns a network view
        a network member is a member that owns a dhcp network
        a service member is a member that serves dhcp and dns

        There are 3 types of member reservation for dhcp network member.
        1. authority manager is CP so dhcp network member is also CP.
           then condition.mapping_relation is 'CP'
        2. both authority manager and dhcp network member are GM so mapping
           relation is 'GM'
        3. authority manager is GM and dhcp network member is one or more
          other members so mapping relation is 'GM-DISTRIBUTED'

        For CP, authority member owns network view as well as dhcp network.
        So authority and dhcp network are the same member.

        For host record, dns primary is the same as dhcp network member.
        For dns records, dns primary can be different members.
        Secondary members can be different members.

        For GM, authority member is GM but it can have many multiple dhcp
        networks. Each dhcp network member should also serve as dns primary
        for host records. For DNS records, dns primary can be different
        members.

        For REGULAR member, dhcp members are purely protocol. dhcp network is
        owned by GM. GM can have many network views but each network view
        needs to be assigned to each dhcp member that serves the protocol.

        As far as a member assignment is concerned in grid module,
        network member is the dhcp network member.
        """
        self._check_grid_sync()

        condition = self.config.get_condition(network, subnet)
        self._set_grid_connection(condition)

        conf_condition = condition.condition
        conf_grid_id = condition.grid_id
        conf_authority_member = condition.authority_member
        conf_dhcp_members = condition.dhcp_members

        grid_members = self.grid_members[conf_grid_id]['members']
        service_members_config = self.config.service_members

        is_dynamic = conf_authority_member == ib_const.NEXT_AVAILABLE_MEMBER
        needs_dhcp_member_reservation = (conf_dhcp_members ==
                                         ib_const.NEXT_AVAILABLE_MEMBER)

        # authority member is predefined
        if not is_dynamic:
            condition.authority_member = ib_utils.find_one_in_list(
                'member_id', conf_authority_member, grid_members)
            condition.authority_member_type = \
                condition.authority_member.member_type
            condition.mapping_relation = self._get_mapping_relation(condition)

        # reserve a member if authority member is <next-available-member> or
        # GM where dhc_members is <next-available-member>
        network_members = self.member.reserve_network_member(condition)
        if not network_members:
            raise ib_ex.InfobloxMemberReservationError(
                msg="No member was reserved for network.")

        network_member_ids = ib_utils.get_values_from_records('member_id',
                                                              network_members)
        condition.network_members = ib_utils.find_in_list('member_id',
                                                          network_member_ids,
                                                          grid_members)

        # update condition.authority_member for <next-available-member>
        if is_dynamic:
            search_member_id = network_members[0].member_id
            condition.authority_member = ib_utils.find_one_in_list(
                'member_id', search_member_id, grid_members)

        # if authority member is GM and dns member is <next-available-member>
        # dhcp member is used as a network view mapping member, this member
        # needs to be included as service member as well.
        is_gm = condition.authority_member_type == \
            ib_const.MEMBER_TYPE_GRID_MASTER
        if is_gm and needs_dhcp_member_reservation:
            network_id_list = [m.member_id for m in network_members]
            service_type_dhcp = ib_const.SERVICE_TYPE_DHCP
            cond_service_members = service_members_config.get(conf_condition)
            if cond_service_members is None:
                cond_service_members[conf_condition] = \
                    {service_type_dhcp: network_id_list}
            else:
                service_member_ids = ib_utils.merge_list(
                    cond_service_members[conf_condition][service_type_dhcp],
                    network_id_list)
                cond_service_members[conf_condition][service_type_dhcp] = \
                    service_member_ids

        # reserve service members
        service_members = self.member.reserve_service_members(
            condition, service_members_config)
        if service_members is None or \
                service_members.get('dhcp_members') is None or \
                service_members.get('dns_members') is None:
            raise ib_ex.InfobloxMemberReservationError(
                msg="member reservation for services has failed.")

        # get dhcp members
        dhcp_members = service_members['dhcp_members']
        dhcp_member_ids = ib_utils.get_values_from_records('member_id',
                                                           dhcp_members)
        condition.dhcp_members = ib_utils.find_in_list('member_id',
                                                       dhcp_member_ids,
                                                       grid_members)

        # get dns members
        condition.dns_members = dict()
        dns_primary = service_members['dns_members']['primary']
        dns_primary_ids = ib_utils.get_values_from_records('member_id',
                                                           dns_primary)
        dns_primary_members = ib_utils.find_in_list('member_id',
                                                    dns_primary_ids,
                                                    grid_members)

        dns_secondary = service_members['dns_members']['secondary']
        dns_secondary_ids = ib_utils.get_values_from_records('member_id',
                                                             dns_secondary)
        dns_secondary_members = ib_utils.find_in_list('member_id',
                                                      dns_secondary_ids,
                                                      grid_members)
        condition.dns_members['primary'] = dns_primary_members
        condition.dns_members['secondary'] = dns_secondary_members

        valid = (condition.network_members and condition.dhcp_members and
                 condition.dns_members['primary'])
        if not valid:
            raise ib_ex.InfobloxMemberReservationError(
                msg="At least one DHCP network and DHCP and DNS services "
                    "must be reserved but returned (DHCP network: %s, "
                    "DHCP service: %s, DNS service: %s)" %
                    (condition.network_members, condition.dhcp_members,
                     condition.dns_members['primary']))
        return condition

    def _check_grid_sync(self):
        if not self.is_grid_synced:
            raise ib_ex.InfobloxMemberReservationError(
                msg="Infoblox grid is not in sync. GridManager.sync() should "
                    "be called first.")

    def _set_grid_connection(self, condition):
        subnet_grid = self.grid_members.get(condition.grid_id)
        if subnet_grid is None:
            raise ib_ex.InfobloxMemberReservationError(
                msg="Infoblox grid id '%s' is not found." % condition.grid_id)

        if condition.grid_members is None:
            condition.grid_members = subnet_grid['members']
        if condition.grid_connection is None:
            condition.grid_connection = subnet_grid['grid'].grid_connection

    @staticmethod
    def _get_mapping_relation(condition):
        if condition.authority_member == ib_const.NEXT_AVAILABLE_MEMBER:
            return ib_const.MAPPING_RELATION_CP

        mapping_relation = ib_const.MAPPING_RELATION_CP
        needs_dhcp_member_reservation = (condition.dhcp_members ==
                                         ib_const.NEXT_AVAILABLE_MEMBER)
        is_gm = condition.authority_member_type == \
            ib_const.MEMBER_TYPE_GRID_MASTER
        if is_gm:
            if needs_dhcp_member_reservation:
                mapping_relation = ib_const.MAPPING_RELATION_GM_DISTRIBUTED
            elif len(condition.dhcp_members) == 1 and \
                    condition.authority_member.member_id == \
                    condition.dhcp_members[0]:
                mapping_relation = ib_const.MAPPING_RELATION_GM
            else:
                mapping_relation = ib_const.MAPPING_RELATION_GM_DISTRIBUTED
        return mapping_relation


class GridMemberManager(object):

    def __init__(self, context, config_stream=None):
        self._context = context
        if not config_stream:
            config_file = ib_conf.CONF_IPAM.member_config
            if not config_file:
                raise ib_ex.InfobloxConfigException(
                    msg="Member config not found")
            config_stream = io.FileIO(config_file)

        with config_stream:
            try:
                self._conf = jsonutils.loads(config_stream.read())
            except ValueError as e:
                raise ib_ex.InfobloxConfigException(msg="Member => %s" % e)

    @property
    def member_conf(self):
        return self._conf

    def sync(self):
        """Synchronizes members between config file and db."""
        session = self._context.session
        db_grids = ib_dbi.get_grids(session)
        db_grid_ids = ib_utils.get_values_from_records('grid_id', db_grids)

        db_members = ib_dbi.get_members(session)
        db_member_ids = ib_utils.get_values_from_records('member_id',
                                                         db_members)

        db_reserved_members = ib_dbi.get_reserved_members_for_network(session)
        db_reserved_member_ids = ib_utils.get_values_from_records(
            'member_id', db_reserved_members)

        conf_grid_ids = []
        conf_member_ids = []

        # register new and existing grids and grid members
        for conf_grid in self._conf:
            grid = self._get_grid_from_config(conf_grid)
            # register grid
            if grid.grid_id in db_grid_ids:
                # an existing grid
                ib_dbi.update_grid(session,
                                   grid.grid_id,
                                   grid.grid_name,
                                   grid.grid_connection)
            else:
                # a new grid
                ib_dbi.add_grid(session,
                                grid.grid_id,
                                grid.grid_name,
                                grid.grid_connection)
            conf_grid_ids.append(grid.grid_id)
            session.flush()

            # register members for the grid
            for conf_member in conf_grid['grid_members']:
                member = self._get_member_from_config(conf_member)
                if member.member_id in db_member_ids:
                    ib_dbi.update_member(session,
                                         member.member_id,
                                         grid.grid_id,
                                         member.member_name,
                                         member.member_ip,
                                         member.member_ipv6,
                                         member.member_type,
                                         member.member_status)
                else:
                    ib_dbi.add_member(session,
                                      member.member_id,
                                      grid.grid_id,
                                      member.member_name,
                                      member.member_ip,
                                      member.member_ipv6,
                                      member.member_type,
                                      member.member_status)
                conf_member_ids.append(member.member_id)

        reserved_set = set(db_reserved_member_ids)
        configured_set = set(conf_member_ids)
        registered_set = set(db_member_ids)

        # find the missing members from the configuration
        missing_set = reserved_set.difference(configured_set)
        missing_member_ids = list(missing_set)
        if missing_member_ids:
            raise ib_ex.InfobloxGridSyncError(
                msg="Reserved members are not found in the member "
                    "configuration: %s." % missing_member_ids)

        # find the removable members
        removable_set = registered_set.difference(configured_set)
        removable_member_ids = list(removable_set)
        if removable_member_ids:
            ib_dbi.remove_members(session, removable_member_ids)

        # find the removable grids
        registered_set = set(db_grid_ids)
        configured_set = set(conf_grid_ids)
        removable_set = registered_set.difference(configured_set)
        removable_grid_ids = list(removable_set)
        if removable_grid_ids:
            ib_dbi.remove_grids(session, removable_grid_ids)

    def reserve_network_member(self, condition):
        """Reserve a network member

        if authority_member is <next-available-member>, a CP member must be
        selected since only CP can generate a network view dynamically.

        if authority_member is a GM, then network view can be dynamically
        generated on GM but dhcp member should be set to
        <next-available-member>.

        The following conditions are allowed.
        {
             "network_view": "default",
             "authority_member": "master.com",
             "dhcp_members": "<next-available-member>"
        }

        {
             "network_view": "<next-available-member>",
             "authority_member": "master.com"
        }
        """
        if condition is None or condition.grid_id is None or \
                condition.network_view is None or \
                condition.mapping_scope is None or \
                condition.authority_member is None:
            raise ib_ex.InfobloxMemberReservationError(
                msg="A valid condition must be passed with mandatory "
                    "fields.")

        conf_network_view = condition.network_view
        reserved_members = self.get_network_members(conf_network_view)
        if reserved_members:
            return reserved_members

        conf_grid_id = condition.grid_id
        conf_mapping_scope = condition.mapping_scope
        conf_authority_member_type = condition.authority_member_type
        conf_mapping_relation = condition.mapping_relation

        # if authority member type is GM, then next member can be either CP
        # or REGULAR. if not GM, then it is CP since REGULAR cannot be
        # authority member.
        if conf_authority_member_type == ib_const.MEMBER_TYPE_GRID_MASTER:
            member_type = None
        else:
            member_type = ib_const.MEMBER_TYPE_CP_MEMBER

        reserved_member = self._reserve_next_available_member_for_network(
            conf_grid_id, conf_network_view, conf_mapping_scope,
            conf_mapping_relation, member_type)
        if reserved_member:
            return [reserved_member]

        raise ib_ex.InfobloxMemberReservationError(
            msg="'%s' failed to reserve a member for network" %
                conf_network_view)

    def reserve_service_members(self, condition, service_members_config):
        authority_member = condition.authority_member
        conf_condition = condition.condition

        if condition is None or conf_condition is None or \
                condition.subnet is None or authority_member == \
                ib_const.NEXT_AVAILABLE_MEMBER:
            raise ib_ex.InfobloxMemberReservationError(
                msg="A valid condition must be passed with mandatory "
                    "fields like authority_member, condition, and subnet. "
                    "'authority_member' should have a valid member assigned.")

        authority_member_id = authority_member.member_id
        network_id = condition.subnet.get('network_id')
        if service_members_config is None:
            service_members_config = dict()

        serviced_members = self.get_service_members(network_id)

        # configured service members are populated if network view is static
        reserved_members = dict()
        service_members = service_members_config.get(conf_condition)
        if service_members is None:
            # no configured service members, so service member must be the
            # same as conf_authority_member
            dhcp_member = self._reserve_service(serviced_members,
                                                ib_const.SERVICE_TYPE_DHCP,
                                                network_id,
                                                authority_member_id)
            reserved_members['dhcp_members'] = [dhcp_member]

            dns_member = self._reserve_service(serviced_members,
                                               ib_const.SERVICE_TYPE_DNS,
                                               network_id,
                                               authority_member_id)
            reserved_members['dns_members'] = {'primary': [dns_member],
                                               'secondary': []}
        else:
            # configured service members are found so network view is static
            # and dhcp and dns members are predefined.
            service_type = ib_const.SERVICE_TYPE_DHCP
            dhcp_member_ids = service_members.get(service_type, [])
            dhcp_member_list = []
            for member_id in dhcp_member_ids:
                dhcp_member = self._reserve_service(serviced_members,
                                                    service_type,
                                                    network_id,
                                                    member_id)
                dhcp_member_list.append(dhcp_member)
            reserved_members['dhcp_members'] = dhcp_member_list

            service_type = ib_const.SERVICE_TYPE_DNS
            dns_members = service_members.get(service_type, None)
            if dns_members is None:
                reserved_members['dns_members'] = {'primary': [],
                                                   'secondary': []}
            else:
                dns_primary_list = []
                for member_id in dns_members['primary']:
                    dns_member = self._reserve_service(serviced_members,
                                                       service_type,
                                                       network_id,
                                                       member_id)
                    dns_primary_list.append(dns_member)

                dns_secondary_list = []
                for member_id in dns_members['secondary']:
                    dns_member = self._reserve_service(serviced_members,
                                                       service_type,
                                                       network_id,
                                                       member_id)
                    dns_secondary_list.append(dns_member)

                reserved_members['dns_members'] = \
                    {'primary': dns_primary_list,
                     'secondary': dns_secondary_list}

        return reserved_members

    def get_network_members(self, network_view):
        session = self._context.session
        db_network_members = ib_dbi.get_reserved_members_for_network(
            session=session, mapping_id=network_view)
        network_members = ib_utils.db_records_to_obj('Member',
                                                     db_network_members)
        return network_members

    def get_service_members(self, network_id):
        session = self._context.session
        db_service_members = ib_dbi.get_members_for_services(
            session, network_id=network_id)
        service_members = ib_utils.db_records_to_obj('Member',
                                                     db_service_members)
        return service_members

    @staticmethod
    def _get_member_from_config(conf_member):
        member_id = conf_member.get('member_id', None)
        member_name = conf_member.get('member_name', None)
        member_type = conf_member.get('member_type', 'invalid').upper()
        member_status = conf_member.get('member_status', 'invalid').upper()
        member_ip = conf_member.get('member_ip', None)
        member_ipv6 = conf_member.get('member_ipv6', None)

        if not member_id:
            raise ib_ex.InfobloxConfigException(
                msg="member_id cannot be empty")
        if not member_name:
            raise ib_ex.InfobloxConfigException(
                msg="member_name cannot be empty")
        if member_type not in [ib_const.MEMBER_TYPE_GRID_MASTER,
                               ib_const.MEMBER_TYPE_CP_MEMBER,
                               ib_const.MEMBER_TYPE_REGULAR_MEMBER]:
            raise ib_ex.InfobloxConfigException(
                msg="Invalid member type: %s" % member_type)
        if member_status not in [ib_const.MEMBER_STATUS_ON,
                                 ib_const.MEMBER_STATUS_OFF]:
            raise ib_ex.InfobloxConfigException(
                msg="Invalid member status: %s" % member_status)
        if member_ip is None and member_ipv6 is None:
            raise ib_ex.InfobloxConfigException(
                msg="No member IP addresses are found.")

        member = {'member_id': member_id,
                  'member_name': member_name,
                  'member_type': member_type,
                  'member_status': member_status,
                  'member_ip': member_ip,
                  'member_ipv6': member_ipv6}
        return ib_utils.json_to_obj('Member', member)

    @staticmethod
    def _get_grid_from_config(conf_grid):
        grid_id = conf_grid.get('grid_id', None)
        grid_name = conf_grid.get('grid_name', None)
        grid_connection = conf_grid.get('grid_connection', None)
        if not grid_id:
            raise ib_ex.InfobloxConfigException(
                msg="grid_id cannot be empty")
        if not grid_name:
            raise ib_ex.InfobloxConfigException(
                msg="grid_name cannot be empty")
        if not grid_connection:
            raise ib_ex.InfobloxConfigException(
                msg="grid_connection cannot be empty")

        connection_info = ib_utils.json_to_obj('grid_connection',
                                               grid_connection)
        valid = False
        if (hasattr(connection_info, 'wapi_version') and
                hasattr(connection_info, 'wapi_ssl_verify') and
                hasattr(connection_info, 'wapi_http_pool_connections') and
                hasattr(connection_info, 'wapi_http_pool_maxsize') and
                hasattr(connection_info, 'wapi_http_request_timeout') and
                hasattr(connection_info, 'wapi_admin_user') and
                hasattr(connection_info, 'wapi_cloud_user')):
            # wapi_admin_user is optional for cloud api but required
            # for pre=hellfire
            if ib_utils.is_cloud_wapi(connection_info.wapi_version):
                valid = (hasattr(connection_info.wapi_cloud_user, 'name') and
                         hasattr(connection_info.wapi_cloud_user, 'password'))
            else:
                valid = (hasattr(connection_info.wapi_admin_user, 'name') and
                         hasattr(connection_info.wapi_admin_user, 'password'))
        if not valid:
            raise ib_ex.InfobloxConfigException(
                msg="Invalid grid connection configuration: %s" %
                    grid_connection)

        grid = {'grid_id': grid_id,
                'grid_name': grid_name,
                'grid_connection': None}
        grid = ib_utils.json_to_obj('grid', grid)
        # grid_connection should be in json string format for db update
        grid.grid_connection = jsonutils.dumps(grid_connection)
        return grid

    def _reserve_next_available_member_for_network(self, grid_id,
                                                   network_view,
                                                   mapping_scope,
                                                   mapping_relation,
                                                   member_type=None):
        session = self._context.session
        avail_member = ib_dbi.get_available_member_for_network(session,
                                                               grid_id,
                                                               member_type)
        if not avail_member:
            raise ib_ex.InfobloxMemberReservationError(
                msg="No Infoblox member available.")

        member = ib_dbi.reserve_member_for_network(session,
                                                   avail_member.member_id,
                                                   network_view,
                                                   mapping_scope,
                                                   mapping_relation)
        return member

    def _reserve_service(self, serviced_members, service_type, network_id,
                         member_id):
        session = self._context.session

        service_members = [m for m in serviced_members
                           if m.member_id == member_id and
                           m.service == service_type and
                           m.network_id == network_id]
        if not service_members:
            reserved_member = ib_dbi.add_member_for_service(
                session,
                member_id,
                service_type,
                network_id)
        else:
            reserved_member = service_members[0]

        return reserved_member


class GridConfigManager(object):
    """
    _variable_conditions: 'tenant_id:', 'subnet_range:'
    _static_conditions: 'global', 'tenant'
    """
    VALID_STATIC_CONDITIONS = ['global', 'tenant']
    VALID_VARIABLE_CONDITIONS = ['tenant:', 'subnet:']
    VALID_CONDITIONS = VALID_STATIC_CONDITIONS + VALID_VARIABLE_CONDITIONS

    def __init__(self, context, config_stream=None):
        """Reads config from `io.IOBase`:stream:. Config is JSON format."""
        self._context = context

        self._variable_conditions = []
        self._static_conditions = []

        self._service_members = dict()
        self._network_members = dict()

        if not config_stream:
            config_file = ib_conf.CONF_IPAM.condition_config
            if not config_file:
                raise ib_ex.InfobloxConfigException(
                    msg="Conditional config not found")
            config_stream = io.FileIO(config_file)

        with config_stream:
            try:
                self._conf = jsonutils.loads(config_stream.read())
            except ValueError as e:
                raise ib_ex.InfobloxConfigException(
                    msg="Conditional => %s" % e)

    @property
    def conditional_conf(self):
        return self._conf

    @property
    def service_members(self):
        return self._service_members

    def sync(self):
        """Synchronizes conditional conf

        Reserve network members that use static network views
        service members are computed and stored and used by
        reserve_service_members in the GridMemberManager because
        network id is not available at this time.

        Note: this does not support network_template
        """
        session = self._context.session
        db_registered_members = ib_dbi.get_members(session)
        registered_members = ib_utils.db_records_to_obj('Member',
                                                        db_registered_members)

        db_reserved_members = ib_dbi.get_reserved_members_for_network(
            session)
        reserved_members = ib_utils.db_records_to_obj('Member',
                                                      db_reserved_members)

        self._read_conditions(registered_members)

        # reserve predefined members for network
        for net_view, dhcp_network in self._network_members.items():
            for member_id in dhcp_network['members']:
                reserved_member_ids = [m.member_id for m in reserved_members
                                       if m.mapping_id == net_view and
                                       m.member_id == member_id]
                if not reserved_member_ids:
                    ib_dbi.reserve_member_for_network(
                        session,
                        member_id,
                        net_view,
                        ib_const.MAPPING_SCOPE_NETWORK_VIEW,
                        dhcp_network['mapping_relation'])

    def get_condition(self, network, subnet):
        """Gets a matching config based on network type whether it is
        a tenant or an external network.
        """
        for conditions in [self._variable_conditions,
                           self._static_conditions]:
            for condition in conditions:
                try:
                    ib_condition = InfobloxCondition(condition, network,
                                                     subnet)
                    if self._condition_matches(ib_condition, network, subnet):
                        return ib_condition
                except ib_ex.InfobloxConfigException as ex:
                    LOG.error(_LE("Invalid configuration found: %s") % ex)
                    raise ex
        raise ib_ex.InfobloxConfigException(
            msg="No config found for subnet %s" % subnet)

    def get_conditions(self, network, subnet):
        """Gets both tenant and external network configurations."""
        ib_conditions = []
        for conditions in [self._variable_conditions,
                           self._static_conditions]:
            for condition in conditions:
                ib_condition = InfobloxCondition(condition, network, subnet)
                ib_conditions.append(ib_condition)
        return ib_conditions

    def _read_conditions(self, registered_members):
        self._network_members.clear()
        self._service_members.clear()

        # define lambdas to check
        is_static_cond = lambda cond, static_conds: cond in static_conds
        is_var_cond = lambda cond, var_conds: any([cond.startswith(valid)
                                                  for valid in var_conds])
        for conf in self._conf:
            conf_condition = conf['condition']
            # if condition contain colon: validate it as variable
            if ':' in conf_condition and \
                is_var_cond(conf['condition'],
                            self.VALID_VARIABLE_CONDITIONS):
                self._variable_conditions.append(conf)
            # if not: validate it as static
            elif is_static_cond(conf_condition,
                                self.VALID_STATIC_CONDITIONS):
                self._static_conditions.append(conf)
            # if any of previous checker cannot validate value - rise error
            else:
                raise ib_ex.InfobloxConfigException(
                    msg='Invalid condition specified: %s' % conf_condition)

            # if network view is static, its owing member must be specified
            # in 'authority_member' which should be a single member.
            # a network view can be either delegated or not delegated.
            # if reversed_member is a grid master, multiple service members be
            # listed but a regular member should service serve dhcp/dns
            # services on itself.
            conf_net_view = conf.get('network_view', 'default')
            conf_authority_member = conf.get('authority_member')
            conf_dhcp_members = conf.get('dhcp_members', None)
            conf_dns_members = conf.get('dns_members', None)
            is_dynamic_net_view = conf_net_view.startswith('{')
            if is_dynamic_net_view:
                self._validate_dynamic_network_view(conf_condition,
                                                    conf_authority_member,
                                                    conf_dhcp_members,
                                                    conf_dns_members)
            else:
                self._validate_static_network_view(conf_condition,
                                                   conf_net_view,
                                                   registered_members,
                                                   conf_authority_member,
                                                   conf_dhcp_members,
                                                   conf_dns_members)
                self._prepare_member_for_network(conf_net_view,
                                                 registered_members,
                                                 conf_authority_member,
                                                 conf_dhcp_members)
                self._prepare_members_for_services(conf['condition'],
                                                   conf_dhcp_members,
                                                   conf_dns_members)

    @staticmethod
    def _validate_static_network_view(condition, net_view,
                                      registered_members, authority_member,
                                      dhcp_members, dns_members):
        if authority_member is None:
            raise ib_ex.InfobloxConfigException(
                msg="From condition (%s), 'authority_member' field is "
                    "missing 'authority_member' for the pre-defined network "
                    "view (%s)." % (condition, net_view))

        if authority_member == ib_const.NEXT_AVAILABLE_MEMBER:
            raise ib_ex.InfobloxConfigException(
                msg="From condition (%s), 'authority_member' cannot be set "
                    "to <next-available-member> for the pre-defined network "
                    "view (%s)." % (condition, net_view))

        if not isinstance(authority_member, six.string_types):
            raise ib_ex.InfobloxConfigException(
                msg="From condition (%s), 'authority_member' (%s) should be "
                    "a string that indicate a member id." %
                    (condition, authority_member))

        reserved_authority_members = [m for m in registered_members
                                      if m.member_id == authority_member]
        if not reserved_authority_members:
            raise ib_ex.InfobloxConfigException(
                msg="From condition (%s), 'authority_member' (%s) is not "
                    "found from the grid member list." % (condition,
                                                          authority_member))

        authority_member_status = reserved_authority_members[0].member_status
        authority_member_type = reserved_authority_members[0].member_type

        if authority_member_status == ib_const.MEMBER_TYPE_REGULAR_MEMBER:
            raise ib_ex.InfobloxConfigException(
                msg="From condition (%s), a REGULAR member "
                    "(%s) cannot be a authority member for the pre-defined "
                    "network (%s)." % (condition, authority_member, net_view))
        if authority_member_status != ib_const.MEMBER_STATUS_ON:
            raise ib_ex.InfobloxConfigException(
                msg="From condition (%s), 'authority_member' (%s) has member "
                    "status OFF." % (condition, authority_member))

        if dhcp_members is None and dns_members is None:
            return True

        # for CP member, dhcp/dns members cannot be <next-available-member>
        # since the member itself serves dhcp/dns.
        if authority_member_type == ib_const.MEMBER_TYPE_CP_MEMBER and \
                (dhcp_members == ib_const.NEXT_AVAILABLE_MEMBER or
                 dns_members == ib_const.NEXT_AVAILABLE_MEMBER):
            raise ib_ex.InfobloxConfigException(
                msg="From condition (%s), 'authority_member' (%s) is a CP "
                    "member so 'dhcp_members' or 'dns_members' cannot be set "
                    "to <next-available-member> for the pre-defined "
                    "network (%s)" % (condition, authority_member, net_view))

        # for GM, dhcp or dns member can be <next-available-member>
        if authority_member_type == ib_const.MEMBER_TYPE_GRID_MASTER and \
                ((dhcp_members == ib_const.NEXT_AVAILABLE_MEMBER and
                  dns_members == ib_const.NEXT_AVAILABLE_MEMBER) or
                 (dhcp_members == ib_const.NEXT_AVAILABLE_MEMBER and
                  dns_members is None) or
                 (dhcp_members is None and
                  dns_members == ib_const.NEXT_AVAILABLE_MEMBER)):
            return True

        # for REGULAR member, dhcp and dns members purely protocols only and
        # dhcp and dns primary is owned by GM. so dhcp and dns members can be
        # predefined or <next-available-member>. however once a dhcp member is
        # reserved, it cannot be used for other dhcp network. this is
        # pre-hellfire behavior. this check can be enforced.
        #
        # authority     network view        dhcp member
        # ---------     ------------        -----------
        # GM            default             GM
        #               nv1                 RM1
        #               nv2                 RM2, RM3
        # CPM1          nv3                 CPM1
        dhcp_list = []
        if dhcp_members:
            if not isinstance(dhcp_members, six.string_types):
                raise ib_ex.InfobloxConfigException(
                    msg="From condition (%s), 'dhcp_members' is optional but "
                        "if specified, it cannot be empty." % condition)

            dhcp_list = ib_utils.get_list_from_string(dhcp_members, [','])
            dhcp_count = len(dhcp_list)

            # CP member can have only one dhcp/dns member
            if authority_member_type == ib_const.MEMBER_TYPE_CP_MEMBER:
                valid_cp_member = (dhcp_count == 1 and
                                   dhcp_list[0] == authority_member)
                if not valid_cp_member:
                    raise ib_ex.InfobloxConfigException(
                        msg="From condition (%s), if 'authority_member' (%s) "
                            "is a CP member, 'dhcp_members' (%s) cannot have "
                            "more than one member and 'authority_member' is "
                            "'dhcp_members' itself." % (condition,
                                                        authority_member,
                                                        dhcp_members))

            # GM itself can service dhcp network for 'default' view or
            # it can have other member(s) serve(s) dhcp network(s) but GM
            # cannot be in the list if multiple members are listed.
            if authority_member_type == ib_const.MEMBER_TYPE_GRID_MASTER:
                gm_found = ib_utils.exists_in_list([authority_member],
                                                   dhcp_list)
                valid_gm_member = (dhcp_count == 1 or
                                   (dhcp_count > 1 and not gm_found))
                if not valid_gm_member:
                    raise ib_ex.InfobloxConfigException(
                        msg="From condition (%(cd)s), if 'authority_member' "
                            "(%(am)s) is a GM, GM can be the dhcp member "
                            "itself or GM can have other members to serve "
                            "dhcp networks but in this case GM cannot be "
                            "included in the dhcp member list."
                            "(%(dm)s)." % {'cd': condition,
                                           'am': authority_member,
                                           'dm': dhcp_members})

            # REGULAR member cannot be authority member and it can only serve
            # dhcp so check is done with GM since GM is the authority member.

            GridConfigManager._validate_reserved_members(
                condition, dhcp_list, registered_members, 'dhcp_members')

        primary_dns_list = []
        if dns_members:
            if not isinstance(dns_members, six.string_types):
                raise ib_ex.InfobloxConfigException(
                    msg="From condition (%s), 'dns_members' is optional but "
                        "if specified, it cannot be empty." % condition)

            dns_list = ib_utils.get_list_from_string(dns_members, [':', ','])
            primary_dns_list = dns_list[0]
            GridConfigManager._validate_reserved_members(
                condition, primary_dns_list, registered_members, 'dns_members')
            if len(dns_list) == 2:
                secondary_dns_list = dns_list[1]
                GridConfigManager._validate_reserved_members(
                    condition, secondary_dns_list, registered_members,
                    'dns_members')

        # for a host record, dhcp member and dns member must match since they
        # cannot have different parent (network view).
        # for a dns record without host record option, dns primary can be
        # different from dhcp member and multiple members can be primary.
        # (multi master dns)
        use_host_record = ib_conf.CONF_IPAM.use_host_records_for_ip_allocation
        if dhcp_list and primary_dns_list and use_host_record:
            matched_members = list(set(dhcp_list).intersection(
                primary_dns_list))
            matched = (len(matched_members) == len(dhcp_list) ==
                       len(primary_dns_list))
            if not matched:
                raise ib_ex.InfobloxConfigException(
                    msg="From condition (%s), dhcp and dns primary member "
                        "must match because host record ip allocation option "
                        "is set in neutron conf." % condition)

        return True

    @staticmethod
    def _validate_reserved_members(condition, member_id_list,
                                   registered_members, member_field):
        for member_id in member_id_list:
            found = False
            for rm in registered_members:
                if member_id == rm.member_id:
                    found = True
                    if rm.member_status != ib_const.MEMBER_STATUS_ON:
                        raise ib_ex.InfobloxConfigException(
                            msg="From condition (%s), '%s' contains member "
                                "(%s) in OFF status" %
                                (condition, member_field, member_id))
                    break
            if not found:
                raise ib_ex.InfobloxConfigException(
                    msg="From condition (%s), '%s' contains member (%s) not "
                        "in the registered grid member list." %
                        (condition, member_field, member_id))
        return True

    @staticmethod
    def _validate_dynamic_network_view(condition, authority_member,
                                       dhcp_members, dns_members):
        # authority_member is mandatory and should be
        # '<next-available-member>' for dynamic network view.
        if authority_member is None:
            raise ib_ex.InfobloxConfigException(
                msg="From condition (%s), 'authority_member' field is "
                    "missing." % condition)

        if authority_member != ib_const.NEXT_AVAILABLE_MEMBER:
            raise ib_ex.InfobloxConfigException(
                msg="From condition (%s), 'authority_member' should be set "
                    "to <next-available-member>." % condition)

        valid_dhcp_member = (dhcp_members is None or dhcp_members ==
                             ib_const.NEXT_AVAILABLE_MEMBER)
        if not valid_dhcp_member:
            raise ib_ex.InfobloxConfigException(
                msg="From condition (%s), 'dhcp_members' is optional but if "
                    "specified, it should be set to "
                    "'<next-available-member>'." % condition)

        valid_dns_member = (dns_members is None or dns_members ==
                            ib_const.NEXT_AVAILABLE_MEMBER)
        if not valid_dns_member:
            raise ib_ex.InfobloxConfigException(
                msg="From condition (%s), 'dns_members' is optional but if "
                    "specified, it should be set to "
                    "'<next-available-member>'." % condition)

        return True

    def _prepare_member_for_network(self, net_view, registered_members,
                                    authority_member, dhcp_members):
        reserved_authority_member = ib_utils.find_one_in_list(
            'member_id', authority_member, registered_members)
        authority_member_type = reserved_authority_member.member_type

        network_members = []
        relation = ib_const.MAPPING_RELATION_CP
        if authority_member_type == ib_const.MEMBER_TYPE_CP_MEMBER:
            network_members.append(authority_member)
        else:
            # authority member is GM
            if dhcp_members is None or \
                    dhcp_members == ib_const.NEXT_AVAILABLE_MEMBER:
                # this is a dynamic dhcp network so nothing to store
                # relation = ib_const.MAPPING_RELATION_GM_DISTRIBUTED
                return

            # dhcp members are predefined
            dhcp_member_ids = ib_utils.get_list_from_string(dhcp_members,
                                                            [','])
            if len(dhcp_member_ids) == 1 and \
                    authority_member == dhcp_member_ids[0]:
                relation = ib_const.MAPPING_RELATION_GM
            else:
                relation = ib_const.MAPPING_RELATION_GM_DISTRIBUTED

            network_members = dhcp_member_ids

        if self._network_members.get(net_view) is None:
            self._network_members[net_view] = {'members': network_members,
                                               'mapping_relation': relation}

    def _prepare_members_for_services(self, condition, dhcp_members,
                                      dns_members):
        """look for members to be reserved for dhcp and dns

        A grid member whose member type is 'member' can only have
        one service member but grid master can have multiple servers for
        services.

        #  DHCP                      DNS                       Action
           -----------------------   -----------------------   ---------
        1. <next-available-member>   <next-available-member>   N/A
        2. [ "member1" ]             <next-available-member>   DHCP
        3. <next-available-member>   [ "member1" ]             DNS
        4. [ "member1" ]             [ "member1" ]             DHCP/DNS
        5. <next-available-member>                             Same as 1
        6.                           <next-available-member>   Same as 1
        7. [ "member1" ]                                       DHCP/DNS
        8.                           [ "member1" ]             Same as 7
        9.                                                     Same as 1

        DHCP and DNS member cannot be different. the following is wrong
        [ "member1" ]             [ "member2" ]             DHCP/DNS
        host record generation will fail because dns zone has different
        parent.
        """
        # case 1, 5, 6, and 9
        if (dhcp_members == ib_const.NEXT_AVAILABLE_MEMBER and
                dns_members == ib_const.NEXT_AVAILABLE_MEMBER) or \
                (dhcp_members == ib_const.NEXT_AVAILABLE_MEMBER and
                    dns_members is None) or \
                (dhcp_members is None and
                    dns_members == ib_const.NEXT_AVAILABLE_MEMBER) or \
                (dhcp_members is None and dns_members is None):
            return

        # case 2
        if isinstance(dhcp_members, list) and \
                dns_members == ib_const.NEXT_AVAILABLE_MEMBER:
            self._update_service_members(condition,
                                         ib_const.SERVICE_TYPE_DHCP,
                                         dhcp_members)
            return

        # case 3
        if dhcp_members == ib_const.NEXT_AVAILABLE_MEMBER and \
                isinstance(dns_members['primary'], list):
            self._update_service_members(condition,
                                         ib_const.SERVICE_TYPE_DNS,
                                         dhcp_members)
            return

        # case 4
        if isinstance(dhcp_members, list) and \
                isinstance(dns_members['primary'], list):
            self._update_service_members(condition,
                                         ib_const.SERVICE_TYPE_DHCP,
                                         dhcp_members)
            self._update_service_members(condition, ib_const.SERVICE_TYPE_DNS,
                                         dns_members)
            return

        # case 7
        if isinstance(dhcp_members, list) and dns_members is None:
            self._update_service_members(condition,
                                         ib_const.SERVICE_TYPE_DHCP,
                                         dhcp_members)
            self._update_service_members(condition, ib_const.SERVICE_TYPE_DNS,
                                         dhcp_members)
            return

        # case 8
        if dhcp_members is None and isinstance(dns_members['primary'], list):
            self._update_service_members(condition,
                                         ib_const.SERVICE_TYPE_DHCP,
                                         dns_members)
            self._update_service_members(condition,
                                         ib_const.SERVICE_TYPE_DNS,
                                         dns_members)
            return

    def _update_service_members(self, condition, service_type, members):
        if self._service_members.get(condition) is None:
            self._service_members[condition] = {service_type: members}
        else:
            self._service_members[condition][service_type] = members

    def _condition_matches(self, condition, network, subnet):
        subnet = subnet if subnet else {}
        network = network if network else {}

        cidr = subnet.get('cidr')
        tenant_id = subnet.get('tenant_id') or network.get('tenant_id')
        is_external = network.get('router:external', False)
        cond = condition.condition

        condition_matches = (
            cond == 'global' or
            cond == 'tenant' or
            self._variable_condition_match(cond, 'tenant_id', tenant_id) or
            self._variable_condition_match(cond, 'subnet_range', cidr)
        )
        return condition.is_external == is_external and condition_matches

    @staticmethod
    def _variable_condition_match(condition, variable, expected):
        return (condition.startswith(variable) and
                condition.split(':')[1] == expected)

    def _set_grid_connection(self, condition):
        session = self._context.session
        db_grids = ib_dbi.get_grids(session, grid_id=condition.grid_id)
        grids = ib_utils.db_records_to_obj('Grid', db_grids)
        if not grids or len(grids) != 1 or \
                grids[0].grid_id != condition.grid_id:
            raise ib_ex.InfobloxMemberReservationError(
                msg="Infoblox grid id '%s' is not found." % condition.grid_id)

        condition.grid_members = grids[0].members
        condition.grid_connection = ib_utils.json_to_obj(
            'Connection', grids[0].grid_connection)


class InfobloxCondition(object):

    NETWORK_VIEW_TEMPLATES = ['{tenant_id}',
                              '{network_name}',
                              '{network_id}']

    CONDITION_ATTRS = ['condition', '_dhcp_members', '_dns_members',
                       'grid_id', '_network_view', '_dns_view',
                       '_authority_member', '_is_external']

    def __init__(self, condition, network, subnet):
        self._subnet = subnet if subnet else {}
        self._network = network if network else {}

        # condition: global or tenant
        self._condition = condition.get('condition', None)
        if self._condition is None:
            raise ib_ex.InfobloxConfigException(
                msg="Missing mandatory 'condition' config option.")

        # grid id
        self._grid_id = condition.get('grid_id', None)
        if self._grid_id is None:
            raise ib_ex.InfobloxConfigException(
                msg="condition '%s' is missing mandatory 'grid_id' config "
                    "option." % self._condition)

        # grid connection info
        self._grid_connection = None
        self._grid_members = None

        # config for external network?
        self._is_external = condition.get('is_external', False)

        # nios mapping
        self._network_view = condition.get('network_view', 'default')
        self._authority_member = condition.get('authority_member',
                                               ib_const.NEXT_AVAILABLE_MEMBER)
        if self._authority_member == ib_const.NEXT_AVAILABLE_MEMBER:
            self._authority_member_type = ib_const.MEMBER_TYPE_CP_MEMBER
            self._mapping_relation = ib_const.MAPPING_RELATION_CP
        else:
            self._authority_member_type = None
            self._mapping_relation = None

        self._network_members = []

        self._dns_view = condition.get('dns_view', 'default')
        self._set_member_mapping()

        # dhcp/dns relay
        self._require_dhcp_relay = condition.get('require_dhcp_relay', False)

        # dhcp members
        self._dhcp_members = condition.get('dhcp_members',
                                           ib_const.NEXT_AVAILABLE_MEMBER)
        if not isinstance(self._dhcp_members, six.string_types):
            raise ib_ex.InfobloxConfigException(
                msg="From condition '%s', 'dhcp_members' must be a "
                    "comma-separated string." % self._condition)
        if self._dhcp_members != ib_const.NEXT_AVAILABLE_MEMBER:
            self._dhcp_members = ib_utils.get_list_from_string(
                self._dhcp_members, [','])

        # dns members
        self._dns_members = condition.get('dns_members',
                                          ib_const.NEXT_AVAILABLE_MEMBER)
        if not isinstance(self._dns_members, six.string_types):
            raise ib_ex.InfobloxConfigException(
                msg="From condition '%s', 'dns_members' must be a "
                    "comma-separated string." % self._condition)
        if self._dns_members != ib_const.NEXT_AVAILABLE_MEMBER:
            dns_list = ib_utils.get_list_from_string(self._dns_members,
                                                     [':', ','])
            if not dns_list or len(dns_list) not in [1, 2]:
                raise ib_ex.InfobloxConfigException(
                    msg="From condition '%s', 'dns_members' cannot be empty "
                        "when specified. 'dns_members' can list primary "
                        "server(s) only or both primary and secondary "
                        "servers with ':' separated" % self._condition)
            # get primary dns members
            primary_dns_members = dns_list[0]
            self._dns_members = {'primary': primary_dns_members,
                                 'secondary': []}
            if len(dns_list) == 2:
                secondary_dns_members = dns_list[1]
                self._dns_members['secondary'] = secondary_dns_members
            overlapping_members = [m for m in self._dns_members['secondary']
                                   if m in self._dns_members['primary']]
            if overlapping_members:
                raise ib_ex.InfobloxConfigException(
                    msg="From condition '%s', 'dns_members' contains "
                        "secondary members that are already listed as "
                        "primary members." % self._condition)

        # extra nios network config
        self._network_template = condition.get('network_template', None)
        self._ns_group = condition.get('ns_group', None)

        # dns configs
        self._domain_suffix_pattern = condition.get(
            'domain_suffix_pattern', 'global.com')
        self._hostname_pattern = condition.get(
            'hostname_pattern', 'host-{ip_address}.{subnet_name}')
        self._determine_domain_suffix_pattern()

        self._pattern_builder = PatternBuilder(self._domain_suffix_pattern,
                                               self._hostname_pattern)

    def __eq__(self, other):
        return (isinstance(other, self.__class__) and
                all(map(lambda attr:
                        getattr(self, attr) == getattr(other, attr),
                        self.CONDITION_ATTRS)))

    def __hash__(self):
        return hash(tuple(self.CONDITION_ATTRS))

    def __repr__(self):
        values = {'condition': self._condition,
                  'ready': self.ready,
                  'is_external': self._is_external,
                  'grid_id': self._grid_id,
                  'grid_connection': self._grid_connection,
                  'grid_members': self._grid_members,
                  'require_dhcp_relay': self._require_dhcp_relay,
                  'network_view': self.network_view,
                  'dns_view': self.dns_view,
                  'authority_member': self._authority_member,
                  'authority_member_type': self._authority_member_type,
                  'mapping_relation': self._mapping_relation,
                  'mapping_scope': self._mapping_scope,
                  'network_members': self._network_members,
                  'dhcp_members': self._dhcp_members,
                  'dns_members': self._dns_members,
                  'domain_suffix_pattern': self._domain_suffix_pattern,
                  'hostname_pattern': self._hostname_pattern,
                  'network_template': self._network_template,
                  'ns_group': self._ns_group}
        return "InfobloxCondition{0}".format(values)

    @property
    def condition(self):
        return self._condition

    @property
    def network(self):
        return self._network

    @property
    def subnet(self):
        return self._subnet

    @property
    def grid_id(self):
        return self._grid_id

    @property
    def grid_connection(self):
        return self._grid_connection

    @grid_connection.setter
    def grid_connection(self, value):
        if value is None:
            raise ValueError('grid_connection cannot be empty.')
        self._grid_connection = value

    @property
    def grid_members(self):
        return self._grid_members

    @grid_members.setter
    def grid_members(self, value):
        if value is None or not isinstance(value, list):
            raise ValueError('grid_members must be a list and '
                             'cannot be empty.')
        self._grid_members = value

    @property
    def is_global_config(self):
        return self.condition == 'global'

    @property
    def is_external(self):
        return self._is_external

    @property
    def require_dhcp_relay(self):
        return self._require_dhcp_relay

    @property
    def network_view(self):
        return self._network_view

    @property
    def ready(self):
        return self._authority_member != ib_const.NEXT_AVAILABLE_MEMBER

    @property
    def authority_member(self):
        return self._authority_member

    @authority_member.setter
    def authority_member(self, value):
        self._authority_member = value

    @property
    def authority_member_type(self):
        return self._authority_member_type

    @authority_member_type.setter
    def authority_member_type(self, value):
        self._authority_member_type = value

    @property
    def mapping_relation(self):
        return self._mapping_relation

    @mapping_relation.setter
    def mapping_relation(self, value):
        self._mapping_relation = value

    @property
    def mapping_scope(self):
        return self._mapping_scope

    @property
    def dns_view(self):
        if self._network_view == 'default':
            return self._dns_view
        return '.'.join([self._dns_view, self._network_view])

    @property
    def dhcp_members(self):
        return self._dhcp_members

    @dhcp_members.setter
    def dhcp_members(self, value):
        self._dhcp_members = value

    @property
    def dns_members(self):
        return self._dns_members

    @dns_members.setter
    def dns_members(self, value):
        self._dns_members = value

    @property
    def network_members(self):
        return self._network_members

    @network_members.setter
    def network_members(self, value):
        self._network_members = value

    @property
    def domain_suffix_pattern(self):
        return self._domain_suffix_pattern

    @property
    def is_static_domain_suffix(self):
        return self._is_static_domain_suffix

    @property
    def hostname_pattern(self):
        return self._hostname_pattern

    @property
    def network_template(self):
        return self._network_template

    @property
    def ns_group(self):
        return self._ns_group

    @property
    def pattern_builder(self):
        return self._pattern_builder

    def _set_member_mapping(self):
        if self._network_view.startswith('{') and \
                self._network_view not in self.NETWORK_VIEW_TEMPLATES:
            raise ib_ex.InfobloxConfigException(
                msg="Invalid config value for 'network_view'")

        net_view = self._network_view
        scope = ib_const.MAPPING_SCOPE_NETWORK_VIEW

        if self._network_view == '{tenant_id}':
            scope = ib_const.MAPPING_SCOPE_TENANT_ID
            net_view = (self._subnet.get('tenant_id') or
                        self._network.get('tenant_id'))
        elif self._network_view == '{network_name}':
            scope = ib_const.MAPPING_SCOPE_NETWORK_NAME
            net_view = self._network.get('name', None)
        elif self._network_view == '{network_id}':
            scope = ib_const.MAPPING_SCOPE_NETWORK_ID
            net_view = (self._subnet.get('network_id')or
                        self._network.get('id'))

        self._mapping_scope = scope
        self._network_view = net_view

    def _determine_domain_suffix_pattern(self):
        pattern = re.compile(r'\{\S+\}')
        if pattern.findall(self._domain_suffix_pattern):
            self._is_static_domain_suffix = False
        else:
            self._is_static_domain_suffix = True


class PatternBuilder(object):

    def __init__(self, domain_suffix_pattern, hostname_pattern):
        self.domain_suffix_pattern = domain_suffix_pattern
        self.hostname_pattern = hostname_pattern

    def build_hostname(self, network, subnet, port, ip_address,
                       instance_name=None):
        hostname_pattern = self.hostname_pattern
        port_owner = port['device_owner']
        if port_owner == n_const.DEVICE_OWNER_FLOATINGIP:
            if instance_name and "{instance_name}" in self.hostname_pattern:
                return self.hostname_pattern
        if port_owner in ib_const.NEUTRON_DEVICE_OWNER_TO_PATTERN_MAP.keys():
            hostname_pattern = \
                ib_const.NEUTRON_DEVICE_OWNER_TO_PATTERN_MAP[port_owner]

        pattern = [hostname_pattern, self.domain_suffix_pattern]
        pattern = '.'.join([el.strip('.') for el in pattern if el])
        self._build(pattern, network, subnet, port, ip_address, instance_name)

    def build_zone_name(self, network, subnet):
        pattern = self.domain_suffix_pattern
        self._build(pattern, network, subnet)

    def _build(self, pattern, network, subnet, port=None, ip_addr=None,
               instance_name=None):
        self._validate_pattern(pattern)

        subnet_name = subnet['name'] if subnet['name'] else subnet['id']
        pattern_dict = {
            'network_id': subnet['network_id'],
            'network_name': network.get('name'),
            'tenant_id': subnet['tenant_id'],
            'subnet_name': subnet_name,
            'subnet_id': subnet['id']
        }

        if ip_addr:
            octets = ip_addr.split('.')
            ip_addr = ip_addr.replace('.', '-').replace(':', '-')
            pattern_dict['ip_address'] = ip_addr
            for i in range(len(octets)):
                octet_key = 'ip_address_octet{i}'.format(i=(i + 1))
                pattern_dict[octet_key] = octets[i]

        if port:
            pattern_dict['port_id'] = port['id']
            pattern_dict['instance_id'] = port['device_id']
            if instance_name:
                pattern_dict['instance_name'] = instance_name

        try:
            fqdn = pattern.format(**pattern_dict)
        except (KeyError, IndexError) as e:
            raise ib_ex.InfobloxConfigException(
                msg="Invalid pattern %s" % e)

        return fqdn

    @staticmethod
    def _validate_pattern(pattern):
        invalid_values = ['..']
        for val in invalid_values:
            if val in pattern:
                error_message = "Invalid pattern value {0}".format(val)
                raise ib_ex.InfobloxConfigException(msg=error_message)
