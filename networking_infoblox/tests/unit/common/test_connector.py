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

import mock
from mock import patch
import requests
from requests import exceptions as req_exc

from networking_infoblox.common import connector
from networking_infoblox.common import exceptions
from networking_infoblox.tests import base


class TestInfobloxConnector(base.TestCase):
    def setUp(self):
        super(TestInfobloxConnector, self).setUp()

        self.default_opts = self._prepare_options()
        self.connector = connector.InfobloxWAPIClient(self.default_opts)

    @staticmethod
    def _prepare_options():
        opts = mock.Mock()
        opts.host = 'infoblox.example.org'
        opts.wapi_version = 'v1.1'
        opts.username = 'admin'
        opts.password = 'password'
        opts.ssl_verify = False
        opts.http_pool_connections = 10
        opts.http_pool_maxsize = 10
        opts.http_request_timeout = 10
        return opts

    def test_create_object(self):
        objtype = 'network'
        payload = {'ip': '0.0.0.0'}

        with patch.object(requests.Session, 'post',
                          return_value=mock.Mock()) as patched_create:
            patched_create.return_value.status_code = 201
            patched_create.return_value.content = '{}'
            self.connector.create_object(objtype, payload)
            patched_create.assert_called_once_with(
                'https://infoblox.example.org/wapi/v1.1/network',
                data=payload,
                headers=self.connector.DEFAULT_HEADER,
                timeout=self.default_opts.http_request_timeout,
                verify=False
            )

    def test_create_object_with_extattrs(self):
        objtype = 'network'
        payload = {'extattrs': {'Subnet ID': {'value': 'fake_subnet_id'}},
                   'ip': '0.0.0.0'}
        with patch.object(requests.Session, 'post',
                          return_value=mock.Mock()) as patched_create:
            patched_create.return_value.status_code = 201
            patched_create.return_value.content = '{}'
            self.connector.create_object(objtype, payload)
            patched_create.assert_called_once_with(
                'https://infoblox.example.org/wapi/v1.1/network',
                data=payload,
                headers=self.connector.DEFAULT_HEADER,
                timeout=self.default_opts.http_request_timeout,
                verify=False
            )

    def test_get_object(self):
        objtype = 'network'
        payload = {'ip': '0.0.0.0'}

        with patch.object(requests.Session, 'get',
                          return_value=mock.Mock()) as patched_get:
            patched_get.return_value.status_code = 200
            patched_get.return_value.content = '{}'
            self.connector.get_object(objtype, payload)
            patched_get.assert_called_once_with(
                'https://infoblox.example.org/wapi/v1.1/network?ip=0.0.0.0',
                headers=self.connector.DEFAULT_HEADER,
                timeout=self.default_opts.http_request_timeout,
                verify=False
            )

    def test_get_objects_with_extattrs(self):
        objtype = 'network'
        payload = {'ip': '0.0.0.0'}
        extattrs = {
            'Subnet ID': {'value': 'fake_subnet_id'}
        }
        with patch.object(requests.Session, 'get',
                          return_value=mock.Mock()) as patched_get:
            patched_get.return_value.status_code = 200
            patched_get.return_value.content = '{}'
            self.connector.get_object(objtype, payload, extattrs=extattrs)
            patched_get.assert_called_once_with(
                'https://infoblox.example.org/wapi/'
                'v1.1/network?*Subnet ID=fake_subnet_id&ip=0.0.0.0',
                headers=self.connector.DEFAULT_HEADER,
                timeout=self.default_opts.http_request_timeout,
                verify=False
            )

    def test_update_object(self):
        ref = 'network'
        payload = {'ip': '0.0.0.0'}

        with patch.object(requests.Session, 'put',
                          return_value=mock.Mock()) as patched_update:
            patched_update.return_value.status_code = 200
            patched_update.return_value.content = '{}'
            self.connector.update_object(ref, payload)
            patched_update.assert_called_once_with(
                'https://infoblox.example.org/wapi/v1.1/network',
                data=payload,
                headers=self.connector.DEFAULT_HEADER,
                timeout=self.default_opts.http_request_timeout,
                verify=False
            )

    def test_delete_object(self):
        ref = 'network'
        with patch.object(requests.Session, 'delete',
                          return_value=mock.Mock()) as patched_delete:
            patched_delete.return_value.status_code = 200
            patched_delete.return_value.content = '{}'
            self.connector.delete_object(ref)
            patched_delete.assert_called_once_with(
                'https://infoblox.example.org/wapi/v1.1/network',
                headers=self.connector.DEFAULT_HEADER,
                timeout=self.default_opts.http_request_timeout,
                verify=False
            )

    def test_construct_url_absolute_path_fails(self):
        pathes = ('/starts_with_slash', '', None)
        for path in pathes:
            self.assertRaises(ValueError,
                              self.connector._construct_url, path)

    def test_construct_url_with_query_params_and_extattrs(self):
        query_params = {'some_option': 'some_value'}
        ext_attrs = {'Subnet ID': {'value': 'fake_subnet_id'}}
        url = self.connector._construct_url('network',
                                            query_params=query_params,
                                            extattrs=ext_attrs)
        self.assertEqual('https://infoblox.example.org/wapi/v1.1/network?'
                         '*Subnet ID=fake_subnet_id&some_option=some_value',
                         url)

    def test_construct_url_with_force_proxy(self):
        ext_attrs = {'Subnet ID': {'value': 'fake_subnet_id'}}
        url = self.connector._construct_url('network',
                                            extattrs=ext_attrs,
                                            force_proxy=True)
        self.assertEqual('https://infoblox.example.org/wapi/v1.1/network?'
                         '*Subnet ID=fake_subnet_id&_proxy_search=GM',
                         url)

    def test_get_object_with_proxy_flag(self):
        self.connector._get_object = mock.MagicMock(return_value=False)
        self.connector._construct_url = mock.MagicMock()
        self.connector.cloud_api_enabled = True

        result = self.connector.get_object('network', force_proxy=True)

        self.assertEqual(None, result)
        self.connector._construct_url.assert_called_with('network', {},
                                                         None, True)
        self.connector._get_object.called_with('network',
                                               self.connector._construct_url)

    def test_get_object_without_proxy_flag(self):
        self.connector._get_object = mock.MagicMock(return_value=False)
        self.connector._construct_url = mock.MagicMock()
        self.connector.cloud_api_enabled = True

        result = self.connector.get_object('network')

        self.assertEqual(None, result)
        construct_calls = [mock.call('network', {}, None, False),
                           mock.call('network', {}, None, force_proxy=True)]
        self.connector._construct_url.assert_has_calls(construct_calls)


