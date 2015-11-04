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

from datetime import datetime
from datetime import timedelta
from oslo_log import log as logging

from neutron.i18n import _LI

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
    member = None
    mapping = None
    last_sync_time = None

    def __init__(self, context):
        self.grid_config = self._create_grid_configuration(context)
        self.member = grid_member.GridMemberManager(self.grid_config)
        self.mapping = grid_mapping.GridMappingManager(self.grid_config)

    def sync(self):
        """Synchronize members, config, and mapping between NIOS and neutron.

        First sync members, then config, and lastly mapping because config
        sync needs GM info and mapping needs grid config.
        """
        session = self.grid_config.context.session
        allow_sync = False
        if self.grid_config.grid_sync_support:
            self.last_sync_time = dbi.get_last_sync_time(session)
            if not self.last_sync_time:
                allow_sync = True
            elif (datetime.utcnow() - self.last_sync_time >
                    timedelta(
                        seconds=self.grid_config.grid_sync_minimum_wait_time)):
                allow_sync = True

        if allow_sync:
            self.member.sync()
            self.grid_config.sync()
            self.mapping.sync()
            self.last_sync_time = datetime.utcnow().replace(microsecond=0)
            dbi.record_last_sync_time(session, self.last_sync_time)

    def get_config(self):
        """Gets grid configuration.

        Before this call is made, the grid member must be in sync.
        """
        self.grid_config.sync()
        return self.grid_config

    @staticmethod
    def _create_grid_configuration(context):
        grid_conf = GridConfiguration(context)
        grid_conf.grid_id = cfg.CONF.infoblox.cloud_data_center_id
        grid_opts = cfg.get_infoblox_grid_opts(grid_conf.grid_id)
        if not grid_opts['grid_master_host']:
            raise exc.InfobloxInvalidCloudDataCenter(
                data_center_id=grid_conf.grid_id)
        grid_conf.grid_name = grid_opts['data_center_name']
        grid_conf.grid_master_host = grid_opts['grid_master_host']
        grid_conf.admin_user_name = grid_opts['admin_user_name']
        grid_conf.admin_password = grid_opts['admin_password']
        grid_conf.cloud_user_name = grid_opts['cloud_user_name']
        grid_conf.cloud_user_password = grid_opts['cloud_user_password']
        grid_conf.wapi_version = grid_opts['wapi_version']
        grid_conf.ssl_verify = grid_opts['ssl_verify']
        grid_conf.http_request_timeout = grid_opts['http_request_timeout']
        grid_conf.http_pool_connections = grid_opts['http_pool_connections']
        grid_conf.http_pool_maxsize = grid_opts['http_pool_maxsize']

        # create connector to GM
        admin_opts = {
            'host': grid_conf.grid_master_host,
            'username': grid_conf.admin_user_name,
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
        'grid_sync_support':
            const.EA_GRID_CONFIG_GRID_SYNC_SUPPORT,
        'grid_sync_minimum_wait_time':
            const.EA_GRID_CONFIG_GRID_SYNC_MINIMUM_WAIT_TIME,
        'default_network_view_scope':
            const.EA_GRID_CONFIG_DEFAULT_NETWORK_VIEW_SCOPE,
        'default_network_view': const.EA_GRID_CONFIG_DEFAULT_NETWORK_VIEW,
        'default_host_name_pattern':
            const.EA_GRID_CONFIG_DEFAULT_HOST_NAME_PATTERN,
        'default_domain_name_pattern':
            const.EA_GRID_CONFIG_DEFAULT_DOMAIN_NAME_PATTERN,
        'ns_group': const.EA_GRID_CONFIG_NS_GROUP,
        'network_template': const.EA_GRID_CONFIG_NETWORK_TEMPLATE,
        'admin_network_deletion': const.EA_GRID_CONFIG_ADMIN_NETWORK_DELETION,
        'ip_allocation_strategy': const.EA_GRID_CONFIG_IP_ALLOCATION_STRATEGY,
        'dns_record_binding_types':
            const.EA_GRID_CONFIG_DNS_RECORD_BINDING_TYPES,
        'dns_record_unbinding_types':
            const.EA_GRID_CONFIG_DNS_RECORD_UNBINDING_TYPES,
        'dns_record_removable_types':
            const.EA_GRID_CONFIG_DNS_RECORD_REMOVABLE_TYPES,
        'dhcp_relay_management_network_view':
            const.EA_GRID_CONFIG_DHCP_RELAY_MANAGEMENT_NETWORK_VIEW,
        'dhcp_relay_management_network':
            const.EA_GRID_CONFIG_DHCP_RELAY_MANAGEMENT_NETWORK,
        'dhcp_support': const.EA_GRID_CONFIG_DHCP_SUPPORT
    }

    def __init__(self, context):
        self.context = context

        # grid info from neutron conf
        self.grid_id = None
        self.grid_name = None
        self.grid_master_host = None

        # grid connection from neutron conf
        self.admin_user_name = None
        self.admin_password = None
        self.cloud_user_name = None
        self.cloud_user_password = None
        self.ssl_verify = False
        self.http_request_timeout = 120
        self.http_pool_connections = 100
        self.http_pool_maxsize = 100

        # connector object to GM
        self.gm_connector = None
        self.wapi_major_version = None
        self._wapi_version = None
        self._is_cloud_wapi = False

        # default settings from nios grid master
        self.grid_sync_support = True
        self.grid_sync_minimum_wait_time = 60
        self.default_network_view_scope = const.NETWORK_VIEW_SCOPE_SINGLE
        self.default_network_view = 'default'
        self.default_host_name_pattern = 'host-{ip_address}'
        self.default_domain_name_pattern = '{subnet_id}.cloud.global.com'
        self.ns_group = None
        self.network_template = None
        self.admin_network_deletion = False
        self.ip_allocation_strategy = const.IP_ALLOCATION_STRATEGY_HOST_RECORD
        self.dns_record_binding_types = []
        self.dns_record_unbinding_types = []
        self.dns_record_removable_types = []
        self.dhcp_relay_management_network_view = None
        self.dhcp_relay_management_network = None
        self.dhcp_support = False

    @property
    def wapi_version(self):
        return self._wapi_version

    @wapi_version.setter
    def wapi_version(self, value):
        self._wapi_version = value
        if value:
            self._is_cloud_wapi = connector.Connector.is_cloud_wapi(value)
            self.wapi_major_version = utils.get_major_version(value)

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
        if discovered_config:
            self._update_fields(discovered_config)
            LOG.debug(_LI("grid config synced: %s"), self.__dict__)

    def get_grid_connection(self):
        grid_connection = {
            "wapi_version": self.wapi_version,
            "ssl_verify": self.ssl_verify,
            "http_pool_connections": self.http_pool_connections,
            "http_pool_maxsize": self.http_pool_maxsize,
            "http_request_timeout": self.http_request_timeout,
            "admin_user": {"name": self.admin_user_name,
                           "password": self.admin_password},
            "cloud_user": {"name": self.cloud_user_name,
                           "password": self.cloud_user_password}
        }
        return grid_connection

    def _discover_config(self, gm_member):
        return_fields = ['extattrs']
        if self.wapi_major_version >= 2:
            return_fields.append('ipv6_setting')

        obj_type = 'member'
        payload = {'host_name': gm_member['member_name']}
        config = self.gm_connector.get_object(
            obj_type, payload=payload, return_fields=return_fields)
        return config[0] if config and config[0].get('extattrs') else None

    def _update_fields(self, extattr):
        for pm in self.property_to_ea_mapping:
            self._update_from_ea(pm,
                                 self.property_to_ea_mapping[pm],
                                 extattr)

    def _update_from_ea(self, field, ea_name, extattrs):
        value = utils.get_ea_value(ea_name, extattrs)
        if value:
            setattr(self, field, value)
