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

import six

from oslo_log import log as logging

from networking_infoblox.common import exceptions as ib_ex
from networking_infoblox.common import utils as ib_utils


LOG = logging.getLogger(__name__)


class Network(object):
    """Represents Infoblox Network

    Sample Infoblox 'network' object in JSON format:
    [
        {
            "_ref": "network/ZG5zLm5ldHdvcmskMTAuMzkuMTEuMC8yNC8w:
                     10.39.11.0/24/default",
            "members": [
                {
                    "_struct": "dhcpmember",
                    "ipv4addr": "10.39.11.123",
                    "name": "infoblox.localdomain"
                }
            ],
            "options": [
                {
                    "name": "dhcp-lease-time",
                    "num": 51,
                    "use_option": false,
                    "value": "43200",
                    "vendor_class": "DHCP"
                },
                {
                    "name": "domain-name-servers",
                    "num": 6,
                    "use_option": true,
                    "value": "10.39.11.123",
                    "vendor_class": "DHCP"
                },
                {
                    "name": "routers",
                    "num": 3,
                    "use_option": false,
                    "value": "10.39.11.1",
                    "vendor_class": "DHCP"
                }
            ]
        }
    ]
    """
    DNS_NAMESERVERS_OPTION = 'domain-name-servers'

    def __init__(self):
        self.nios_type = 'network'
        self.members = []
        self.options = []
        self.member_ips = []
        self.nios_reference = None
        self.ref = None

    def __repr__(self):
        return "{0}".format(self.to_dict())

    @staticmethod
    def from_dict(ib_network):
        net = Network()
        net.members = ib_network['members']
        net.options = ib_network['options']

        for member in net.members:
            net.member_ips.append(member['ipv4addr'])

        net.ref = ib_network['_ref']
        return net

    @property
    def dns_nameservers(self):
        # NOTE: The behaviour of the WAPI is as follows:
        # * If the subnet created without domain-name-servers option it will
        # be absent in the options list.
        # * If the subnet created with domain-name-servers option and then
        # it's cleared by update operation, the option will be present in
        # the list, will carry the last data, but will have use_option = False
        # Both cases mean that there are NO specified nameservers on NIOS.
        dns_nameservers = []
        for opt in self.options:
            if self._is_dns_option(opt):
                if opt.get('use_option', True):
                    dns_nameservers = opt['value'].split(',')
                    break
        return dns_nameservers

    @dns_nameservers.setter
    def dns_nameservers(self, value):
        for opt in self.options:
            if self._is_dns_option(opt):
                if value:
                    opt['value'] = ",".join(value)
                    opt['use_option'] = True
                else:
                    opt['use_option'] = False
                break
        else:
            if value:
                self.options.append(dict(
                    name=self.DNS_NAMESERVERS_OPTION,
                    value=",".join(value),
                    use_option=True
                ))

    def has_dns_members(self):
        for opt in self.options:
            if self._is_dns_option(opt):
                return True
        return False

    def _is_member_ip(self, ip):
        return ip in self.member_ips

    def update_member_ip_in_dns_nameservers(self, relay_ip):
        for opt in self.options:
            if self._is_dns_option(opt):
                original_value = opt['value'].split(',')
                original_value.insert(0, relay_ip)
                opt['value'] = ",".join(
                    [val for val in original_value
                        if val and not self._is_member_ip(val)])
                return

    def to_dict(self):
        return {'members': self.members, 'options': self.options}

    @staticmethod
    def _is_dns_option(option):
        return option['name'] == Network.DNS_NAMESERVERS_OPTION


class IPAddress(object):

    def __init__(self, ip=None, mac=None, use_dhcp=True):
        self.ip = ip
        self.mac = mac
        self.configure_for_dhcp = use_dhcp
        self.hostname = None
        self.dns_zone = None
        self.fqdn = None

    def __eq__(self, other):
        if isinstance(other, six.string_types):
            return self.ip == other
        elif isinstance(other, self.__class__):
            return self.ip == other.ip and self.dns_zone == other.dns_zone
        return False


