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

from oslo_log import log as logging
from oslo_serialization import jsonutils

from networking_infoblox.neutron.common import constants as const
from networking_infoblox.neutron.common import utils
from networking_infoblox.neutron.db import infoblox_db as dbi


LOG = logging.getLogger(__name__)


class GridMemberManager(object):

    def __init__(self, context, connector, grid_config):
        self._context = context
        self._connector = connector
        self._grid_config = grid_config

    def sync(self):
        """Discover and sync the active grid and its members."""
        self.sync_grid()
        self.sync_members()

    def sync_grid(self):
        """Synchronize an active grid.

        Only one active grid should be kept where grid_status is set to 'ON'.
        """
        session = self._context.session
        grid_connection = self._get_grid_connection()

        db_grids = dbi.get_grids(session)
        db_grid_ids = utils.get_values_from_records('grid_id', db_grids)

        # update the existing grid or add new grid
        if self._grid_config.grid_id in db_grid_ids:
            dbi.update_grid(session,
                            self._grid_config.grid_id,
                            self._grid_config.grid_name,
                            grid_connection,
                            const.GRID_STATUS_ON)
        else:
            dbi.add_grid(session,
                         self._grid_config.grid_id,
                         self._grid_config.grid_name,
                         grid_connection,
                         const.GRID_STATUS_ON)

        # deleting grids are delicate operation so we won't allow it
        # but we will set grid status to OFF to unused grids.
        persisted_set = set(db_grid_ids)
        current_set = set([self._grid_config.grid_id])
        disable_set = persisted_set.difference(current_set)
        disabling_grid_ids = list(disable_set)
        for grid_id in disabling_grid_ids:
            dbi.update_grid(session,
                            grid_id,
                            grid_status=const.GRID_STATUS_OFF)
        session.flush()

    def _get_grid_connection(self):
        grid_connection = {
            "wapi_version": self._grid_config.wapi_version,
            "ssl_verify": self._grid_config.ssl_verify,
            "http_pool_connections": self._grid_config.http_pool_connections,
            "http_pool_maxsize": self._grid_config.http_pool_maxsize,
            "http_request_timeout": self._grid_config.http_request_timeout,
            "admin_user": {"name": self._grid_config.admin_username,
                           "password": self._grid_config.admin_password},
            "cloud_user": {"name": self._grid_config.cloud_username,
                           "password": self._grid_config.cloud_user_password}
        }
        return jsonutils.dumps(grid_connection)

    def sync_members(self):
        """Synchronizes grid members.

        Members in the active grid are discovered from NIOS backend and
        grid members are in sync in neutron db. The members who are no longer
        in used are set to 'OFF' status.
        """
        session = self._context.session

        db_members = dbi.get_members(session,
                                     grid_id=self._grid_config.grid_id)
        db_member_ids = utils.get_values_from_records('member_id',
                                                      db_members)

        discovered_members = self._discover_members()
        if not discovered_members:
            return

        discovered_licenses = self._discover_member_licenses()

        gm_info = self._get_gm_info()
        discovered_member_ids = []

        for member in discovered_members:
            # get member attributes
            member_id = utils.get_oid_from_nios_ref(member['_ref'])
            member_name = member['host_name']
            member_ipv4 = member['vip_setting']['address']
            member_ipv6 = member['ipv6_setting'].get('virtual_ip') \
                if member.get('ipv6_setting') else None
            node_status = None
            for ns in member['node_info'][0]['service_status']:
                if ns['service'] == 'NODE_STATUS':
                    node_status = ns['status']
                    break
            member_hwid = member['node_info'][0].get('hwid')
            member_status = utils.get_member_status(node_status)
            member_type = self._get_member_type(gm_info,
                                                discovered_licenses,
                                                member_hwid,
                                                member_name,
                                                member_ipv4,
                                                member_ipv6)

            # update the existing member or add a new member
            if member_id in db_member_ids:
                dbi.update_member(session,
                                  member_id,
                                  self._grid_config.grid_id,
                                  member_name,
                                  member_ipv4,
                                  member_ipv6,
                                  member_type,
                                  member_status)
            else:
                dbi.add_member(session,
                               member_id,
                               self._grid_config.grid_id,
                               member_name,
                               member_ipv4,
                               member_ipv6,
                               member_type,
                               member_status)

            discovered_member_ids.append(member_id)

        # deleting members are delicate operation so we won't allow it
        # but we will set member status to OFF to unused members.
        persisted_set = set(db_member_ids)
        discovered_set = set(discovered_member_ids)
        disable_set = persisted_set.difference(discovered_set)
        disabling_member_ids = list(disable_set)
        for member_id in disabling_member_ids:
            dbi.update_member(session,
                              member_id,
                              self._grid_config.grid_id,
                              member_status=const.MEMBER_STATUS_OFF)
        session.flush()

    def _discover_members(self):
        return_fields = ['node_info', 'host_name', 'vip_setting']
        if self._grid_config.is_cloud_wapi:
            return_fields.append('ipv6_setting')

        members = self._connector.get_object('member',
                                             return_fields=return_fields)
        return members

    def _discover_member_licenses(self):
        if not self._grid_config.is_cloud_wapi:
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

    def _get_member_type(self, gm_info, member_licenses, member_hwid,
                         member_name, member_ipv4, member_ipv6):
        # figure out GM from gm configuration from neutron conf
        if (gm_info['ipv4'] and gm_info['ipv4'] == member_ipv4) or \
                (gm_info['ipv6'] and gm_info['ipv6'] == member_ipv6) or \
                (gm_info['host'] and gm_info['host'] == member_name):
            return const.MEMBER_TYPE_GRID_MASTER

        # member is not GM, so figure out whether the member is CPM or REGULAR
        # for cloud, 'CLOUD_API' license must exist to qualify for CPM
        member_type = const.MEMBER_TYPE_REGULAR_MEMBER
        found_cloud_license = False
        if self._grid_config.is_cloud_wapi and member_licenses:
            for license in member_licenses:
                if license['hwid'] == member_hwid and \
                        license['type'] == const.MEMBER_LICENSE_TYPE_CLOUD_API:
                    found_cloud_license = True
                    break
            if found_cloud_license:
                member_type = const.MEMBER_TYPE_CP_MEMBER

        return member_type
