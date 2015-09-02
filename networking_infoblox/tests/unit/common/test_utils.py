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

from networking_infoblox.common import utils
from networking_infoblox.tests import base


class TestUtils(base.TestCase):

    def test_is_valid_ip(self):
        ips = ('192.168.0.1',
               '8.8.8.8',
               'fffe::1')
        for ip in ips:
            self.assertEqual(True, utils.is_valid_ip(ip))

    def test_is_invalid_ip(self):
        ips = ('192.data.0.1',
               'text',
               None,
               '192.168.159.658')
        for ip in ips:
            self.assertEqual(False, utils.is_valid_ip(ip))