class IPv4(IPAddress):

    def to_dict(self, add_host=False):
        d = {"ipv4addr": self.ip,
             "configure_for_dhcp": self.configure_for_dhcp}
        if self.fqdn and add_host:
            d['host'] = self.fqdn
        if self.mac:
            d['mac'] = self.mac
        return d

    def __repr__(self):
        return "IPv4Addr{0}".format(self.to_dict())

    @staticmethod
    def from_dict(d):
        ip = d.get('ipv4addr')
        if not ib_utils.is_valid_ip(ip):
            raise ib_ex.InfobloxInvalidIp(ip=ip)

        ipv4obj = IPv4()
        host = d.get('host', 'unknown.unknown')
        hostname, _, dns_zone = host.partition('.')
        ipv4obj.ip = ip
        ipv4obj.mac = d.get('mac')
        ipv4obj.configure_for_dhcp = d.get('configure_for_dhcp')
        ipv4obj.hostname = hostname
        ipv4obj.zone_auth = dns_zone
        ipv4obj.fqdn = host
        return ipv4obj


class IPv6(IPAddress):

    def to_dict(self, add_host=False):
        d = {"ipv6addr": self.ip,
             "configure_for_dhcp": self.configure_for_dhcp}
        if self.fqdn and add_host:
            d['host'] = self.fqdn
        if self.mac:
            d['duid'] = ib_utils.generate_duid(self.mac)
        return d

    def __repr__(self):
        return "IPv6Addr{0}".format(self.to_dict())

    @staticmethod
    def from_dict(d):
        ip = d.get('ipv6addr')
        if not ib_utils.is_valid_ip(ip):
            raise ib_ex.InfobloxInvalidIp(ip=ip)

        ipv6obj = IPv6()
        host = d.get('host', 'unknown.unknown')
        hostname, _, dns_zone = host.partition('.')
        ipv6obj.ip = ip
        ipv6obj.duid = d.get('duid')
        ipv6obj.configure_for_dhcp = d.get('configure_for_dhcp')
        ipv6obj.hostname = hostname
        ipv6obj.zone_auth = dns_zone
        ipv6obj.fqdn = host
        return ipv6obj


class IPAllocationObject(object):

    @staticmethod
    def next_available_ip_from_cidr(net_view_name, cidr):
        return ('func:nextavailableip:'
                '{cidr:s},{net_view_name:s}').format(**locals())

    @staticmethod
    def next_available_ip_from_range(net_view_name, first_ip, last_ip):
        return ('func:nextavailableip:'
                '{first_ip}-{last_ip},{net_view_name}').format(**locals())


class HostRecord(IPAllocationObject):

    def __init__(self, use_dhcp=True):
        self.type = 'record:host'
        self._zone_auth = None
        self.ips = []
        self.ref = None
        self.name = None
        self.dns_view = None
        self.extattrs = None
        self.configure_for_dhcp = use_dhcp

    def __repr__(self):
        return "HostRecord{0}".format(self.to_dict())

    def __eq__(self, other):
        return (isinstance(other, self.__class__) and
                self.ips == other.ips and
                self.name == other.name and
                self.dns_view == other.dns_view)

    @property
    def zone_auth(self):
        return self._zone_auth

    @zone_auth.setter
    def zone_auth(self, value):
        if value:
            self._zone_auth = value.lstrip('.')

    def to_dict(self):
        return {'ips': self.ips,
                'ref': self.ref,
                'name': self.name,
                'dns_view': self.dns_view}


