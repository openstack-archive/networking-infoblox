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


class DummyKeystoneAuthtoken(object):
    def __init__(self):
        self.auth_uri = ''
        self.auth_version = 'v2.0'
        self.admin_user = 'cloud_admin_user'
        self.admin_password = 'cloud_admin_password'
        self.admin_tenant_name = 'cloud_admin_tenant'
        self.project_domain_id = 'cloud_admin_domain'
        self.cafile = 'ca.crt'


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

    @mock.patch('keystoneclient.session.Session')
    def test_init_keystone_session(self, SessionMock):
        keystone_manager._SESSION = None  # reset glogal variable
        cafile = False
        # call function and check that Session created without params
        session1 = keystone_manager.init_keystone_session(cafile)
        SessionMock.assert_called_once_with(verify=cafile)
        # reset mock, call function again and check that Session is not called
        # and function return same session
        SessionMock.reset_mock()
        session2 = keystone_manager.init_keystone_session(cafile)
        assert not SessionMock.called
        assert session1 is session2

    @mock.patch('keystoneclient.auth.token_endpoint.Token')
    @mock.patch('networking_infoblox.neutron.common.keystone_manager.CONF')
    @mock.patch('networking_infoblox.neutron.common.keystone_manager.'
                'init_keystone_session')
    def _test_get_keystone_client(self, ClientMock, keystone_authtoken,
                                  InitMock, ConfMock,
                                  TokenEndpointMock):
        # prepare mocks
        session = 'test_session'
        auth_token = 'test_auth_token'
        auth_uri = 'test_auth_uri'
        token_endpoint = 'token_endpoint'
        InitMock.return_value = session
        ConfMock.keystone_authtoken = DummyKeystoneAuthtoken()
        ConfMock.keystone_authtoken.auth_uri = auth_uri
        ConfMock.keystone_authtoken.auth_version = (
            keystone_authtoken['version'])
        cafile = ConfMock.keystone_authtoken.cafile
        TokenEndpointMock.return_value = token_endpoint
        # call tested function
        k_client = keystone_manager.get_keystone_client(auth_token)
        # check calls
        keystone_manager.init_keystone_session.assert_called_once_with(cafile)
        TokenEndpointMock.assert_called_once_with(
            auth_uri + '/' + keystone_authtoken['version'], auth_token)
        ClientMock.assert_called_once_with(session=session,
                                           auth=token_endpoint)
        assert k_client == ClientMock.return_value

    @mock.patch('keystoneclient.v2_0.client.Client')
    def test_get_keystone_client_v2_0(self, ClientMock):
        ClientMock.return_value = 'keystone_client_v2_0'
        self._test_get_keystone_client(ClientMock, {'version': 'v2.0'})

    @mock.patch('networking_infoblox.neutron.common.keystone_manager.CONF')
    @mock.patch('keystoneclient.v3.client.Client')
    def test_get_keystone_client_v3(self, ClientMock, ConfMock):
        ClientMock.return_value = 'keystone_client_v3'
        auth_uri = 'test_auth_uri'
        auth_token = 'test_auth_token'
        ConfMock.keystone_authtoken = DummyKeystoneAuthtoken()
        ConfMock.keystone_authtoken.auth_uri = auth_uri
        ConfMock.keystone_authtoken.auth_version = 'v3'
        # call tested function
        k_client = keystone_manager.get_keystone_client(auth_token)
        # check calls
        ClientMock.assert_called_once_with(
            auth_url=ConfMock.keystone_authtoken.auth_uri + '/v3',
            username=ConfMock.keystone_authtoken.admin_user,
            password=ConfMock.keystone_authtoken.admin_password,
            domain_name=ConfMock.keystone_authtoken.project_domain_id,
            verify=ConfMock.keystone_authtoken.cafile)
        assert k_client == ClientMock.return_value

    @mock.patch('networking_infoblox.neutron.common.keystone_manager.'
                'get_keystone_client')
    def _test_get_all_tenants(self, version, get_keystone_client_mock):
        # prepare mocks
        auth_token = 'test_auth_token'
        client_mock = mock.MagicMock()
        client_mock.version = version
        get_keystone_client_mock.return_value = client_mock
        # call tested function
        keystone_manager.get_all_tenants(auth_token)
        # check calls
        get_keystone_client_mock.assert_called_once_with(auth_token)
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
    def _test_update_tenant_mapping(self, auth_token, networks, tenants,
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
                context, networks, tenant_id, tenant_name, auth_token)
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
            sync_tenants_from_keystone.assert_called_once_with(context,
                                                               auth_token)
        else:
            sync_tenants_from_keystone.assert_not_called()

    def test_update_tenant_mapping(self):
        auth_token = 'test_auth_token'
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
        self._test_update_tenant_mapping(auth_token, networks, tenants,
                                         expected_results)

    def test_update_tenant_mapping_all_tenant_in_db(self):
        auth_token = 'test_auth_token'
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
        self._test_update_tenant_mapping(auth_token, networks, tenants,
                                         expected_results)

    def test_update_tenant_mapping_all_tenant_in_networks(self):
        auth_token = 'test_auth_token'
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
        self._test_update_tenant_mapping(auth_token, networks, tenants,
                                         expected_results)

    def test_update_tenant_mapping_without_token(self):
        auth_token = ''
        networks = self.networks
        tenants = self.tenants
        expected_results = {
            'get_unknown_count': 0,
            'get_unknown_params': [],
            'get_tenants_called': False,
            'sync_tenants_from_keystone_called': False
            }
        self._test_update_tenant_mapping(auth_token, networks, tenants,
                                         expected_results)

    @mock.patch('networking_infoblox.neutron.common.keystone_manager.'
                'get_all_tenants')
    @mock.patch('networking_infoblox.neutron.db.infoblox_db.'
                'add_or_update_tenant')
    def test_sync_tenants_from_keystone(self, AddTenantMock, get_all_tenants):
        # prepare test data
        context = mock.Mock()
        context.session = 'test_session'
        auth_token = 'test_auth_token'
        get_all_tenants.return_value = self.tenants
        # call tested function
        ret = keystone_manager.sync_tenants_from_keystone(context, auth_token)
        # check return value and calls
        assert ret == len(self.tenants)
        get_all_tenants.assert_called_once_with(auth_token)
        expected_call_list = [
            mock.call(context.session, t.id, t.name) for t in self.tenants]
        assert AddTenantMock.call_args_list == expected_call_list

    @mock.patch('networking_infoblox.neutron.common.keystone_manager.'
                'get_all_tenants')
    @mock.patch('networking_infoblox.neutron.db.infoblox_db.'
                'add_or_update_tenant')
    def test_sync_tenants_from_keystone_without_token(self, AddTenantMock,
                                                      get_all_tenants):
        ret = keystone_manager.sync_tenants_from_keystone('context', None)
        assert ret is None
        get_all_tenants.assert_not_called()
        AddTenantMock.assert_not_called
