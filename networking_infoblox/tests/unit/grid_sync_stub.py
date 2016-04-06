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

import mock

from oslo_config import cfg

from neutron.common import config as common_config

from networking_infoblox.neutron.common import config
from networking_infoblox.neutron.common import grid

from networking_infoblox.tests import base


class GridSyncStub(object):

    def __init__(self, context, connector_fixture):
        self.context = context
        self.fixture = connector_fixture

    def prepare_grid_manager(self, wapi_version):
        self.wapi_version = wapi_version

        self._setup_config()
        self.grid_mgr = grid.GridManager(self.context)
        self.grid_mgr.grid_config.gm_connector = mock.Mock()
        self.grid_mgr.member._discover_dns_settings = mock.Mock(
            return_value=[])
        self.grid_mgr.member._discover_dhcp_settings = mock.Mock(
            return_value=[])

        self._prepare_discovery_resources()

    def get_grid_manager(self):
        return self.grid_mgr

    def _setup_config(self):
        # config init is needed to initialize transport and config loading
        common_config.init([])

        # register infoblox stanza
        config.register_infoblox_ipam_opts(cfg.CONF)
        cfg.CONF.set_override("cloud_data_center_id", 100, 'infoblox')
        cfg.CONF.set_override("ipam_agent_workers", 1, 'infoblox')

        # register infoblox data center stanza
        data_center_id = cfg.CONF.infoblox.cloud_data_center_id
        config.register_infoblox_grid_opts(cfg.CONF, data_center_id)
        data_center = 'infoblox-dc:%s' % data_center_id
        cfg.CONF.set_override('grid_master_host', '192.168.1.7', data_center)
        cfg.CONF.set_override('grid_master_name', 'nios-7.2.0-master.com',
                              data_center)
        cfg.CONF.set_override('data_center_name', 'admin', data_center)
        cfg.CONF.set_override('admin_user_name', 'admin', data_center)
        cfg.CONF.set_override('admin_password', 'infoblox', data_center)
        cfg.CONF.set_override('wapi_version', self.wapi_version, data_center)

    def _prepare_discovery_resources(self):
        resource_map = base.FixtureResourceMap

        member_resource = resource_map.FAKE_MEMBERS_WITHOUT_CLOUD
        if self.grid_mgr.grid_config.is_cloud_wapi:
            member_resource = resource_map.FAKE_MEMBERS_WITH_CLOUD

        license_resource = None
        if self.grid_mgr.grid_config.is_cloud_wapi:
            license_resource = resource_map.FAKE_MEMBER_LICENSES

        netview_resource = resource_map.FAKE_NETWORKVIEW_WITHOUT_CLOUD
        network_resource = resource_map.FAKE_NETWORK_WITHOUT_CLOUD
        if self.grid_mgr.grid_config.is_cloud_wapi:
            netview_resource = resource_map.FAKE_NETWORKVIEW_WITH_CLOUD
            network_resource = resource_map.FAKE_NETWORK_WITH_CLOUD

        dnsview_resource = resource_map.FAKE_DNS_VIEW

        # create members
        member_json = self.fixture.get_object(member_resource)
        self.grid_mgr.member._discover_members = mock.Mock()
        self.grid_mgr.member._discover_members.return_value = member_json

        if license_resource:
            license_json = self.fixture.get_object(license_resource)
            self.grid_mgr.member._discover_member_licenses = mock.Mock()
            self.grid_mgr.member._discover_member_licenses.return_value = (
                license_json)

        config_json = self.fixture.get_object(
            resource_map.FAKE_GRID_MASTER_GRID_CONFIGURATION)
        self.grid_mgr.grid_config._discover_config = mock.Mock()
        self.grid_mgr.grid_config._discover_config.return_value = config_json

        netview_json = self.fixture.get_object(netview_resource)
        self.grid_mgr.mapping._discover_network_views = mock.Mock()
        self.grid_mgr.mapping._discover_network_views.return_value = (
            netview_json)

        network_json = self.fixture.get_object(network_resource)
        self.grid_mgr.mapping._discover_networks = mock.Mock()
        self.grid_mgr.mapping._discover_networks.return_value = network_json

        dnsview_json = self.fixture.get_object(dnsview_resource)
        self.grid_mgr.mapping._discover_dns_views = mock.Mock()
        self.grid_mgr.mapping._discover_dns_views.return_value = dnsview_json
