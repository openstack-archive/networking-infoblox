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

import mock
import six

#from neutron.ipam.drivers.infoblox.common import exceptions as ib_exc
from neutron.ipam.drivers.infoblox.common import ibom
#from neutron.ipam.drivers.infoblox.common import ibo
from neutron.tests import base


class PayloadMatcher(object):
    ANYKEY = 'MATCH_ANY_KEY'

    def __init__(self, expected_values):
        self.args = expected_values

    def __eq__(self, actual):
        expected = []

        for key, expected_value in six.iteritems(self.args):
            expected.append(self._verify_value_is_expected(actual, key,
                                                           expected_value))

        return all(expected)

    def __repr__(self):
        return "Expected args: %s" % self.args

    def _verify_value_is_expected(self, d, key, expected_value):
        found = False
        if not isinstance(d, dict):
            return False

        for k in d:
            if isinstance(d[k], dict):
                found = self._verify_value_is_expected(d[k], key,
                                                       expected_value)
            if isinstance(d[k], list):
                if k == key and d[k] == expected_value:
                    return True
                for el in d[k]:
                    found = self._verify_value_is_expected(el, key,
                                                           expected_value)

                    if found:
                        return True
            if (key == k or key == self.ANYKEY) and d[k] == expected_value:
                return True
        return found


class ObjectManipulatorTestCase(base.BaseTestCase):

    def test_create_network_view(self):
        connector = mock.Mock()
        connector.get_object.return_value = None
        connector.create_object.return_value = None

        ib_obj_mgr = ibom.InfobloxObjectManager(connector)

        net_view_name = 'test_net_view_name'
        ib_obj_mgr.create_network_view(net_view_name, mock.ANY)

        matcher = PayloadMatcher({'name': net_view_name})
        connector.get_object.assert_called_once_with('networkview', matcher,
                                                     None, proxy=False)
        connector.create_object.assert_called_once_with('networkview',
                                                        matcher, mock.ANY)

    # def test_create_network(self):
    #     network_view = 'net-view-name'
    #     cidr = '192.168.1.0/24'
    #     nameservers = []
    #     dhcp_members = ['', '']
    #     gateway_ip = '192.168.1.1'
    #     expected_members = members[0].ip
    #     extattrs = mock.Mock()
    #
    #     connector = mock.Mock()
    #     ib_obj_mgr = ibom.InfobloxObjectManager(connector)
    #
    #     ibom.create_network(network_view, cidr, nameservers, members,
    #                         gateway_ip, extattrs)
    #
    #     assert not connector.get_object.called
    #     matcher = PayloadMatcher({'ipv4addr': expected_members})
    #     connector.create_object.assert_called_once_with('network', matcher,
    #                                                     None)
