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

from infoblox_client import connector

from networking_infoblox.neutron.common import config as cfg
from networking_infoblox.neutron.common import constants as const
from networking_infoblox.neutron.common import exceptions as exc
from networking_infoblox.neutron.common import mapping as grid_mapping
from networking_infoblox.neutron.common import member as grid_member
from networking_infoblox.neutron.common import utils
from networking_infoblox.neutron.db import infoblox_db as dbi


LOG = logging.getLogger(__name__)


class GridManager(object):

    grid_config = None
    connector = None
    member = None
    mapping = None

    def __init__(self, context):
        self.grid_config = self._create_grid_configuration(context)
        self.member = grid_member.GridMemberManager(self.grid_config)
        self.mapping = grid_mapping.GridMappingManager(self.grid_config)

    def sync(self):
        """Synchronize members, config, and mapping between NIOS and neutron.

        First sync members, then config, and lastly mapping because config
        sync needs GM info and mapping needs grid config.
        """
        self.member.sync()
        self.grid_config.sync()
        self.mapping.sync()

    def get_config(self):
        """Gets grid configuration.

        Before this call is made, the grid member must be in sync.
        """
        self.grid_config.sync()
        return self.grid_config

    def _create_grid_configuration(self, context):
        grid_conf = GridConfiguration(context)
        grid_conf.grid_id = cfg.CONF.infoblox.cloud_data_center_id
        grid_opts = cfg.get_infoblox_grid_opts(grid_conf.grid_id)
        grid_conf.grid_name = grid_opts['data_center_name']
        grid_conf.grid_master_host = grid_opts['grid_master_host']
        grid_conf.admin_username = grid_opts['admin_user_name']
        grid_conf.admin_password = grid_opts['admin_password']
        grid_conf.wapi_version = grid_opts['wapi_version']
        grid_conf.ssl_verify = grid_opts['ssl_verify']
        grid_conf.http_request_timeout = grid_opts['http_request_timeout']
        grid_conf.http_pool_connections = grid_opts['http_pool_connections']
        grid_conf.http_pool_maxsize = grid_opts['http_pool_maxsize']

        # create connector to GM
        admin_opts = {
            'host': grid_conf.grid_master_host,
            'username': grid_conf.admin_username,
            'password': grid_conf.admin_password,
            'wapi_version': grid_conf.wapi_version,
            'ssl_verify': grid_conf.ssl_verify,
            'http_request_timeout': grid_conf.http_request_timeout,
            'http_pool_connections': grid_conf.http_pool_connections,
            'http_pool_maxsize': grid_conf.http_pool_maxsize}
        grid_conf.gm_connector = connector.Connector(admin_opts)
        return grid_conf


class GridConfiguration(object):

    property_to_ea_mapping = {
        'default_network_view_scope':
            const.EA_GRID_CONFIG_DEFAULT_NETWORK_VIEW_SCOPE,
        'default_network_view': const.EA_GRID_CONFIG_DEFAULT_NETWORK_VIEW,
        'default_host_name_pattern':
            const.EA_GRID_CONFIG_DEFAULT_HOST_NAME_PATTERN,
        'default_domain_name_pattern':
            const.EA_GRID_CONFIG_DEFAULT_DOMAIN_NAME_PATTERN,
        'default_ns_group': const.EA_GRID_CONFIG_DEFAULT_NS_GROUP,
        'admin_network_deletion': const.EA_GRID_CONFIG_ADMIN_NETWORK_DELETION,
        'ip_allocation_strategy': const.EA_GRID_CONFIG_IP_ALLOCATION_STRATEGY,
        'dns_record_binding_types':
            const.EA_GRID_CONFIG_DNS_RECORD_BINDING_TYPES,
        'dns_record_unbinding_types':
            const.EA_GRID_CONFIG_DNS_RECORD_UNBINDING_TYPES,
        'dns_record_removable_types':
            const.EA_GRID_CONFIG_DNS_RECORD_REMOVABLE_TYPES,
        'dhcp_replay_management_network_view':
            const.EA_GRID_CONFIG_DHCP_RELAY_MANAGEMENT_NETWORK_VIEW,
        'dhcp_replay_management_network':
            const.EA_GRID_CONFIG_DHCP_RELAY_MANAGEMENT_NETWORK
    }

    def __init__(self, context):
        self.context = context

        # grid info from neutron conf
        self.grid_id = None
        self.grid_name = None
        self.grid_master_host = None

        # grid connection from neutron conf
        self.admin_username = None
        self.admin_password = None
        self.cloud_username = None
        self.cloud_user_password = None
        self.ssl_verify = False
        self.http_request_timeout = 120
        self.http_pool_connections = 100
        self.http_pool_maxsize = 100

        # connector object to GM
        self.gm_connector = None

        self._wapi_version = None
        self._is_cloud_wapi = False

        # default settings from nios grid master
        self.default_network_view_scope = const.NETWORK_VIEW_SCOPE_SINGLE
        self.default_network_view = 'default'
        self.default_host_name_pattern = 'host-{ip_address}'
        self.default_domain_name_pattern = '{subnet_id}.cloud.global.com'
        self.default_ns_group = None
        self.admin_network_deletion = False
        self.ip_allocation_strategy = const.IP_ALLOCATION_STRATEGY_HOST_RECORD
        self.dns_record_binding_types = []
        self.dns_record_unbinding_types = []
        self.dns_record_removable_types = []
        self.dhcp_replay_management_network_view = None
        self.dhcp_replay_management_network = None

    @property
    def wapi_version(self):
        return self._wapi_version

    @wapi_version.setter
    def wapi_version(self, value):
        self._wapi_version = value
        if value:
            self._is_cloud_wapi = connector.Connector.is_cloud_wapi(value)

    @property
    def is_cloud_wapi(self):
        return self._is_cloud_wapi

    def sync(self):
        session = self.context.session
        members = dbi.get_members(session,
                                  grid_id=self.grid_id,
                                  member_type=const.MEMBER_TYPE_GRID_MASTER)
        if not members or len(members) != 1:
            raise exc.InfobloxCannotFindMember(member="GM")

        discovered_config = self._discover_config(members[0])
        if discovered_config and discovered_config.get('extattrs'):
            self._update_fields(discovered_config)

    def get_grid_connection(self):
        grid_connection = {
            "wapi_version": self.wapi_version,
            "ssl_verify": self.ssl_verify,
            "http_pool_connections": self.http_pool_connections,
            "http_pool_maxsize": self.http_pool_maxsize,
            "http_request_timeout": self.http_request_timeout,
            "admin_user": {"name": self.admin_username,
                           "password": self.admin_password},
            "cloud_user": {"name": self.cloud_username,
                           "password": self.cloud_user_password}
        }
        return grid_connection

    def _discover_config(self, gm_member):
        return_fields = ['extattrs']
        if self._grid_config.is_cloud_wapi:
            return_fields.append('ipv6_setting')

        obj_type = "member/%s:%s" % (gm_member['member_id'],
                                     gm_member['member_name'])
        config = self.gm_connector.get_object(
            obj_type, return_fields=return_fields)
        return config

    def _update_fields(self, extattr):
        for property in self.property_to_ea_mapping:
            self._update_from_ea(property,
                                 self.property_to_ea_mapping[property],
                                 extattr)

    def _update_from_ea(self, field, ea_name, extattrs):
        value = utils.get_ea_value(ea_name, extattrs)
        if value:
            setattr(self, field, value)
