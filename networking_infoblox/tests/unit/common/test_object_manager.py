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

from neutron.tests import base

from networking_infoblox.common import exceptions
from networking_infoblox.common import object_manager as om
from networking_infoblox.common import objects


class PayloadMatcher(object):
    ANYKEY = 'MATCH_ANY_KEY'

    def __init__(self, expected_values):
        self.args = expected_values

    def __eq__(self, actual):
        expected = []

        for key, expected_value in self.args.iteritems():
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
    EXT_ATTRS = {'Tenant ID': {'value': '40501209848593'}}

    def test_create_net_view_creates_network_view_object(self):
        connector = mock.Mock()
        connector.get_object.return_value = None
        connector.create_object.return_value = None

        ibom = om.InfobloxObjectManager(connector)

        net_view_name = 'test_net_view_name'
        ibom.create_network_view(net_view_name, self.EXT_ATTRS)

        get_matcher = PayloadMatcher({'name': net_view_name})
        create_matcher = PayloadMatcher({'name': net_view_name,
                                         'extattrs': self.EXT_ATTRS})
        connector.get_object.assert_called_once_with(
            'networkview', get_matcher, None, proxy=mock.ANY)
        connector.create_object.assert_called_once_with(
            'networkview', create_matcher, mock.ANY)

    def test_create_host_record_creates_host_record_object(self):
        dns_view_name = 'test_dns_view_name'
        zone_auth = 'test.dns.zone.com'
        hostname = 'test_hostname'
        ip = '192.168.0.1'
        mac = 'aa:bb:cc:dd:ee:ff'

        sample_host_record = objects.HostRecordIPv4()
        sample_host_record.hostname = hostname
        sample_host_record.zone_auth = zone_auth
        sample_host_record.ip = ip

        connector = mock.Mock()
        connector.create_object.return_value = sample_host_record.to_dict()

        ibom = om.InfobloxObjectManager(connector)

        ibom.create_host_record_for_given_ip(dns_view_name, zone_auth,
                                             hostname, mac, ip, self.EXT_ATTRS,
                                             True)

        exp_payload = {
            'name': 'test_hostname.test.dns.zone.com',
            'view': dns_view_name,
            'extattrs': self.EXT_ATTRS,
            'ipv4addrs': [
                {'mac': mac, 'configure_for_dhcp': True, 'ipv4addr': ip}
            ]
        }

        connector.create_object.assert_called_once_with('record:host',
                                                        exp_payload,
                                                        mock.ANY)

    def test_create_host_record_range_create_host_record_object(self):
        dns_view_name = 'test_dns_view_name'
        zone_auth = 'test.dns.zone.com'
        hostname = 'test_hostname'
        mac = 'aa:bb:cc:dd:ee:ff'
        net_view_name = 'test_net_view_name'
        first_ip = '192.168.0.1'
        last_ip = '192.168.0.254'

        sample_host_record = objects.HostRecordIPv4()
        sample_host_record.hostname = hostname
        sample_host_record.zone_auth = zone_auth
        sample_host_record.ip = first_ip
        sample_host_record.view = dns_view_name

        connector = mock.Mock()
        connector.create_object.return_value = sample_host_record.to_dict()

        ibom = om.InfobloxObjectManager(connector)

        ibom.create_host_record_from_range(
            dns_view_name, net_view_name, zone_auth, hostname, mac, first_ip,
            last_ip, self.EXT_ATTRS, True)

        next_ip = \
            'func:nextavailableip:192.168.0.1-192.168.0.254,test_net_view_name'
        exp_payload = {
            'name': 'test_hostname.test.dns.zone.com',
            'view': dns_view_name,
            'extattrs': self.EXT_ATTRS,
            'ipv4addrs': [
                {'mac': mac, 'configure_for_dhcp': True, 'ipv4addr': next_ip}
            ]
        }

        connector.create_object.assert_called_once_with(
            'record:host', exp_payload, mock.ANY)

    def test_delete_host_record_deletes_host_record_object(self):
        connector = mock.Mock()
        connector.get_object.return_value = mock.MagicMock()

        ibom = om.InfobloxObjectManager(connector)

        dns_view_name = 'test_dns_view_name'
        ip_address = '192.168.0.254'

        ibom.delete_host_record(dns_view_name, ip_address)

        matcher = PayloadMatcher({'view': dns_view_name,
                                  PayloadMatcher.ANYKEY: ip_address})
        connector.get_object.assert_called_once_with(
            'record:host', matcher, ['ipv4addrs'], proxy=mock.ANY)
        connector.delete_object.assert_called_once_with(mock.ANY)

    def test_get_network_gets_network_object(self):
        connector = mock.Mock()
        connector.get_object.return_value = mock.MagicMock()

        ibom = om.InfobloxObjectManager(connector)

        net_view_name = 'test_dns_view_name'
        cidr = '192.168.0.0/24'

        ibom.get_network(net_view_name, cidr)

        matcher = PayloadMatcher({'network_view': net_view_name,
                                  'network': cidr})
        connector.get_object.assert_called_once_with('network',
                                                     matcher,
                                                     mock.ANY,
                                                     proxy=mock.ANY)

    def test_throws_network_not_available_on_get_network(self):
        connector = mock.Mock()
        connector.get_object.return_value = None

        ibom = om.InfobloxObjectManager(connector)

        net_view_name = 'test_dns_view_name'
        cidr = '192.168.0.0/24'

        self.assertRaises(exceptions.InfobloxNetworkNotAvailable,
                          ibom.get_network, net_view_name, cidr)

        matcher = PayloadMatcher({'network_view': net_view_name,
                                  'network': cidr})
        connector.get_object.assert_called_once_with('network',
                                                     matcher,
                                                     mock.ANY,
                                                     proxy=mock.ANY)

    def test_object_is_not_created_if_already_exists(self):
        connector = mock.Mock()
        connector.get_object.return_value = mock.MagicMock()

        ibom = om.InfobloxObjectManager(connector)

        net_view_name = 'test_dns_view_name'

        ibom.create_network_view(net_view_name, self.EXT_ATTRS)

        matcher = PayloadMatcher({'name': net_view_name})
        connector.get_object.assert_called_once_with(
            'networkview', matcher, None, proxy=mock.ANY)
        assert not connector.create_object.called

    def test_get_member_gets_member_object(self):
        connector = mock.Mock()
        connector.get_object.return_value = None

        ibom = om.InfobloxObjectManager(connector)

        member = objects.Member(name='member1', ip='some-ip')

        ibom.get_member(member)

        matcher = PayloadMatcher({'host_name': member.name})
        connector.get_object.assert_called_once_with('member', matcher)

    def test_restart_services_calls_infoblox_function(self):
        connector = mock.Mock()
        connector.get_object.return_value = mock.MagicMock()

        ibom = om.InfobloxObjectManager(connector)

        member = objects.Member(name='member1', ip='some-ip')

        ibom.restart_all_services(member)

        connector.call_func.assert_called_once_with(
            'restartservices', mock.ANY, mock.ANY)

    def test_update_network_updates_object(self):
        ref = 'infoblox_object_id'
        opts = 'infoblox_options'

        connector = mock.Mock()
        ib_network = mock.Mock()
        ib_network.ref = ref
        ib_network.options = opts

        ibom = om.InfobloxObjectManager(connector)

        ibom.update_network_options(ib_network)

        connector.update_object.assert_called_once_with(ref, {'options': opts},
                                                        mock.ANY)

    def test_update_network_updates_eas_if_not_null(self):
        ref = 'infoblox_object_id'
        opts = 'infoblox_options'
        eas = 'some-eas'

        connector = mock.Mock()
        ib_network = mock.Mock()
        ib_network.ref = ref
        ib_network.options = opts

        ibom = om.InfobloxObjectManager(connector)

        ibom.update_network_options(ib_network, eas)

        connector.update_object.assert_called_once_with(ref, {'options': opts,
                                                              'extattrs': eas},
                                                        mock.ANY)

    def test_member_is_assigned_as_list_on_network_create(self):
        net_view = 'net-view-name'
        cidr = '192.168.1.0/24'
        nameservers = []
        members = [
            objects.Member(name='just-a-single-member-ip', ip='some-ip')
        ]
        gateway_ip = '192.168.1.1'
        expected_members = members[0].ip
        extattrs = mock.Mock()

        connector = mock.Mock()
        ibom = om.InfobloxObjectManager(connector)

        ibom.create_network(net_view, cidr, nameservers, members, gateway_ip,
                            extattrs)

        assert not connector.get_object.called
        matcher = PayloadMatcher({'ipv4addr': expected_members})
        connector.create_object.assert_called_once_with('network', matcher,
                                                        None)

    def test_create_ip_range_creates_range_object(self):
        net_view = 'net-view-name'
        start_ip = '192.168.1.1'
        end_ip = '192.168.1.123'
        disable = False

        connector = mock.Mock()
        connector.get_object.return_value = None

        ibom = om.InfobloxObjectManager(connector)
        ibom.create_ip_range(net_view, start_ip, end_ip, None, disable,
                             self.EXT_ATTRS)

        assert connector.get_object.called
        matcher = PayloadMatcher({'start_addr': start_ip,
                                  'end_addr': end_ip,
                                  'network_view': net_view,
                                  'extattrs': self.EXT_ATTRS,
                                  'disable': disable})
        connector.create_object.assert_called_once_with('range', matcher,
                                                        mock.ANY)

    def test_delete_ip_range_deletes_infoblox_object(self):
        net_view = 'net-view-name'
        start_ip = '192.168.1.1'
        end_ip = '192.168.1.123'

        connector = mock.Mock()
        connector.get_object.return_value = mock.MagicMock()

        ibom = om.InfobloxObjectManager(connector)

        ibom.delete_ip_range(net_view, start_ip, end_ip)

        matcher = PayloadMatcher({'start_addr': start_ip,
                                  'end_addr': end_ip,
                                  'network_view': net_view})
        connector.get_object.assert_called_once_with('range', matcher, None,
                                                     proxy=mock.ANY)
        connector.delete_object.assert_called_once_with(mock.ANY)

    def test_delete_network_deletes_infoblox_network(self):
        net_view = 'net-view-name'
        cidr = '192.168.1.0/24'

        connector = mock.Mock()
        connector.get_object.return_value = mock.MagicMock()

        ibom = om.InfobloxObjectManager(connector)

        ibom.delete_network(net_view, cidr)

        matcher = PayloadMatcher({'network_view': net_view,
                                  'network': cidr})
        connector.get_object.assert_called_once_with('network', matcher, None,
                                                     proxy=mock.ANY)
        connector.delete_object.assert_called_once_with(mock.ANY)

    def test_delete_network_view_deletes_infoblox_object(self):
        net_view = 'net-view-name'

        connector = mock.Mock()
        connector.get_object.return_value = mock.MagicMock()

        ibom = om.InfobloxObjectManager(connector)

        ibom.delete_network_view(net_view)

        matcher = PayloadMatcher({'name': net_view})
        connector.get_object.assert_called_once_with(
            'networkview', matcher, None, proxy=mock.ANY)
        connector.delete_object.assert_called_once_with(mock.ANY)

    def test_bind_names_updates_host_record(self):
        dns_view_name = 'dns-view-name'
        fqdn = 'host.global.com'
        ip = '192.168.1.1'
        extattrs = None

        connector = mock.Mock()
        connector.get_object.return_value = mock.MagicMock()

        ibom = om.InfobloxObjectManager(connector)

        ibom.bind_name_with_host_record(dns_view_name, ip, fqdn, extattrs)

        matcher = PayloadMatcher({'view': dns_view_name,
                                  PayloadMatcher.ANYKEY: ip})
        connector.get_object.assert_called_once_with('record:host', matcher,
                                                     None, proxy=mock.ANY)

        matcher = PayloadMatcher({'name': fqdn})
        connector.update_object.assert_called_once_with(mock.ANY, matcher,
                                                        mock.ANY)

    def test_create_dns_zone_creates_zone_auth_object(self):
        dns_view_name = 'dns-view-name'
        fqdn = 'host.global.com'
        member = objects.Member(name='member_name', ip='some-ip')
        zone_format = 'IPV4'

        connector = mock.Mock()
        connector.get_object.return_value = None

        ibom = om.InfobloxObjectManager(connector)

        ibom.create_dns_zone(dns_view_name, fqdn, [member],
                             zone_format=zone_format)

        matcher = PayloadMatcher({'view': dns_view_name,
                                  'fqdn': fqdn})
        connector.get_object.assert_called_once_with('zone_auth', matcher,
                                                     None, proxy=mock.ANY)

        matcher = PayloadMatcher({'view': dns_view_name,
                                  'fqdn': fqdn,
                                  'zone_format': zone_format,
                                  'name': member.name})
        connector.create_object.assert_called_once_with('zone_auth', matcher,
                                                        None)

    def test_create_dns_zone_with_grid_secondaries(self):
        dns_view_name = 'dns-view-name'
        fqdn = 'host.global.com'
        primary_dns_members = [objects.Member(name='member_primary',
                                              ip='some-ip')]
        secondary_dns_members = [objects.Member(name='member_secondary',
                                                ip='some-ip')]
        zone_format = 'IPV4'

        connector = mock.Mock()
        connector.get_object.return_value = None

        ibom = om.InfobloxObjectManager(connector)

        ibom.create_dns_zone(dns_view_name, fqdn, primary_dns_members,
                             secondary_dns_members, zone_format=zone_format)

        matcher = PayloadMatcher({'view': dns_view_name,
                                  'fqdn': fqdn})
        connector.get_object.assert_called_once_with('zone_auth', matcher,
                                                     None, proxy=mock.ANY)

        payload = {'view': dns_view_name,
                   'fqdn': fqdn,
                   'zone_format': zone_format,
                   'extattrs': {},
                   'grid_primary': [{'name': primary_dns_members[0].name,
                                     '_struct': 'memberserver'}],
                   'grid_secondaries': [{'name': member.name,
                                         '_struct': 'memberserver'}
                                        for member in secondary_dns_members]
                   }
        connector.create_object.assert_called_once_with('zone_auth', payload,
                                                        None)

    def test_create_host_record_throws_exception_on_error(self):
        dns_view_name = 'dns-view-name'
        hostname = 'host.global.com'
        mac = 'aa:bb:cc:dd:ee:ff'
        ip = '192.168.1.1'
        zone_auth = 'my.auth.zone.com'
        use_dhcp = True

        connector = mock.Mock()
        response = {'text': "Cannot find 1 available IP"}

        connector.create_object.side_effect = \
            exceptions.InfobloxCannotCreateObject(response=response,
                                                  objtype='host:record',
                                                  content='adsfasd',
                                                  code='1234')
        ibom = om.InfobloxObjectManager(connector)

        self.assertRaises(exceptions.InfobloxCannotAllocateIp,
                          ibom.create_host_record_for_given_ip,
                          dns_view_name, zone_auth, hostname, mac, ip,
                          self.EXT_ATTRS, use_dhcp)

    def test_create_dns_view_creates_view_object(self):
        net_view_name = 'net-view-name'
        dns_view_name = 'dns-view-name'

        connector = mock.Mock()
        connector.get_object.return_value = None

        ibom = om.InfobloxObjectManager(connector)

        ibom.create_dns_view(net_view_name, dns_view_name)

        matcher = PayloadMatcher({'name': dns_view_name,
                                  'network_view': net_view_name})
        connector.get_object.assert_called_once_with('view', matcher, None,
                                                     proxy=mock.ANY)
        connector.create_object.assert_called_once_with('view', matcher, None)

    def test_default_net_view_is_never_deleted(self):
        connector = mock.Mock()

        ibom = om.InfobloxObjectManager(connector)

        ibom.delete_network_view('default')

        assert not connector.delete_object.called


