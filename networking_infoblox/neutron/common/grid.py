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
    context = None
    grid_config = None
    connector = None
    member = None
    mapping = None

    def __init__(self, context):
        self.context = context
        self.connector = self._create_connector()
        self.grid_config = self._create_grid_configuration()
        self.member = grid_member.GridMemberManager(context, self.connector,
                                                    self.grid_config)
        self.mapping = grid_mapping.GridMappingManager(context, self.connector,
                                                       self.grid_config)

    def sync(self):
        """Synchronize members, config, and mapping between NIOS and neutron.

        First sync members, then config, and lastly mapping because config
        sync needs GM info and mapping needs grid config.
        """
        self.member.sync()
        self.grid_config.sync()
        self.mapping.sync()

    def _create_connector(self):
        opts = {'host': cfg.CONF_DC['grid_master_host'],
                'username': cfg.CONF_DC['admin_user_name'],
                'password': cfg.CONF_DC['admin_password'],
                'wapi_version': cfg.CONF_DC['wapi_version'],
                'ssl_verify': cfg.CONF_DC['ssl_verify'],
                'http_request_timeout': cfg.CONF_DC['http_request_timeout'],
                'http_pool_connections': cfg.CONF_DC['http_pool_connections'],
                'http_pool_maxsize': cfg.CONF_DC['http_pool_maxsize']}
        return connector.Connector(opts)

    def _create_grid_configuration(self):
        grid_conf = GridConfiguration(self.context, self.connector)
        grid_conf.grid_id = cfg.CONF_IPAM.cloud_data_center_id
        grid_conf.grid_name = cfg.CONF_DC['data_center_name']
        grid_conf.grid_master_host = cfg.CONF_DC['grid_master_host']
        grid_conf.admin_username = cfg.CONF_DC['admin_user_name']
        grid_conf.admin_password = cfg.CONF_DC['admin_password']
        grid_conf.wapi_version = cfg.CONF_DC['wapi_version']
        grid_conf.ssl_verify = cfg.CONF_DC['ssl_verify']
        grid_conf.http_request_timeout = cfg.CONF_DC['http_request_timeout']
        grid_conf.http_pool_connections = cfg.CONF_DC['http_pool_connections']
        grid_conf.http_pool_maxsize = cfg.CONF_DC['http_pool_maxsize']
        return grid_conf


