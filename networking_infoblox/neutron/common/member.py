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
from oslo_serialization import jsonutils

from networking_infoblox.neutron.common import constants as const
from networking_infoblox.neutron.common import utils
from networking_infoblox.neutron.db import infoblox_db as dbi


class GridMemberManager(object):

    def __init__(self, grid_config):
        self._grid_config = grid_config
        self._context = self._grid_config.context
        self._connector = self._grid_config.gm_connector

    def sync(self):
        """Discover and sync the active grid and its members."""
        self.sync_grid()
        self.sync_members()

    def sync_grid(self):
        """Synchronize an active grid.

        Only one active grid should be kept where grid_status is set to 'ON'.
        """
        session = self._context.session
        grid_connection = self._grid_config.get_grid_connection()
        grid_connection_json = jsonutils.dumps(grid_connection)

        db_grids = dbi.get_grids(session)
        db_grid_ids = utils.get_values_from_records('grid_id', db_grids)

        # update the existing grid or add new grid
        if self._grid_config.grid_id in db_grid_ids:
            dbi.update_grid(session,
                            self._grid_config.grid_id,
                            self._grid_config.grid_name,
                            grid_connection_json,
                            const.GRID_STATUS_ON)
        else:
            dbi.add_grid(session,
                         self._grid_config.grid_id,
                         self._grid_config.grid_name,
                         grid_connection_json,
                         const.GRID_STATUS_ON,
                         utils.get_hash())

        # deleting grids are delicate operation so we won't allow it
        # but we will set grid status to OFF to unused grids.
        persisted_set = set(db_grid_ids)
        disable_set = persisted_set.difference([self._grid_config.grid_id])
        disabling_grid_ids = list(disable_set)
        for grid_id in disabling_grid_ids:
            dbi.update_grid(session,
                            grid_id,
                            grid_status=const.GRID_STATUS_OFF)
        session.flush()

    def sync_members(self):
        """Synchronizes grid members.

        Members in the active grid are discovered from NIOS backend and
        grid members are in sync in neutron db. The members who are no longer
        in used are set to 'OFF' status.
        """
        session = self._context.session
        grid_id = self._grid_config.grid_id

        db_grids = dbi.get_grids(session)
        db_grid = utils.find_one_in_list('grid_id', grid_id, db_grids)
        gm_member_id = db_grid.gm_id

        db_members = dbi.get_members(session, grid_id=grid_id)
        gm_member = utils.find_one_in_list('member_id', gm_member_id,
                                           db_members)

        discovered_members = self._discover_members()
        if not discovered_members:
            return

        dns_member_settings = self._discover_dns_settings()
        dhcp_member_settings = self._discover_dhcp_settings()

        discovered_licenses = self._discover_member_licenses()

        discovered_member_ids = []

        for member in discovered_members:
            member_name = member['host_name']
            member_ip, member_ipv6 = self._get_lan1_ips(member)
            member_wapi = member_ip if member_ip else member_ipv6
            member_hwid = member['node_info'][0].get('hwid')
            member_status = self._get_member_status(
                member['node_info'][0]['service_status'])
            member_type = self._get_member_type(discovered_licenses,
                                                member_name,
                                                member_hwid)

            require_db_update = False
            if member_type == const.MEMBER_TYPE_GRID_MASTER:
                if gm_member:
                    require_db_update = True
                member_id = gm_member_id
                member_wapi = self._grid_config.grid_master_host
            else:
                # no need to process 'Is Cloud Member' flag for non GM members
                ea_is_cloud_member = utils.get_ea_value(
                    const.EA_IS_CLOUD_MEMBER, member)
                is_cloud_member = (types.Boolean()(ea_is_cloud_member)
                                   if ea_is_cloud_member else False)
                if not is_cloud_member:
                    continue

                db_member = utils.find_one_in_list('member_name', member_name,
                                                   db_members)
                if db_member:
                    require_db_update = True
                    member_id = db_member.member_id
                else:
                    member_id = utils.get_hash(str(grid_id) + member_name)

            member_dhcp_ip, member_dhcp_ipv6 = self._get_dhcp_ips(
                member, dhcp_member_settings)
            member_dns_ip, member_dns_ipv6 = self._get_dns_ips(
                member, dns_member_settings)

            if require_db_update:
                dbi.update_member(session,
                                  member_id,
                                  grid_id,
                                  member_name,
                                  member_ip,
                                  member_ipv6,
                                  member_type,
                                  member_status,
                                  member_dhcp_ip,
                                  member_dhcp_ipv6,
                                  member_dns_ip,
                                  member_dns_ipv6,
                                  member_wapi)
            else:
                dbi.add_member(session,
                               member_id,
                               grid_id,
                               member_name,
                               member_ip,
                               member_ipv6,
                               member_type,
                               member_status,
                               member_dhcp_ip,
                               member_dhcp_ipv6,
                               member_dns_ip,
                               member_dns_ipv6,
                               member_wapi)

            discovered_member_ids.append(member_id)

        # deleting members are delicate operation so we won't allow it
        # but we will set member status to OFF to unused members.
        db_member_ids = utils.get_values_from_records('member_id', db_members)
        persisted_set = set(db_member_ids)
        discovered_set = set(discovered_member_ids)
        disable_set = persisted_set.difference(discovered_set)
        disabling_member_ids = list(disable_set)
        for member_id in disabling_member_ids:
            dbi.update_member(session,
                              member_id,
                              grid_id,
                              member_status=const.MEMBER_STATUS_OFF)
        session.flush()

    def _discover_members(self):
        return_fields = ['node_info', 'host_name', 'vip_setting', 'extattrs']
        # ipv6_setting, lan2_port_setting and mgmt_port_setting fields are
        # available with wapi 2.2+, so check only 'member_ipv6_setting' feature
        if utils.get_features(
                self._grid_config.wapi_version).member_ipv6_setting:
            return_fields.extend(['ipv6_setting', 'lan2_port_setting',
                                  'mgmt_port_setting'])

        members = self._connector.get_object('member',
                                             return_fields=return_fields)
        return members

    def _discover_dns_settings(self):
        members = {}
        # all this info available only with wapi 2.3+
        features = utils.get_features(self._grid_config.wapi_version)
        if not features.dns_settings:
            return members

        return_fields = ['host_name', 'use_mgmt_port', 'use_mgmt_ipv6_port',
                         'use_lan_port', 'use_lan_ipv6_port', 'use_lan2_port',
                         'use_lan2_ipv6_port', 'additional_ip_list']
        dns_members = self._connector.get_object('member:dns',
                                                 return_fields=return_fields)
        # Convert members into dict with host_name as a key
        if dns_members:
            return {member['host_name']: member for member in dns_members}
        return members

    def _discover_dhcp_settings(self):
        members = {}
        # enable_dhcp available only with wapi 2.2.1+
        features = utils.get_features(self._grid_config.wapi_version)
        if not features.enable_dhcp:
            return members

        return_fields = ['host_name', 'enable_dhcp']
        dhcp_members = self._connector.get_object('member:dhcpproperties',
                                                  return_fields=return_fields)
        # Convert members into dict with host_name as a key
        if dhcp_members:
            return {member['host_name']: member for member in dhcp_members}
        return members

    def _get_lan1_ips(self, member):
        member_ip = member['vip_setting']['address']
        member_ipv6 = (member['ipv6_setting'].get('virtual_ip')
                       if member.get('ipv6_setting') else None)
        return member_ip, member_ipv6

    def _get_dhcp_ips(self, member, dhcp_member_settings):
        member_dhcp_ip = None
        member_dhcp_ipv6 = None
        member_name = member['host_name']
        member_ip, member_ipv6 = self._get_lan1_ips(member)

        if member_name in dhcp_member_settings:
            # Use LAN1 interface if enable_dhcp is turned on or LAN2 is
            # not configured
            l2 = member.get('lan2_port_setting')
            if dhcp_member_settings[member_name].get('enable_dhcp') or not l2:
                member_dhcp_ip = member_ip
                member_dhcp_ipv6 = member_ipv6
            else:
                if l2.get('network_setting'):
                    member_dhcp_ip = l2['network_setting'].get('address')
                if l2.get('v6_network_setting'):
                    member_dhcp_ipv6 = l2['v6_network_setting'].get(
                        'virtual_ip')
        return member_dhcp_ip, member_dhcp_ipv6

    def _get_dns_ips(self, member, dns_member_settings):
        member_dns_ip = None
        member_dns_ipv6 = None
        member_name = member['host_name']
        member_ip, member_ipv6 = self._get_lan1_ips(member)

        if member_name in dns_member_settings:
            dns_settings = dns_member_settings[member_name]
            # Assign IPv4 address
            if dns_settings.get('use_lan_port'):
                member_dns_ip = member_ip
            elif dns_settings.get('use_lan2_port'):
                l2 = member.get('lan2_port_setting')
                if l2 and l2.get('network_setting'):
                    member_dns_ip = l2['network_setting'].get('address')
            elif dns_settings.get('use_mgmt_port'):
                n_info = member.get('node_info')
                if n_info and n_info[0].get('mgmt_network_setting'):
                    member_dns_ip = n_info[0]['mgmt_network_setting'].get(
                        'address')
            elif dns_settings.get('additional_ip_list'):
                for ip in dns_settings.get('additional_ip_list'):
                    if utils.get_ip_version(ip) == 4:
                        member_dns_ip = ip
                        break

            # If ip is still blank fallback to member ip
            if not member_dns_ip:
                member_dns_ip = member_ip

            # Assign IPv6 address
            if dns_settings.get('use_lan_ipv6_port'):
                member_dns_ipv6 = member_ipv6
            elif dns_settings.get('use_lan2_ipv6_port'):
                l2 = member.get('lan2_port_setting')
                if l2 and l2.get('v6_network_setting'):
                    member_dns_ipv6 = l2['v6_network_setting'].get(
                        'virtual_ip')
            elif dns_settings.get('use_mgmt_ipv6_port'):
                n_info = member.get('node_info')
                if n_info and n_info[0].get('v6_mgmt_network_setting'):
                    member_dns_ipv6 = n_info[0]['v6_mgmt_network_setting'].get(
                        'virtual_ip')
            elif dns_settings.get('additional_ip_list'):
                for ip in dns_settings.get('additional_ip_list'):
                    if utils.get_ip_version(ip) == 6:
                        member_dns_ipv6 = ip
                        break

            # If ipv6 is still blank fallback to member ipv6
            if not member_dns_ipv6:
                member_dns_ipv6 = member_ipv6

        return member_dns_ip, member_dns_ipv6

    def _discover_member_licenses(self):
        if not utils.get_features(
                self._grid_config.wapi_version).member_licenses:
            return None

        return_fields = ['expiry_date', 'hwid', 'kind', 'type']
        licenses = self._connector.get_object('member:license',
                                              return_fields=return_fields)
        return licenses

    def _get_gm_info(self):
        """Get detail GM info.

        'grid_master_host' configuration accepts host IP or name of GM, so
        we need to figure whether hostname is used or ip address for either
        ipv4 or ipv6.
        """
        gm_ipv4 = None
        gm_ipv6 = None
        gm_hostname = None

        gm_host = self._grid_config.grid_master_host
        if utils.is_valid_ip(gm_host):
            ip_version = utils.get_ip_version(gm_host)
            if ip_version == 4:
                gm_ipv4 = gm_host
            else:
                gm_ipv6 = gm_host
        else:
            gm_hostname = gm_host

        return {'ipv4': gm_ipv4, 'ipv6': gm_ipv6, 'host': gm_hostname}

    def _get_member_status(self, member_service_status):
        node_status = None
        for ns in member_service_status:
            if ns['service'] == 'NODE_STATUS':
                node_status = ns['status']
                break
        return utils.get_member_status(node_status)

    def _get_member_type(self, member_licenses, member_name, member_hwid):
        if self._grid_config.grid_master_name == member_name:
            return const.MEMBER_TYPE_GRID_MASTER

        # member is not GM, so figure out whether the member is CPM or REGULAR
        # for cloud, 'CLOUD_API' license must exist to qualify for CPM
        member_type = const.MEMBER_TYPE_REGULAR_MEMBER
        found_cloud_license = False
        if self._grid_config.is_cloud_wapi and member_licenses:
            for ml in member_licenses:
                if (ml['hwid'] == member_hwid and
                        ml['type'] == const.MEMBER_LICENSE_TYPE_CLOUD_API):
                    found_cloud_license = True
                    break
            if found_cloud_license:
                member_type = const.MEMBER_TYPE_CP_MEMBER

        return member_type
