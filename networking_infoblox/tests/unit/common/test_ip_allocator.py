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

from networking_infoblox.neutron.common import ip_allocator
from networking_infoblox.tests import base


class FixedAddressAllocatorTestCase(base.TestCase):
    def setUp(self):
        super(FixedAddressAllocatorTestCase, self).setUp()
        self.ib_mock = mock.Mock()

        self.extattrs = 'test-extattrs'
        self.netview = 'some-test-net-view'
        self.mac = 'de:ad:be:ef:00:00'
        self.ip = '192.168.1.1'
        self.dnsview = 'some-dns-view'
        self.zone_auth = 'zone-auth'
        self.hostname = 'host1'
        self.dhcp_enabled = True

        options = {'use_host_record': False}

        self.allocator = ip_allocator.IPAllocator(self.ib_mock, options)

    def test_creates_fixed_address_on_allocate_ip(self):
        self.allocator.allocate_given_ip(
            self.netview, self.dnsview, self.zone_auth,
            self.hostname, self.mac, self.ip, self.extattrs)

        self.ib_mock.create_fixed_address_for_given_ip.assert_called_once_with(
            self.netview, self.mac, self.ip, self.extattrs)

    def test_creates_fixed_address_range_on_range_allocation(self):
        first_ip = '192.168.1.1'
        last_ip = '192.168.1.123'

        self.allocator.allocate_ip_from_range(
            self.netview, self.dnsview, self.zone_auth, self.hostname,
            self.mac, first_ip, last_ip, self.extattrs)

        self.ib_mock.create_fixed_address_from_range.assert_called_once_with(
            self.netview, self.mac, first_ip, last_ip, self.extattrs)

    def test_deletes_fixed_address(self):
        self.allocator.deallocate_ip(self.netview, self.dnsview, self.ip)

        self.ib_mock.delete_fixed_address.assert_called_once_with(self.netview,
                                                                  self.ip)


class HostRecordAllocatorTestCase(base.TestCase):
    def test_creates_host_record_on_allocate_ip(self):
        ib_mock = mock.MagicMock()

        netview = 'some-test-net-view'
        dnsview = 'some-dns-view'
        zone_auth = 'zone-auth'
        hostname = 'host1'
        mac = 'de:ad:be:ef:00:00'
        ip = '192.168.1.1'

        ib_mock.find_hostname.return_value = None
        options = {'use_host_record': True}

        allocator = ip_allocator.IPAllocator(ib_mock, options)
        allocator.allocate_given_ip(netview, dnsview, zone_auth, hostname,
                                    mac, ip)

        ib_mock.create_host_record_for_given_ip.assert_called_once_with(
            dnsview, zone_auth, hostname, mac, ip, mock.ANY, True)

    def test_creates_host_record_range_on_range_allocation(self):
        ib_mock = mock.MagicMock()

        netview = 'some-test-net-view'
        dnsview = 'some-dns-view'
        zone_auth = 'zone-auth'
        hostname = 'host1'
        mac = 'de:ad:be:ef:00:00'
        first_ip = '192.168.1.2'
        last_ip = '192.168.1.254'

        ib_mock.find_hostname.return_value = None
        options = {'use_host_record': True}

        allocator = ip_allocator.IPAllocator(ib_mock, options)
        allocator.allocate_ip_from_range(
            netview, dnsview, zone_auth, hostname, mac, first_ip, last_ip)

        ib_mock.create_host_record_from_range.assert_called_once_with(
            dnsview, netview, zone_auth, hostname,
            mac, first_ip, last_ip, mock.ANY, True)

    def test_deletes_host_record(self):
        ib_mock = mock.MagicMock()

        netview = 'some-test-net-view'
        dnsview = 'some-dns-view'
        ip = '192.168.1.2'

        options = {'use_host_record': True}

        allocator = ip_allocator.IPAllocator(ib_mock, options)
        allocator.deallocate_ip(netview, dnsview, ip)

        ib_mock.delete_host_record.assert_called_once_with(dnsview, ip)