class HostRecordIPv4(HostRecord):
    """Represents Infoblox HostRecord IPv4

    Sample Infoblox host record object in JSON format:
    {
        u'_ref': u'record:host/ZG5zLmhvc3QkLl9kZWZhdWx0LmNvbS5nbG9iYWwuY22NA
                   :test_host_name.testsubnet.cloud.global.com/default',
        u'ipv4addrs': [
            {
                u'configure_for_dhcp': False,
                u'_ref': u'record:host_ipv4addr/lMmQ3ZjkuM4Zj5Mi00Y2:22.0.0.2/
                         test_host_name.testsubnet.cloud.global.com/default',
                u'ipv4addr': u'22.0.0.2',
                u'mac': u'fa:16:3e:29:87:70',
                u'host': u'2c8f8e97-0d92-4cac-a350-096ff2b79.cloud.global.com'
            }
        ],
        u'extattrs': {
            u'Account': {u'value': u'8a21c40495f04f30a1b2dc6fd1d9ed1a'},
            u'Cloud API Owned': {u'value': u'True'},
            u'VM ID': {u'value': u'None'},
            u'IP Type': {u'value': u'Fixed'},
            u'CMP Type': {u'value': u'OpenStack'},
            u'Port ID': {u'value': u'136ef9ad-9c88-41ea-9fa6-bd48d8ec789a'},
            u'Tenant ID': {u'value': u'00fd80791dee4112bb538c872b206d4c'}
        }
    }
    """
    return_fields = ['ipv4addrs', 'extattrs']

    def __repr__(self):
        return "HostRecord{0}".format(self.to_dict())

    def __eq__(self, other):
        return (isinstance(other, self.__class__) and
                self.ips == other.ips and
                self.name == other.name and
                self.dns_view == other.dns_view)

    @property
    def ip(self):
        if self.ips:
            return self.ips[0].ip

    @ip.setter
    def ip(self, ip_address):
        if self.ips:
            self.ips[0].ip = ip_address
        else:
            ip_obj = IPv4()
            ip_obj.ip = ip_address
            self.ips.append(ip_obj)

    @property
    def mac(self):
        if self.ips:
            return self.ips[0].mac

    @mac.setter
    def mac(self, mac_address):
        if self.ips:
            self.ips[0].mac = mac_address
        else:
            ip_obj = IPv4()
            ip_obj.mac = mac_address
            self.ips.append(ip_obj)

    @property
    def hostname(self):
        if self.ips:
            return self.ips[0].hostname

    @hostname.setter
    def hostname(self, name):
        if self.ips:
            self.ips[0].hostname = name
        else:
            ip_obj = IPv4()
            ip_obj.hostname = name
            self.ips.append(ip_obj)

    def to_dict(self):
        return {'view': self.dns_view,
                'name': '.'.join([self.hostname, self.zone_auth]),
                'extattrs': self.extattrs,
                'ipv4addrs': [ip.to_dict() for ip in self.ips]}

    @staticmethod
    def from_dict(hr_dict):
        ipv4addrs = hr_dict.get('ipv4addrs', None)
        if not ipv4addrs:
            raise ib_ex.HostRecordNotPresent()

        ipv4addr = ipv4addrs[0]
        ip = ipv4addr['ipv4addr']
        if not ib_utils.is_valid_ip(ip):
            raise ib_ex.InfobloxInvalidIp(ip=ip)
        host = ipv4addr.get('host', 'unknown.unknown')
        hostname, _, dns_zone = host.partition('.')

        host_record = HostRecordIPv4()
        host_record.hostname = hostname
        host_record.zone_auth = dns_zone
        host_record.ref = hr_dict.get('_ref')
        host_record.ips = [IPv4.from_dict(ip_addr) for ip_addr in ipv4addrs]
        host_record.extattrs = hr_dict.get('extattrs')
        return host_record

    @property
    def zone_auth(self):
        if self.ips:
            return self.ips[0].zone_auth

    @zone_auth.setter
    def zone_auth(self, value):
        if value:
            self.ips[0].zone_auth = value.lstrip('.')


class HostRecordIPv6(HostRecord):
    """Represents Infoblox HostRecord IPv6

    Sample Infoblox host record object in JSON format:
    {
        u'_ref': u'record:host/ZG5zLmhvc3QkLl9kZWZhdWx0LmNvbS5nbG9iYWwuYMQ
                   :test_host_name.testsubnet.cloud.global.com/default',
        u'ipv6addrs': [
            {
                u'configure_for_dhcp': False,
                u'_ref': u'record:host_ipv6addr/ZG5zLmhvc3RfYWRkcmV:2607%33A2/
                         test_host_name.testsubnet/default',
                u'host': u'ea30c45d-6385-43-2e4fea2859de.cloud.global.com',
                u'duid': u'00:6f:6d:ba:fa:16:3e:86:40:e3',
                u'ipv6addr': u'2607:f0d0:1002:51::2'
            }
        ],
        u'extattrs': {
                        u'Account': {u'value':
                                        u'8a21c40495f04f30a1b2dc6fd1d9ed1a'},
                        u'Port ID': {u'value':
                                        u'77c2ee08-32bf-4cd6-a24f-586ca91bd533'},
                        u'VM ID': {u'value': u'None'},
                        u'IP Type': {u'value': u'Fixed'},
                        u'CMP Type': {u'value': u'OpenStack'},
                        u'Cloud API Owned': {u'value': u'True'},
                        u'Tenant ID': {u'value':
                                       u'00fd80791dee4112bb538c872b206d4c'}
                     }
    }
    """
    return_fields = ['ipv6addrs', 'extattrs']

    def to_dict(self):
        return {'view': self.dns_view,
                'name': '.'.join([self.hostname, self.zone_auth]),
                'extattrs': self.extattrs,
                'ipv6addrs': [
                    {'configure_for_dhcp': self.configure_for_dhcp,
                     'ipv6addr': self.ip,
                     'duid': ib_utils.generate_duid(self.mac)}
                ]}

    @staticmethod
    def from_dict(hr_dict):
        ipv6addrs = hr_dict.get('ipv6addrs', None)
        if not ipv6addrs:
            raise ib_ex.HostRecordNotPresent()

        ipv6addr = ipv6addrs[0]
        ip = ipv6addr['ipv6addr']
        if not ib_utils.is_valid_ip(ip):
            raise ib_ex.InfobloxInvalidIp(ip=ip)
        host = ipv6addr.get('host', 'unknown.unknown')
        mac = ipv6addr.get('mac')

        hostname, _, dns_zone = host.partition('.')

        host_record = HostRecordIPv6()
        host_record.hostname = hostname
        host_record.zone_auth = dns_zone
        host_record.mac = mac
        host_record.ip = ip
        host_record.ref = hr_dict.get('_ref')
        return host_record

    @property
    def ip(self):
        if self.ips:
            return self.ips[0].ip

    @ip.setter
    def ip(self, ip_address):
        if self.ips:
            self.ips[0].ip = ip_address
        else:
            ip_obj = IPv6()
            ip_obj.ip = ip_address
            self.ips.append(ip_obj)

    @property
    def mac(self):
        if self.ips:
            return self.ips[0].mac

    @mac.setter
    def mac(self, mac_address):
        if self.ips:
            self.ips[0].mac = mac_address
        else:
            ip_obj = IPv6()
            ip_obj.mac = mac_address
            self.ips.append(ip_obj)

    @property
    def hostname(self):
        if self.ips:
            return self.ips[0].hostname

    @hostname.setter
    def hostname(self, name):
        if self.ips:
            self.ips[0].hostname = name
        else:
            ip_obj = IPv6()
            ip_obj.hostname = name
            self.ips.append(ip_obj)


