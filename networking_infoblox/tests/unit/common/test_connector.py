# vim: tabstop=4 shiftwidth=4 softtabstop=4
#
# Copyright 2014 OpenStack LLC.
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


class UrlMatcher(object):
    def __init__(self, url, obj):
        self.url = url
        self.obj = obj

    def __eq__(self, actual_url):
        return self.url in actual_url and self.obj in actual_url


class TestInfobloxConnector(base.TestCase):
    def setUp(self):
        super(TestInfobloxConnector, self).setUp()

        self.default_opts = self._prepare_options()
        self.connector = connector.HttpClient(self.default_opts)

    @staticmethod
    def _prepare_options():
        opts = mock.Mock()
        opts.wapi_url = 'https://infoblox.example.org/wapi/v1.1/'
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
                headers={'Content-type': 'application/json'},
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
                headers={'Content-type': 'application/json'},
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
                headers={'Content-type': 'application/json'},
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
                headers={'Content-type': 'application/json'},
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
                headers={'Content-type': 'application/json'},
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
                headers={'Content-type': 'application/json'},
                timeout=self.default_opts.http_request_timeout,
                verify=False
            )

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
