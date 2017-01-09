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
import six
import socket

from neutron import context as neutron_context

from infoblox_client import connector
from infoblox_client import objects as ib_objects

from networking_infoblox._i18n import _LI
from networking_infoblox.neutron.common import config as cfg
from networking_infoblox.neutron.common import constants as const
from networking_infoblox.neutron.common import exceptions as exc
from networking_infoblox.neutron.common import mapping as grid_mapping
from networking_infoblox.neutron.common import member as grid_member
from networking_infoblox.neutron.common import utils
from networking_infoblox.neutron.db import infoblox_db as dbi


LOG = logging.getLogger(__name__)


class GridSyncer(object):
    def __init__(self):
        self._context = neutron_context.get_admin_context()
        self._grid_manager = GridManager(self._context)

    def is_sync_needed(self, interval):
        return self._grid_manager.is_sync_needed(interval)

    def sync(self, force_sync=False):
        self._grid_manager.sync(force_sync)


class GridManager(object):

    grid_config = None
    member = None
    mapping = None
    last_sync_time = None

    def __init__(self, context):
        self.grid_config = self._create_grid_configuration(context)
        self.member = grid_member.GridMemberManager(self.grid_config)
        self.mapping = grid_mapping.GridMappingManager(self.grid_config)
        self.hostname = socket.gethostname()

    def is_sync_needed(self, resync_interval):
        session = self.grid_config.context.session
        self.last_sync_time = dbi.get_last_sync_time(session)
        return (not self.last_sync_time or
                (datetime.utcnow() - self.last_sync_time > timedelta(
                    seconds=resync_interval)))

    def sync(self, force_sync=False):
        """Synchronize members, config, and mapping between NIOS and neutron.

        First sync members, then config, and lastly mapping because config
        sync needs GM info and mapping needs grid config.
        """
        session = self.grid_config.context.session
        allow_sync = False
        if self.grid_config.grid_sync_support:
            interval = self.grid_config.grid_sync_minimum_wait_time
            if force_sync or self.is_sync_needed(interval):
                allow_sync = True

        if allow_sync:
            self.member.sync()
            self.grid_config.sync()
            self.mapping.sync()
            self.last_sync_time = datetime.utcnow().replace(microsecond=0)
            dbi.record_last_sync_time(session, self.last_sync_time)
            self._report_sync_time()
            LOG.info("Infoblox grid has been synced up.")

    def get_config(self):
        """Gets grid configuration.

        Before this call is made, the grid member must be in sync.
        """
        self.grid_config.sync()

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
        grid_conf.grid_master_name = grid_opts['grid_master_name']
        grid_conf.admin_user_name = grid_opts['admin_user_name']
        grid_conf.admin_password = grid_opts['admin_password']
        grid_conf.wapi_version = grid_opts['wapi_version']
        grid_conf.ssl_verify = grid_opts['ssl_verify']
        grid_conf.http_request_timeout = grid_opts['http_request_timeout']
        grid_conf.http_pool_connections = grid_opts['http_pool_connections']
        grid_conf.http_pool_maxsize = grid_opts['http_pool_maxsize']
        grid_conf.wapi_max_results = grid_opts['wapi_max_results']

        # cloud user is used as admin, it needs to have proper permissions to
        # deal with non-delegated objects.
        gm_connection_opts = {
            'host': grid_conf.grid_master_host,
            'username': grid_conf.admin_user_name,
            'password': grid_conf.admin_password,
            'wapi_version': grid_conf.wapi_version,
            'ssl_verify': grid_conf.ssl_verify,
            'log_api_calls_as_info': True,
            'http_request_timeout': grid_conf.http_request_timeout,
            'http_pool_connections': grid_conf.http_pool_connections,
            'http_pool_maxsize': grid_conf.http_pool_maxsize,
            'max_results': grid_conf.wapi_max_results}
        # Silent ssl warnings, if certificate verification is not enabled
        if gm_connection_opts['ssl_verify'] == 'False':
            gm_connection_opts['silent_ssl_warnings'] = True
        grid_conf.gm_connector = connector.Connector(gm_connection_opts)
        return grid_conf

    def _report_sync_time(self):
        if self.grid_config.report_grid_sync_time is False:
            return

        conn = self.grid_config.gm_connector
        gm = self.grid_config.get_gm_member()
        if gm.member_ip:
            gm = ib_objects.Member.search(conn, ipv4_address=gm.member_ip)
        else:
            gm = ib_objects.Member.search(conn, ipv6_address=gm.member_ipv6)

        sync_info = (str(self.grid_config.grid_id) + ':' +
                     self.hostname + ' => ' +
                     self.last_sync_time.strftime("%Y-%m-%d %H:%M:%S"))

        sync_info_list = gm.extattrs.get(const.EA_LAST_GRID_SYNC_TIME)
        if sync_info_list:
            # if a single entry exits. NIOS returns as string rather than list.
            if isinstance(sync_info_list, six.string_types):
                sync_info_list = [sync_info_list]

            found_sync_idx_lst = [idx for idx, si in enumerate(sync_info_list)
                                  if self.hostname in si]
            if found_sync_idx_lst:
                sync_info_list[found_sync_idx_lst[0]] = sync_info
            else:
                sync_info_list.append(sync_info)
        else:
            sync_info_list = [sync_info]

        gm.extattrs.set(const.EA_LAST_GRID_SYNC_TIME, sync_info_list)
        gm.update()