class GridConfiguration(object):

    def __init__(self, context, connector):
        self._context = context
        self._connector = connector

        # grid info from neutron conf
        self._grid_id = None
        self._grid_name = None
        self._grid_master_host = None

        # grid connection from neutron conf
        self._admin_username = None
        self._admin_password = None
        self._cloud_username = None
        self._cloud_user_password = None
        self._wapi_version = None
        self._ssl_verify = False
        self._http_request_timeout = 120
        self._http_pool_connections = 100
        self._http_pool_maxsize = 100
        self._is_cloud_wapi = False

        # default settings from nios grid master
        self._network_view_scope = const.EA_NETWORK_VIEW_SCOPE_SINGLE
        self._default_network_view = 'default'
        self._default_host_name_pattern = 'host-{ip_address}'
        self._default_domain_name_pattern = '{subnet_id}.cloud.global.com'
        self._default_ns_group = None
        self._admin_network_deletion = False
        self._ip_allocation_strategy = \
            const.EA_IP_ALLOCATION_STRATEGY_HOST_RECORD
        self._dns_record_binding_types = []
        self._dns_record_unbinding_types = []
        self._dns_record_removable_types = []
        self._dhcp_replay_management_network_view = None
        self._dhcp_replay_management_network = None

    @property
    def grid_id(self):
        return self._grid_id

    @grid_id.setter
    def grid_id(self, value):
        self._grid_id = value

    @property
    def grid_name(self):
        return self._grid_name

    @grid_name.setter
    def grid_name(self, value):
        self._grid_name = value

    @property
    def grid_master_host(self):
        return self._grid_master_host

    @grid_master_host.setter
    def grid_master_host(self, value):
        self._grid_master_host = value

    @property
    def admin_username(self):
        return self._admin_username

    @admin_username.setter
    def admin_username(self, value):
        self._admin_username = value

    @property
    def admin_password(self):
        return self._admin_password

    @admin_password.setter
    def admin_password(self, value):
        self._admin_password = value

    @property
    def cloud_username(self):
        return self._cloud_username

    @cloud_username.setter
    def cloud_username(self, value):
        self._cloud_username = value

    @property
    def cloud_user_password(self):
        return self._cloud_user_password

    @cloud_user_password.setter
    def cloud_user_password(self, value):
        self._cloud_user_password = value

    @property
    def wapi_version(self):
        return self._wapi_version

    @wapi_version.setter
    def wapi_version(self, value):
        self._wapi_version = value
        self._is_cloud_wapi = connector.Connector.is_cloud_wapi(value)

    @property
    def ssl_verify(self):
        return self._ssl_verify

    @ssl_verify.setter
    def ssl_verify(self, value):
        self._ssl_verify = value

    @property
    def http_request_timeout(self):
        return self._http_request_timeout

    @http_request_timeout.setter
    def http_request_timeout(self, value):
        self._http_request_timeout = value

    @property
    def http_pool_connections(self):
        return self._http_pool_connections

    @http_pool_connections.setter
    def http_pool_connections(self, value):
        self._http_pool_connections = value

    @property
    def http_pool_maxsize(self):
        return self._http_pool_maxsize

    @http_pool_maxsize.setter
    def http_pool_maxsize(self, value):
        self._http_pool_maxsize = value

    @property
    def is_cloud_wapi(self):
        return self._is_cloud_wapi

    @property
    def network_view_scope(self):
        return self._network_view_scope

    @network_view_scope.setter
    def network_view_scope(self, value):
        self._network_view_scope = value

    @property
    def default_network_view(self):
        return self._default_network_view

    @default_network_view.setter
    def default_network_view(self, value):
        self._default_network_view = value

    @property
    def default_host_name_pattern(self):
        return self._default_host_name_pattern

    @default_host_name_pattern.setter
    def default_host_name_pattern(self, value):
        self._default_host_name_pattern = value

    @property
    def default_domain_name_pattern(self):
        return self._default_domain_name_pattern

    @default_domain_name_pattern.setter
    def default_domain_name_pattern(self, value):
        self._default_domain_name_pattern = value

    @property
    def default_ns_group(self):
        return self._default_ns_group

    @default_ns_group.setter
    def default_ns_group(self, value):
        self._default_ns_group = value

    @property
    def admin_network_deletion(self):
        return self._admin_network_deletion

    @admin_network_deletion.setter
    def admin_network_deletion(self, value):
        self._admin_network_deletion = value

    @property
    def ip_allocation_strategy(self):
        return self._ip_allocation_strategy

    @ip_allocation_strategy.setter
    def ip_allocation_strategy(self, value):
        self._ip_allocation_strategy = value

    @property
    def dns_record_binding_types(self):
        return self._dns_record_binding_types

    @dns_record_binding_types.setter
    def dns_record_binding_types(self, value):
        self._dns_record_binding_types = value

    @property
    def dns_record_unbinding_types(self):
        return self._dns_record_unbinding_types

    @dns_record_unbinding_types.setter
    def dns_record_unbinding_types(self, value):
        self._dns_record_unbinding_types = value

    @property
    def dns_record_removable_types(self):
        return self._dns_record_removable_types

    @dns_record_removable_types.setter
    def dns_record_removable_types(self, value):
        self._dns_record_removable_types = value

    @property
    def dhcp_replay_management_network_view(self):
        return self._dhcp_replay_management_network_view

    @dhcp_replay_management_network_view.setter
    def dhcp_replay_management_network_view(self, value):
        self._dhcp_replay_management_network_view = value

    @property
    def dhcp_replay_management_network(self):
        return self._dhcp_replay_management_network

    @dhcp_replay_management_network.setter
    def dhcp_replay_management_network(self, value):
        self._dhcp_replay_management_network = value

    def sync(self):
        session = self._context.session
        members = dbi.get_members(session,
                                  grid_id=self._grid_id,
                                  member_type=const.MEMBER_TYPE_GRID_MASTER)
        if not members or len(members) != 1:
            raise exc.InfobloxCannotFindMember(member="GM")

        discovered_config = self._discover_config(members[0])
        if discovered_config and discovered_config.get('extattrs'):
            self._update_fields(discovered_config)

    def _discovered_config(self, gm_member):
        return_fields = ['extattrs']
        if self._grid_config.is_cloud_wapi:
            return_fields.append('ipv6_setting')

        obj_type = "member/%s:%s" % (gm_member['member_id'],
                                     gm_member['member_name'])
        config = self._connector.get_object(obj_type,
                                            return_fields=return_fields)
        return config

    def _update_fields(self, extattr):
        self._update_from_ea(
            'network_view_scope',
            const.EA_GRID_CONFIG_NETWORK_VIEW_SCOPE,
            extattr)
        self._update_from_ea(
            'default_network_view',
            const.EA_GRID_CONFIG_DEFAULT_NETWORK_VIEW,
            extattr)
        self._update_from_ea(
            'default_host_name_pattern',
            const.EA_GRID_CONFIG_DEFAULT_HOST_NAME_PATTERN,
            extattr)
        self._update_from_ea(
            'default_domain_name_pattern',
            const.EA_GRID_CONFIG_DEFAULT_DOMAIN_NAME_PATTERN,
            extattr)
        self._update_from_ea(
            'default_ns_group',
            const.EA_GRID_CONFIG_DEFAULT_NS_GROUP,
            extattr)
        self._update_from_ea(
            'admin_network_deletion',
            const.EA_GRID_CONFIG_ADMIN_NETWORK_DELETION,
            extattr)
        self._update_from_ea(
            'ip_allocation_strategy',
            const.EA_GRID_CONFIG_IP_ALLOCATION_STRATEGY,
            extattr)
        self._update_from_ea(
            'dns_record_binding_types',
            const.EA_GRID_CONFIG_DNS_RECORD_BINDING_TYPES,
            extattr)
        self._update_from_ea(
            'dns_record_unbinding_types',
            const.EA_GRID_CONFIG_DNS_RECORD_UNBINDING_TYPES,
            extattr)
        self._update_from_ea(
            'dns_record_removable_types',
            const.EA_GRID_CONFIG_DNS_RECORD_REMOVABLE_TYPES,
            extattr)
        self._update_from_ea(
            'dhcp_replay_management_network_view',
            const.EA_GRID_CONFIG_DHCP_RELAY_MANAGEMENT_NETWORK_VIEW,
            extattr)
        self._update_from_ea(
            'dhcp_replay_management_network',
            const.EA_GRID_CONFIG_DHCP_RELAY_MANAGEMENT_NETWORK,
            extattr)

    def _update_from_ea(self, field, ea_name, extattrs):
        value = utils.get_ea_value(ea_name, extattrs)
        if value:
            setattr(self, field, value)