class FixedAddress(IPAllocationObject):

    def __init__(self):
        self.type = 'fixedaddress'
        self.ip = None
        self.net_view = None
        self.mac = None
        self.duid = None
        self.extattrs = None
        self.ref = None

    def __repr__(self):
        return "FixedAddress({0})".format(self.to_dict())

    def to_dict(self):
        return {'ip': self.ip,
                'net_view': self.net_view,
                'mac': self.mac,
                'duid': self.duid}


class FixedAddressIPv4(FixedAddress):

    def __init__(self):
        super(FixedAddressIPv4, self).__init__()
        self.type = 'fixedaddress'

        self.return_fields = ['ipv4addr',
                              'mac',
                              'network_view',
                              'extattrs']

    def to_dict(self):
        return {'mac': self.mac,
                'network_view': self.net_view,
                'ipv4addr': self.ip,
                'extattrs': self.extattrs}

    @staticmethod
    def from_dict(fixed_address_dict):
        ip = fixed_address_dict.get('ipv4addr')
        if not ib_utils.is_valid_ip(ip):
            raise ib_ex.InfobloxInvalidIp(ip=ip)

        fa = FixedAddress()
        fa.ip = ip
        fa.mac = fixed_address_dict.get('mac')
        fa.net_view = fixed_address_dict.get('network_view')
        fa.extattrs = fixed_address_dict.get('extattrs')
        fa.ref = fixed_address_dict.get('_ref')
        return fa


class FixedAddressIPv6(FixedAddress):

    def __init__(self):
        super(FixedAddressIPv6, self).__init__()
        self.type = 'ipv6fixedaddress'

        self.return_fields = ['ipv6addr',
                              'duid',
                              'network_view',
                              'extattrs']

    def to_dict(self):
        return {'duid': ib_utils.generate_duid(self.mac),
                'network_view': self.net_view,
                'ipv6addr': self.ip,
                'extattrs': self.extattrs}

    @staticmethod
    def from_dict(fixed_address_dict):
        ip = fixed_address_dict.get('ipv6addr')
        if not ib_utils.is_valid_ip(ip):
            raise ib_ex.InfobloxInvalidIp(ip=ip)

        fa = FixedAddress()
        fa.ip = ip
        fa.mac = fixed_address_dict.get('mac')
        fa.net_view = fixed_address_dict.get('network_view')
        fa.extattrs = fixed_address_dict.get('extattrs')
        fa.ref = fixed_address_dict.get('_ref')
        return fa


class Member(object):
    def __init__(self, ip, name):
        self.ip = ip
        self.name = name

    def __eq__(self, other):
        return self.ip == other.ip and self.name == other.name

    def __repr__(self):
        return 'Member(IP={ip}, name={name})'.format(ip=self.ip,
                                                     name=self.name)