class TestInfobloxConnectorStaticMethods(base.TestCase):
    def test_neutron_exception_is_raised_on_any_request_error(self):
        # timeout exception raises InfobloxTimeoutError
        f = mock.Mock()
        f.__name__ = 'mock'
        f.side_effect = req_exc.Timeout
        self.assertRaises(exceptions.InfobloxTimeoutError,
                          connector.reraise_neutron_exception(f))

        # all other request exception raises InfobloxConnectionError
        supported_exceptions = [req_exc.HTTPError,
                                req_exc.ConnectionError,
                                req_exc.ProxyError,
                                req_exc.SSLError,
                                req_exc.TooManyRedirects,
                                req_exc.InvalidURL]

        for exc in supported_exceptions:
            f.side_effect = exc
            self.assertRaises(exceptions.InfobloxConnectionError,
                              connector.reraise_neutron_exception(f))

    def test_exception_raised_for_non_authorized(self):
        response = mock.Mock()
        response.status_code = requests.codes.UNAUTHORIZED
        self.assertRaises(exceptions.InfobloxBadWAPICredential,
                          connector.InfobloxWAPIClient._validate_authorized,
                          response)

    def test_no_exceptions_for_ok_statuses(self):
        response = mock.Mock()
        ok_statuses = (requests.codes.OK,
                       requests.codes.CREATED,
                       requests.codes.ACCEPTED)
        for status_code in ok_statuses:
            response.status_code = status_code
            connector.InfobloxWAPIClient._validate_authorized(response)

    def test_non_cloud_api_detection(self):
        wapi_not_cloud = ('v1.4.1', 'v1.9/', 'v1.99', 'asd', '')
        for url in wapi_not_cloud:
            self.assertFalse(connector.InfobloxWAPIClient.is_cloud_wapi(url))

    def test_cloud_api_detection(self):
        wapi_cloud = ('v2.1/', '/v2.0/', 'v2.0.1',
                      'v3.0/', 'v11.0.1/')
        for url in wapi_cloud:
            self.assertTrue(connector.InfobloxWAPIClient.is_cloud_wapi(url))
