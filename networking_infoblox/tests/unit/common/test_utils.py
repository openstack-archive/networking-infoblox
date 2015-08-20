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

    def test_non_cloud_api_detection(self):
        wapi_not_cloud = ('v1.4.1', 'v1.9/', 'v1.99', 'asd', '')
        for url in wapi_not_cloud:
            self.assertFalse(utils.is_cloud_wapi(url))

    def test_cloud_api_detection(self):
        wapi_cloud = ('v2.1/', '/v2.0/', 'v2.0.1',
                      'v3.0/', 'v11.0.1/')
        for url in wapi_cloud:
            self.assertTrue(utils.is_cloud_wapi(url))
