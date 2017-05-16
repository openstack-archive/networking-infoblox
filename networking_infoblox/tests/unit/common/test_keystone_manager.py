# Copyright (c) 2016 Infoblox Inc.
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

from networking_infoblox.neutron.common import keystone_manager

from networking_infoblox.tests import base


class DummyInfobloxOpts(object):
    def __init__(self):
        self.keystone_auth_uri = 'auth_uri'
        self.keystone_admin_username = 'cloud_admin_user'
        self.keystone_admin_password = 'cloud_admin_password'
        self.keystone_admin_project_name = 'cloud_admin_project'
        self.keystone_admin_tenant_name = 'cloud_admin_tenant'
        self.keystone_admin_user_domain_id = 'cloud_admin_domain'
        self.keystone_admin_project_domain_id = 'cloud_admin_domain'
        self.keystone_auth_version = 'v2.0'
        self.keystone_admin_domain_id = ''


class TestKeystoneManager(base.TestCase):

    def setUp(self):
        super(TestKeystoneManager, self).setUp()
        self.tenants = []
        for i in range(1, 4):
            tenant = mock.Mock()
            tenant.id = str(i)
            tenant.tenant_id = tenant.id
            tenant.name = 'tenant_%s' % i
            self.tenants.append(tenant)
        self.networks = [
            {'tenant_id': '1'},
            {'tenant_id': '2'},
            {'tenant_id': '3'},
            {'tenant_id': '4'},
            ]

    def test_get_identity_service_with_auth_version(self):
        version = 'v3'
        ib_opts = DummyInfobloxOpts()
        ib_opts.keystone_auth_version = version
        identity = ib_opts.keystone_auth_uri + '/' + (
            ib_opts.keystone_auth_version)
        # call tested function
        r_identity, r_version = keystone_manager.get_identity_service(ib_opts)
        assert r_identity == identity
        assert r_version == version

    def test_get_identity_service_without_auth_version(self):
        ib_opts = DummyInfobloxOpts()
        version = 'v3'
        auth_url = 'auth_url' + '/' + version
        ib_opts.keystone_auth_uri = auth_url
        # call tested function
        r_identity, r_version = keystone_manager.get_identity_service(ib_opts)
        assert r_identity == auth_url
        assert r_version == version

    @mock.patch('keystoneauth1.loading.load_session_from_conf_options')
    @mock.patch('keystoneauth1.identity.generic.Password')
    def _test_get_keystone_client(self, ClientMock, ConfMock,
                                  PasswordMock, loadSessionMock):
        ib_opts = ConfMock.infoblox
        session = 'session'
        auth = 'auth'
        auth_url = ib_opts.keystone_auth_uri + '/' + (
            ib_opts.keystone_auth_version)
        loadSessionMock.return_value = session
        PasswordMock.return_value = auth
        # call tested function
        k_client = keystone_manager.get_keystone_client()
        PasswordMock.assert_called_once_with(
            auth_url=auth_url,
            username=ib_opts.keystone_admin_username,
            password=ib_opts.keystone_admin_password,
            project_name=ib_opts.keystone_admin_project_name,
            user_domain_id=ib_opts.keystone_admin_user_domain_id,
            project_domain_id=ib_opts.keystone_admin_project_domain_id,
            tenant_name=ib_opts.keystone_admin_tenant_name,
            domain_id=ib_opts.keystone_admin_domain_id)
        loadSessionMock.assert_called_once_with(ConfMock, 'infoblox',
                                                auth=auth)
        ClientMock.assert_called_once_with(session=session)
        assert k_client == ClientMock.return_value

    @mock.patch('networking_infoblox.neutron.common.keystone_manager.CONF')
    @mock.patch('keystoneclient.v2_0.client.Client')
    def test_get_keystone_client_v2_0(self, ClientMock, ConfMock):
        ClientMock.return_value = 'keystone_client_v2_0'
        # prepare mocks
        ConfMock.infoblox = DummyInfobloxOpts()
        self._test_get_keystone_client(ClientMock, ConfMock)

    @mock.patch('networking_infoblox.neutron.common.keystone_manager.CONF')
    @mock.patch('keystoneclient.v3.client.Client')
    def test_get_keystone_client_v3(self, ClientMock, ConfMock):
        ClientMock.return_value = 'keystone_client_v3'
        # prepare mocks
        ConfMock.infoblox = DummyInfobloxOpts()
        ConfMock.infoblox.keystone_auth_version = 'v3'
        self._test_get_keystone_client(ClientMock, ConfMock)

    @mock.patch('networking_infoblox.neutron.common.keystone_manager.'
                'get_keystone_client')
    def _test_get_all_tenants(self, version, get_keystone_client_mock):
        # prepare mocks
        client_mock = mock.MagicMock()
        client_mock.version = version
        get_keystone_client_mock.return_value = client_mock
        # call tested function
        keystone_manager.get_all_tenants()
        # check calls
        get_keystone_client_mock.assert_called_once_with()
        if version == 'v3':
            client_mock.projects.list.assert_called_once_with()
        else:
            client_mock.tenants.list.assert_called_once_with()

    def test_get_all_tenants_v2_0(self):
        self._test_get_all_tenants('v2.0')

    def test_get_all_tenants_v3(self):
        self._test_get_all_tenants('v3')

    @mock.patch('networking_infoblox.neutron.common.keystone_manager.'
                'sync_tenants_from_keystone')
    @mock.patch('networking_infoblox.neutron.db.infoblox_db.'
                'add_or_update_tenant')
    @mock.patch('networking_infoblox.neutron.db.infoblox_db.get_tenants')
    def _test_update_tenant_mapping(self, networks, tenants,
                                    expected_results,
                                    get_tenants, add_or_update_tenant,
                                    sync_tenants_from_keystone):
        context = mock.Mock()
        context.session = 'test_session'
        tenant_id = '1'
        tenant_name = 'test_tenant_name_1'
        get_unknown = mock.Mock()
        get_unknown_params = []
        func = keystone_manager._get_unknown_ids_from_dict

        def store_params(param):
            get_unknown_params.append(param.copy())
            return func(param)

        get_unknown.side_effect = store_params
        get_tenants.return_value = tenants
        with mock.patch('networking_infoblox.neutron.common.keystone_manager.'
                        '_get_unknown_ids_from_dict', get_unknown):
            keystone_manager.update_tenant_mapping(
                context, networks, tenant_id, tenant_name)
        add_or_update_tenant.assert_called_once_with(context.session,
                                                     tenant_id, tenant_name)
        assert get_unknown.call_count == expected_results['get_unknown_count']
        assert get_unknown_params == expected_results['get_unknown_params']
        if expected_results['get_tenants_called']:
            get_tenants.assert_called_once()
            assert get_tenants.call_args[0] == (context.session,)
            tenant_ids = expected_results['get_tenant_tenant_ids']
            assert(
                sorted(
                    get_tenants.call_args[1]['tenant_ids']) == tenant_ids)
        else:
            get_tenants.assert_not_called()
        if expected_results['sync_tenants_from_keystone_called']:
            sync_tenants_from_keystone.assert_called_once_with(context)
        else:
            sync_tenants_from_keystone.assert_not_called()

    def test_update_tenant_mapping(self):
        networks = self.networks
        tenants = self.tenants
        expected_results = {
            'get_unknown_count': 2,
            'get_unknown_params': [
                {
                    networks[0]['tenant_id']: False,
                    networks[1]['tenant_id']: True,
                    networks[2]['tenant_id']: True,
                    networks[3]['tenant_id']: True
                },
                {
                    networks[0]['tenant_id']: False,
                    networks[1]['tenant_id']: False,
                    networks[2]['tenant_id']: False,
                    networks[3]['tenant_id']: True
                }],
            'get_tenants_called': True,
            'get_tenant_tenant_ids': ['2', '3', '4'],
            'sync_tenants_from_keystone_called': True
            }
        self._test_update_tenant_mapping(networks, tenants,
                                         expected_results)

    def test_update_tenant_mapping_all_tenant_in_db(self):
        networks = self.networks
        networks[3]['tenant_id'] = networks[0]['tenant_id']
        tenants = self.tenants
        expected_results = {
            'get_unknown_count': 2,
            'get_unknown_params': [
                {
                    networks[0]['tenant_id']: False,
                    networks[1]['tenant_id']: True,
                    networks[2]['tenant_id']: True,
                    networks[3]['tenant_id']: False
                },
                {
                    networks[0]['tenant_id']: False,
                    networks[1]['tenant_id']: False,
                    networks[2]['tenant_id']: False,
                    networks[3]['tenant_id']: False
                }],
            'get_tenants_called': True,
            'get_tenant_tenant_ids': ['2', '3'],
            'sync_tenants_from_keystone_called': False
            }
        self._test_update_tenant_mapping(networks, tenants,
                                         expected_results)

    def test_update_tenant_mapping_all_tenant_in_networks(self):
        networks = self.networks
        for i in range(1, len(networks)):
            networks[i]['tenant_id'] = networks[0]['tenant_id']
        tenants = self.tenants
        expected_results = {
            'get_unknown_count': 1,
            'get_unknown_params': [
                {
                    networks[0]['tenant_id']: False,
                    networks[1]['tenant_id']: False,
                    networks[2]['tenant_id']: False,
                    networks[3]['tenant_id']: False
                }],
            'get_tenants_called': False,
            'sync_tenants_from_keystone_called': False
            }
        self._test_update_tenant_mapping(networks, tenants,
                                         expected_results)

    @mock.patch('networking_infoblox.neutron.common.keystone_manager.'
                'get_all_tenants')
    @mock.patch('networking_infoblox.neutron.db.infoblox_db.'
                'add_or_update_tenant')
    def test_sync_tenants_from_keystone(self, AddTenantMock, get_all_tenants):
        # prepare test data
        context = mock.Mock()
        context.session = 'test_session'
        get_all_tenants.return_value = self.tenants
        # call tested function
        ret = keystone_manager.sync_tenants_from_keystone(context)
        # check return value and calls
        assert ret == len(self.tenants)
        get_all_tenants.assert_called_once_with()
        expected_call_list = [
            mock.call(context.session, t.id, t.name) for t in self.tenants]
        assert AddTenantMock.call_args_list == expected_call_list