class GridConfiguration(object):

    property_to_ea_mapping = {
        'grid_sync_support':
            const.EA_GRID_CONFIG_GRID_SYNC_SUPPORT,
        'grid_sync_minimum_wait_time':
            const.EA_GRID_CONFIG_GRID_SYNC_MINIMUM_WAIT_TIME,
        'grid_sync_maximum_wait_time':
            const.EA_GRID_CONFIG_GRID_SYNC_MAXIMUM_WAIT_TIME,
        'default_network_view_scope':
            const.EA_GRID_CONFIG_DEFAULT_NETWORK_VIEW_SCOPE,
        'default_network_view': const.EA_GRID_CONFIG_DEFAULT_NETWORK_VIEW,
        'default_host_name_pattern':
            const.EA_GRID_CONFIG_DEFAULT_HOST_NAME_PATTERN,
        'default_domain_name_pattern':
            const.EA_GRID_CONFIG_DEFAULT_DOMAIN_NAME_PATTERN,
        'external_host_name_pattern':
            const.EA_GRID_CONFIG_EXTERNAL_HOST_NAME_PATTERN,
        'external_domain_name_pattern':
            const.EA_GRID_CONFIG_EXTERNAL_DOMAIN_NAME_PATTERN,
        'ns_group': const.EA_GRID_CONFIG_NS_GROUP,
        'dns_view': const.EA_GRID_CONFIG_DNS_VIEW,
        'network_template': const.EA_GRID_CONFIG_NETWORK_TEMPLATE,
        'admin_network_deletion': const.EA_GRID_CONFIG_ADMIN_NETWORK_DELETION,
        'ip_allocation_strategy': const.EA_GRID_CONFIG_IP_ALLOCATION_STRATEGY,
        'dns_record_binding_types':
            const.EA_GRID_CONFIG_DNS_RECORD_BINDING_TYPES,
        'dns_record_unbinding_types':
            const.EA_GRID_CONFIG_DNS_RECORD_UNBINDING_TYPES,
        'dns_record_removable_types':
            const.EA_GRID_CONFIG_DNS_RECORD_REMOVABLE_TYPES,
        'dhcp_support': const.EA_GRID_CONFIG_DHCP_SUPPORT,
        'dns_support': const.EA_GRID_CONFIG_DNS_SUPPORT,
        'relay_support': const.EA_GRID_CONFIG_RELAY_SUPPORT,
        'use_grid_master_for_dhcp': const.EA_GRID_CONFIG_USE_GM_FOR_DHCP,
        'report_grid_sync_time': const.EA_GRID_CONFIG_REPORT_GRID_SYNC_TIME,
        'allow_service_restart': const.EA_GRID_CONFIG_ALLOW_SERVICE_RESTART,
        'allow_static_zone_deletion':
            const.EA_GRID_CONFIG_ALLOW_STATIC_ZONE_DELETION,
        'zone_creation_strategy': const.EA_GRID_CONFIG_ZONE_CREATION_STRATEGY,
        'tenant_name_persistence': const.EA_GRID_CONFIG_TENANT_NAME_PERSISTENCE
    }

    def __init__(self, context):
        self.context = context

        # grid info from neutron conf
        self.grid_id = None
        self.grid_name = None
        self.grid_master_host = None
        self.grid_master_name = None

        # grid connection from neutron conf
        self.admin_user_name = None
        self.admin_password = None
        self.ssl_verify = False
        self.http_request_timeout = 120
        self.http_pool_connections = 100
        self.http_pool_maxsize = 100

        # connector object to GM
        self.gm_connector = None
        self._wapi_version = None
        self._is_cloud_wapi = False

        # default settings from nios grid master
        self._set_default_values()

    @property
    def wapi_version(self):
        return self._wapi_version

    @wapi_version.setter
    def wapi_version(self, value):
        self._wapi_version = value
        if value:
            self._is_cloud_wapi =\
                utils.get_features(self.wapi_version).cloud_api

    @property
    def is_cloud_wapi(self):
        return self._is_cloud_wapi

    def sync(self):
        discovered_config = self._discover_config(self.get_gm_member())
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
                           "password": self.admin_password}
        }
        return grid_connection

    def _discover_config(self, gm_member):
        return_fields = ['extattrs']
        if utils.get_features(self.wapi_version).member_ipv6_setting:
            return_fields.append('ipv6_setting')

        obj_type = 'member'
        payload = {'host_name': gm_member['member_name']}
        config = self.gm_connector.get_object(
            obj_type, payload=payload, return_fields=return_fields)
        return config[0] if config and config[0].get('extattrs') else None

    def _set_default_values(self):
        for prop, key in self.property_to_ea_mapping.items():
            if key in const.GRID_CONFIG_DEFAULTS:
                setattr(self, prop, const.GRID_CONFIG_DEFAULTS[key])

    def _update_fields(self, extattr):
        for pm in self.property_to_ea_mapping:
            self._update_from_ea(pm,
                                 self.property_to_ea_mapping[pm],
                                 extattr)

    def _update_from_ea(self, field, ea_name, extattrs):
        value = utils.get_ea_value(ea_name, extattrs,
                                   ea_name in const.EA_MULTI_VALUES)
        if value:
            setattr(self, field, self._value_to_bool(value))

    @staticmethod
    def _value_to_bool(value):
        """Converts value returned by NIOS into boolean if possible."""
        if value == 'True':
            return True
        elif value == 'False':
            return False
        return value

    def get_gm_member(self):
        session = self.context.session
        members = dbi.get_members(session,
                                  grid_id=self.grid_id,
                                  member_type=const.MEMBER_TYPE_GRID_MASTER,
                                  member_status=const.MEMBER_STATUS_ON)
        if not members or len(members) != 1:
            raise exc.InfobloxCannotFindMember(member="GM")
        return members[0]