class TestInfobloxNetwork(base.BaseTestCase):

    def test_v4_network_is_loaded(self):
        network = om.InfobloxNetwork('some-view', '192.168.1.0/24')
        self.assertIsInstance(network, om.InfobloxNetworkV4)
        self.assertEqual(4, network.ip_version)
        self.assertEqual('network', network.object_type)

    def test_v6_network_is_loaded(self):
        network = om.InfobloxNetwork('some-view', 'ffde:2332::/24')
        self.assertIsInstance(network, om.InfobloxNetworkV6)
        self.assertEqual(6, network.ip_version)
        self.assertEqual('ipv6network', network.object_type)


class TestInfobloxHostRecord(base.BaseTestCase):

    def test_v4_hostrecord_is_loaded(self):
        host = om.InfobloxHostRecord('some-dns-view', '192.168.1.25')
        self.assertIsInstance(host, om.InfobloxHostRecordV4)
        self.assertEqual(4, host.ip_version)
        self.assertEqual('record:host', host.object_type)
        self.assertEqual('192.168.1.25', host.payload['ipv4addr'])

    def test_v6_network_is_loaded(self):
        host = om.InfobloxHostRecord('some-dns-view', 'ffde:2332::12')
        self.assertIsInstance(host, om.InfobloxHostRecordV6)
        self.assertEqual(6, host.ip_version)
        self.assertEqual('record:host', host.object_type)
        self.assertEqual('ffde:2332::12', host.payload['ipv6addr'])


class TestInfobloxIPRange(base.BaseTestCase):

    def test_v4_hostrecord_is_loaded(self):
        host = om.InfobloxIPRange('some-view', '192.168.1.25', '192.168.1.40')
        self.assertIsInstance(host, om.InfobloxIPRangeV4)
        self.assertEqual(4, host.ip_version)
        self.assertEqual('range', host.object_type)
        self.assertEqual('192.168.1.25', host.payload['start_addr'])
        self.assertEqual('192.168.1.40', host.payload['end_addr'])

    def test_v6_network_is_loaded(self):
        host = om.InfobloxIPRange('some-view', 'ffde::12', 'ffde::ffce')
        self.assertIsInstance(host, om.InfobloxIPRangeV6)
        self.assertEqual(6, host.ip_version)
        self.assertEqual('ipv6range', host.object_type)
        self.assertEqual('ffde::12', host.payload['start_addr'])
        self.assertEqual('ffde::ffce', host.payload['end_addr'])
