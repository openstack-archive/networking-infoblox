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

from infoblox_client import connector
from infoblox_client import object_manager as obj_mgr

from networking_infoblox.neutron.common import constants as const
from networking_infoblox.neutron.common import utils
from networking_infoblox.neutron.db import infoblox_db as dbi


LOG = logging.getLogger(__name__)


class InfobloxContext(object):

    def __init__(self, neutron_context, user_id, network, subnet, grid_config,
                 grid_members=None, network_views=None,
                 mapping_conditions=None):
        self.context = neutron_context
        self.user_id = user_id
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
             'authority_member': None}
        )

        self._discovered_grid_members = grid_members
        self._discovered_network_views = network_views
        self._discovered_mapping_conditions = mapping_conditions

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

    def update(self):
        """Finds mapping and load managers that can interact with NIOS grid."""
        if self.network:
            if self.subnet:
                self._find_mapping()
            self._load_managers()

    def reserve_authority_member(self):
        """Reserves the next available authority member.

        Find the next available authority member and reserve it, then
        update mapping metadata and load managers if the authority member is
        CPM.
        :return: None
        """
        pass

    def _load_managers(self):
        self.connector = self._get_connector()
        self.ibom = obj_mgr.InfobloxObjectManager(self.connector)
        self.ip_alloc = None

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

        cpm_memeber_ip = (self.mapping.authority_member.member_ip
                          if self.mapping.authority_member.member_ip
                          else self.mapping.authority_member.member_ipv6)

        cloud_user = grid_connection['cloud_user'].get('name')
        cloud_pwd = grid_connection['cloud_user'].get('password')
        opts = {
            'host': cpm_memeber_ip,
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
