# Copyright 2010-2011 OpenStack Foundation
# Copyright (c) 2013 Hewlett-Packard Development Company, L.P.
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

import fixtures
import io
import os

from oslo_config import cfg
import oslo_messaging
from oslo_serialization import jsonutils

from oslotest import base


class TestCase(base.BaseTestCase):

    """Test case base class for all unit tests."""

    def setUp(self):
        super(TestCase, self).setUp()
        self.connector_fixture = ConnectorFixture()


class RpcTestCase(TestCase):

    """Test case base class for RPC capability."""

    def setUp(self):
        super(RpcTestCase, self).setUp()
        self.transport = oslo_messaging.get_transport(cfg.CONF, "fake://")

    def get_notifier(self, topic='testtopic', publisher_id='testpublisher'):
        return oslo_messaging.Notifier(self.transport, topic=topic,
                                       driver='messaging',
                                       publisher_id=publisher_id)


class ConnectorFixture(fixtures.Fixture):

    def __init__(self):
        super(ConnectorFixture, self).__init__()
        self.script_path = os.path.dirname(os.path.abspath(__file__))
        self.test_fixture_data_path = self.script_path + '/unit/etc'

    def get_object(self, fixture_data_filename):
        stream = io.FileIO("%s/%s" % (self.test_fixture_data_path,
                                      fixture_data_filename))
        obj_json = jsonutils.loads(stream.read())
        return obj_json


class FixtureResourceMap(object):

    FAKE_MEMBERS_WITHOUT_CLOUD = 'fake_members_without_cloud.json'
    FAKE_MEMBERS_WITH_CLOUD = 'fake_members_with_cloud.json'
    FAKE_MEMBER_LICENSES = 'fake_member_licenses.json'
    FAKE_MEMBER_DHCP = 'fake_member_dhcp.json'
    FAKE_MEMBER_DNS = 'fake_member_dns.json'
    FAKE_NETWORKVIEW_WITHOUT_CLOUD = 'fake_networkview_without_cloud.json'
    FAKE_NETWORKVIEW_WITH_CLOUD = 'fake_networkview_with_cloud.json'
    FAKE_NETWORK_WITHOUT_CLOUD = 'fake_network_without_cloud.json'
    FAKE_NETWORK_WITH_CLOUD = 'fake_network_with_cloud.json'
    FAKE_GRID_MASTER_GRID_CONFIGURATION = \
        'fake_grid_master_grid_configuration.json'
    FAKE_DNS_VIEW = 'fake_dns_view.json'
