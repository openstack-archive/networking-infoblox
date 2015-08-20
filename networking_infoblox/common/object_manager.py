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

import netaddr

from oslo_log import log as logging
from neutron.i18n import _LI
from neutron.i18n import _LW

from networking_infoblox.common import connector
from networking_infoblox.common import exceptions as ib_ex
from networking_infoblox.common import ibo
from networking_infoblox.common import utils as ib_utils


LOG = logging.getLogger(__name__)


class IPBackend(object):

    def __init__(self, ib_obj_manager):
        self.ibom = ib_obj_manager

    def get_all_associated_objects(self, network_view, ip):
        obj_type = self.ib_ipaddr_object_name
        payload = {'network_view': network_view, 'ip_address': ip}
        return_fields = ['objects']
        assoc_objects = self.ibom._get_infoblox_object_or_none(obj_type,
                                                               payload,
                                                               return_fields,
                                                               proxy=True)
        if assoc_objects:
            return assoc_objects['objects']
        return []

    def network_exists(self, network_view, cidr):
        obj_type = self.ib_network_name
        payload = {'network_view': network_view, 'network': cidr}
        return_fields = ['options', 'members']
        try:
            network = self.ibom._get_infoblox_object_or_none(obj_type,
                                                             payload,
                                                             return_fields)
        except ib_ex.InfobloxSearchError:
            network = None
        return network is not None

    def delete_network(self, network_view, cidr):
        obj_type = self.ib_network_name
        payload = {'network_view': network_view, 'network': cidr}
        self.ibom._delete_infoblox_object(obj_type, payload)

    def delete_ip_range(self, network_view, start_ip, end_ip):
        obj_type = self.ib_range_name
        payload = {'start_addr': start_ip,
                   'end_addr': end_ip,
                   'network_view': network_view}
        self.ibom._delete_infoblox_object(obj_type, payload)

    def delete_ip_from_host_record(self, host_record, ip):
        obj_type = self.ib_ipaddrs_name
        host_record.ips.remove(ip)
        self.ibom._update_host_record_ips(obj_type, host_record)
        return host_record

    def delete_host_record(self, dns_view, ip_address):
        payload = {'view': dns_view, self.ib_ipaddr_name: ip_address}
        self.ibom._delete_infoblox_object('record:host', payload)

    def delete_fixed_address(self, network_view, ip):
        obj_type = self.ib_fixedaddress_name
        payload = {'network_view': network_view, self.ib_ipaddr_name: ip}
        self.ibom._delete_infoblox_object(obj_type, payload)

    def bind_name_with_host_record(self, dns_view, ip, name, extattrs):
        payload = {self.ib_ipaddr_name: ip,
                   'view': dns_view}
        update_kwargs = {'name': name, 'extattrs': extattrs}
        self.ibom._update_infoblox_object('record:host', payload,
                                          update_kwargs)

    def update_host_record_eas(self, dns_view, ip, extattrs):
        payload = {'view': dns_view, self.ib_ipaddr_name: ip}
        hr = self.ibom._get_infoblox_object_or_none('record:host', payload)
        if hr:
            ea = {'extattrs': extattrs}
            self.ibom._update_infoblox_object_by_ref(hr, ea)

    def update_fixed_address_eas(self, network_view, ip, extattrs):
        obj_type = self.ib_fixedaddress_name
        payload = {'network_view': network_view, self.ib_ipaddr_name: ip}
        fa = self.ibom._get_infoblox_object_or_none(obj_type, payload)
        if fa:
            ea = {'extattrs': extattrs}
            self.ibom._update_infoblox_object_by_ref(fa, ea)

    def update_dns_record_eas(self, dns_view, ip, extattrs):
        payload = {'view': dns_view, self.ib_ipaddr_name: ip}
        ea = {'extattrs': extattrs}

        fa = self.ibom._get_infoblox_object_or_none('record:a', payload)
        if fa:
            self.ibom._update_infoblox_object_by_ref(fa, ea)

        fa = self.ibom._get_infoblox_object_or_none('record:ptr', payload)
        if fa:
            self.ibom._update_infoblox_object_by_ref(fa, ea)


class IPv4Backend(IPBackend):

    ip_version = 4
    ib_ipaddr_name = 'ipv4addr'
    ib_ipaddrs_name = 'ipv4addrs'
    ib_ipaddr_object_name = 'ipv4address'
    ib_network_name = 'network'
    ib_fixedaddress_name = 'fixedaddress'
    ib_range_name = 'range'

    def create_network(self, network_view, cidr, nameservers=None,
                       dhcp_members=None, gateway_ip=None, relay_trel_ip=None,
                       extattrs=None):
        obj_type = self.ib_network_name
        payload = {'network_view': network_view,
                   'network': cidr,
                   'extattrs': extattrs}

        members_struct = []
        for member in dhcp_members:
            members_struct.append({'name': member.member_name,
                                   '_struct': 'dhcpmember'})
        payload['members'] = members_struct

        dhcp_options = []
        if nameservers:
            dhcp_options.append({'name': 'domain-name-servers',
                                 'value': ",".join(nameservers)})
        if gateway_ip:
            dhcp_options.append({'name': 'routers',
                                 'value': gateway_ip})
        if relay_trel_ip:
            dhcp_options.append({'name': 'dhcp-server-identifier',
                                 'num': 54,
                                 'value': relay_trel_ip})
        if dhcp_options:
            payload['options'] = dhcp_options

        return self.ibom._create_infoblox_object(obj_type, payload,
                                                 check_if_exists=False)

    def create_ip_range(self, network_view, start_ip, end_ip, cidr,
                        disable, extattrs):
        payload = {'start_addr': start_ip,
                   'end_addr': end_ip,
                   'extattrs': extattrs,
                   'network_view': network_view}
        ip_range = self.ibom._get_infoblox_object_or_none('range', payload)
        if not ip_range:
            payload['disable'] = disable
            ip_range = self.ibom._create_infoblox_object('range', payload,
                                                         check_if_exists=False)
        return ip_range

    def add_ip_to_record(self, host_record, ip, mac, use_dhcp):
        host_record.ips.append(ibo.IPv4(ip, mac, use_dhcp))
        ips = self.ibom._update_host_record_ips('ipv4addrs', host_record)
        hr = ibo.HostRecordIPv4.from_dict(ips)
        return hr

    @staticmethod
    def create_host_record(use_dhcp):
        return ibo.HostRecordIPv4(use_dhcp)

    def get_host_record(self, dns_view, ip):
        payload = {'view': dns_view,
                   'ipv4addr': ip}
        fields = ['ipv4addrs']
        hr_dict = self.ibom._get_infoblox_object_or_none('record:host',
                                                         payload,
                                                         return_fields=fields)
        if hr_dict:
            hr_obj = ibo.HostRecordIPv4.from_dict(hr_dict)
            return hr_obj
        return None

    @staticmethod
    def get_fixed_address():
        return ibo.FixedAddressIPv4()

    def bind_name_with_record_a(self, dns_view, ip, name, bind_list,
                                extattrs):
        # forward mapping
        if 'record:a' in bind_list:
            payload = {self.ib_ipaddr_name: ip,
                       'view': dns_view}
            additional_create_kwargs = {'name': name,
                                        'extattrs': extattrs}
            self.ibom._create_infoblox_object('record:a',
                                              payload,
                                              additional_create_kwargs,
                                              check_if_exists=True,
                                              update_if_exists=True)

        # reverse mapping
        if 'record:ptr' in bind_list:
            payload = {self.ib_ipaddr_name: ip,
                       'view': dns_view}
            additional_create_kwargs = {'ptrdname': name,
                                        'extattrs': extattrs}
            self.ibom._create_infoblox_object('record:ptr',
                                              payload,
                                              additional_create_kwargs,
                                              check_if_exists=True,
                                              update_if_exists=True)

    def unbind_name_from_record_a(self, dns_view, ip, name, unbind_list):
        if 'record:a' in unbind_list:
            payload = {'name': name,
                       self.ib_ipaddr_name: ip,
                       'view': dns_view}
            self.ibom._delete_infoblox_object('record:a', payload)

        if 'record:ptr' in unbind_list:
            payload = {'ptrdname': name,
                       'view': dns_view}
            self.ibom._delete_infoblox_object('record:ptr', payload)

    def find_hostname(self, dns_view, hostname):
        payload = {'name': hostname, 'view': dns_view}
        fields = ['ipv4addrs']
        hr_dict = self.ibom._get_infoblox_object_or_none('record:host',
                                                         payload,
                                                         return_fields=fields)
        if hr_dict:
            hr_obj = ibo.HostRecordIPv4.from_dict(hr_dict)
            return hr_obj
        return None


class IPv6Backend(IPBackend):

    ip_version = 6
    ib_ipaddr_name = 'ipv6addr'
    ib_ipaddrs_name = 'ipv6addrs'
    ib_ipaddr_object_name = 'ipv6address'
    ib_network_name = 'ipv6network'
    ib_fixedaddress_name = 'ipv6fixedaddress'
    ib_range_name = 'ipv6range'

    def create_ip_range(self, network_view, start_ip, end_ip, cidr,
                        disable, extattrs):
        payload = {'start_addr': start_ip,
                   'end_addr': end_ip,
                   'extattrs': extattrs,
                   'network': cidr,
                   'network_view': network_view}
        ip_range = self.ibom._get_infoblox_object_or_none('ipv6range', payload)
        if not ip_range:
            payload['disable'] = disable
            ip_range = self.ibom._create_infoblox_object(
                'ipv6range', payload, check_if_exists=False)
        return ip_range

    def add_ip_to_record(self, host_record, ip, mac, use_dhcp=True):
        host_record.ips.append(ibo.IPv6(ip, mac, use_dhcp))
        ips = self.ibom._update_host_record_ips('ipv6addrs', host_record)
        hr = ibo.HostRecordIPv6.from_dict(ips)
        return hr

    @staticmethod
    def create_host_record(use_dhcp):
        return ibo.HostRecordIPv6(use_dhcp)

    def get_host_record(self, dns_view, ip):
        payload = {'view': dns_view, 'ipv6addr': ip}
        fields = ['ipv6addrs']
        hr_dict = self.ibom._get_infoblox_object_or_none('record:host',
                                                         payload,
                                                         return_fields=fields)
        if hr_dict:
            hr_obj = ibo.HostRecordIPv6.from_dict(hr_dict)
            return hr_obj
        return None

    @staticmethod
    def get_fixed_address():
        return ibo.FixedAddressIPv6()

    def bind_name_with_record_a(self, dns_view, ip, name, bind_list,
                                extattrs):
        # forward mapping
        if 'record:aaaa' in bind_list:
            payload = {self.ib_ipaddr_name: ip,
                       'view': dns_view}
            additional_create_kwargs = {'name': name,
                                        'extattrs': extattrs}
            self.ibom._create_infoblox_object('record:aaaa',
                                              payload,
                                              additional_create_kwargs,
                                              check_if_exists=True,
                                              update_if_exists=True)

        # reverse mapping
        if 'record:ptr' in bind_list:
            payload = {self.ib_ipaddr_name: ip,
                       'view': dns_view}
            additional_create_kwargs = {'ptrdname': name,
                                        'extattrs': extattrs}
            self.ibom._create_infoblox_object('record:ptr',
                                              payload,
                                              additional_create_kwargs,
                                              check_if_exists=True,
                                              update_if_exists=True)

    def unbind_name_from_record_a(self, dns_view, ip, name, unbind_list):
        if 'record:aaaa' in unbind_list:
            payload = {'name': name,
                       self.ib_ipaddr_name: ip,
                       'view': dns_view}
            self.ibom._delete_infoblox_object('record:aaaa', payload)

        if 'record:ptr' in unbind_list:
            payload = {'ptrdname': name, 'view': dns_view}
            self.ibom._delete_infoblox_object('record:ptr', payload)

    def find_hostname(self, dns_view, hostname):
        payload = {'name': hostname, 'view': dns_view}
        fields = ['ipv6addrs']
        hr_dict = self.ibom._get_infoblox_object_or_none('record:host',
                                                         payload,
                                                         return_fields=fields)
        if hr_dict:
            hr_obj = ibo.HostRecordIPv6.from_dict(hr_dict)
            return hr_obj
        return None


class IPBackendFactory(object):

    @staticmethod
    def get(ib_obj_manager, ip):
        ip_version = ib_utils.get_ip_version(ip)
        if ip_version == 4:
            return IPv4Backend(ib_obj_manager)
        elif ip_version == 6:
            return IPv6Backend(ib_obj_manager)
        return None


class InfobloxObject(object):
    def __init__(self, obj_type, ip=None):
        self._object_type = obj_type
        self._payload = {}
        self._create_data = {}
        self._return_fields = []
        self._ip_version = self._determine_ip_version(ip)

    def __repr__(self):
        return "InfobloxObject{0}".format(self.to_dict())

    def to_dict(self):
        return {'object type': self.object_type,
                'payload': self.payload,
                'create_data': self.create_data,
                'return_fields': self.return_fields,
                'ip_version': self.ip_version}

    @property
    def payload(self):
        return self._payload

    @payload.setter
    def payload(self, data):
        self._payload = data

    @property
    def create_data(self):
        return self._create_data

    @create_data.setter
    def create_data(self, data):
        self._create_data = data

    @property
    def return_fields(self):
        return self._return_fields

    @return_fields.setter
    def return_fields(self, fields):
        self._return_fields = fields

    @property
    def object_type(self):
        return self._object_type

    @property
    def ip_version(self):
        return self._ip_version

    @ip_version.setter
    def ip_version(self, ip_ver):
        self._ip_version = ip_ver

    @staticmethod
    def _determine_ip_version(ip_in):
        ip_ver = 4
        if ip_in:
            if isinstance(ip_in, int):
                if ip_in == 6:
                    ip_ver = 6
                else:
                    ip_ver = 4
            else:
                if type(ip_in) is dict:
                    addr = ip_in['ip_address']
                else:
                    addr = ip_in
                try:
                    ip = netaddr.IPAddress(addr)
                except ValueError:
                    ip = netaddr.IPNetwork(addr)

                ip_ver = ip.version

        return ip_ver


class InfobloxNetworkView(InfobloxObject):
    def __init__(self, name, extattrs=None):
        super(InfobloxNetworkView, self).__init__('networkview')
        self.payload.update({'name': name, 'extattrs': extattrs})
        if extattrs:
            self.create_data.update({'extattrs': extattrs})


class InfobloxDNSView(InfobloxObject):
    def __init__(self, dnsview_name, netview_name=None):
        super(InfobloxDNSView, self).__init__('view')
        self.payload.update({'name': dnsview_name})
        if netview_name:
            self.payload.update({'network_view': netview_name})


class InfobloxNetwork(InfobloxObject):
    def __new__(cls, net_view_name, cidr, nameservers=None,
                members=None, gateway_ip=None, dhcp_trel_ip=None,
                network_extattrs=None):
        if InfobloxObject._determine_ip_version(cidr) == 6:
            return super(InfobloxNetwork, cls).__new__(
                InfobloxNetworkV6, net_view_name, cidr, nameservers,
                members, gateway_ip, dhcp_trel_ip, network_extattrs)
        else:
            return super(InfobloxNetwork, cls).__new__(
                InfobloxNetworkV4, net_view_name, cidr, nameservers,
                members, gateway_ip, dhcp_trel_ip, network_extattrs)

    def __init__(self, obj_type, ip_ver, net_view_name, cidr, nameservers=None,
                 members=None, gateway_ip=None, dhcp_trel_ip=None,
                 network_extattrs=None):

        super(InfobloxNetwork, self).__init__(obj_type, ip_ver)

        self.payload.update({'network_view': net_view_name,
                             'network': cidr})
        self.return_fields = ['options', 'members']

        if network_extattrs:
            self.create_data.update({'extattrs': network_extattrs})

        members_struct = []
        if members:
            members_struct = [member.specifier for member in members]

        self.create_data.update({'members': members_struct})

        dhcp_options = []
        if nameservers:
            dhcp_options.append({'name': 'domain-name-servers',
                                 'value': ",".join(nameservers)})

        if gateway_ip:
            dhcp_options.append({'name': 'routers',
                                 'value': gateway_ip})

        if dhcp_trel_ip:
            dhcp_options.append({'name': 'dhcp-server-identifier',
                                 'num': 54,
                                 'value': dhcp_trel_ip})

        if dhcp_options:
            self.create_data.update({'options': dhcp_options})


class InfobloxNetworkV4(InfobloxNetwork):
        def __init__(self, net_view_name, cidr, nameservers=None,
                     members=None, gateway_ip=None, dhcp_trel_ip=None,
                     network_extattrs=None):

            super(InfobloxNetworkV4, self).__init__(
                'network', 4, net_view_name, cidr, nameservers,
                members, gateway_ip, dhcp_trel_ip, network_extattrs)


class InfobloxNetworkV6(InfobloxNetwork):
        def __init__(self, net_view_name, cidr, nameservers=None,
                     members=None, gateway_ip=None, dhcp_trel_ip=None,
                     network_extattrs=None):

            super(InfobloxNetworkV6, self).__init__(
                'ipv6network', 6, net_view_name, cidr, nameservers,
                members, gateway_ip, dhcp_trel_ip, network_extattrs)


class InfobloxHostRecord(InfobloxObject):
    def __new__(cls, dnsview_name, ip, name=None, extattrs=None):
        if InfobloxObject._determine_ip_version(ip) == 6:
            return super(InfobloxHostRecord, cls).__new__(
                InfobloxHostRecordV6, dnsview_name, ip, name, extattrs)
        else:
            return super(InfobloxHostRecord, cls).__new__(
                InfobloxHostRecordV4, dnsview_name, ip, name, extattrs)

    def __init__(self, obj_type, ip_ver, dnsview_name, ip, name, extattrs):
        super(InfobloxHostRecord, self).__init__(obj_type, ip_ver)

        self.payload.update({'view': dnsview_name})

        if name:
            self.create_data.update({'name': name})
        if extattrs:
            self.create_data.update({'extattrs': extattrs})

    @property
    def host_record_type(self):
        pass


class InfobloxHostRecordV4(InfobloxHostRecord):
    def __init__(self, dnsview_name, ip, name=None, extattrs=None):
        super(InfobloxHostRecordV4, self).__init__(
            'record:host', 4, dnsview_name, ip, name, extattrs)
        self.payload.update({'ipv4addr': ip})
        self.return_fields = ['ipv4addrs']


class InfobloxHostRecordV6(InfobloxHostRecord):
    def __init__(self, dnsview_name, ip, name=None, extattrs=None):
        super(InfobloxHostRecordV6, self).__init__(
            'record:host', 6, dnsview_name, ip, name, extattrs)
        self.payload.update({'ipv6addr': ip})
        self.return_fields = ['ipv6addrs']


class InfobloxIPRange(InfobloxObject):
    def __new__(cls, netview_name, start_addr, end_addr,
                cidr=None, disable=None, extattrs=None):
        if InfobloxObject._determine_ip_version(start_addr) == 6:
            return super(InfobloxIPRange, cls).__new__(
                InfobloxIPRangeV6, netview_name, start_addr, end_addr,
                cidr, disable, extattrs)
        else:
            return super(InfobloxIPRange, cls).__new__(
                InfobloxIPRangeV4, netview_name, start_addr, end_addr,
                cidr, disable, extattrs)

    def __init__(self, obj_type, ip_ver, netview_name, start_addr, end_addr,
                 cidr=None, disable=None, extattrs=None):
        super(InfobloxIPRange, self).__init__(obj_type, ip_ver)

        self.payload.update({'start_addr': start_addr,
                             'end_addr': end_addr,
                             'network_view': netview_name})
        if cidr:
            self.payload.update({'network': cidr})

        if extattrs:
            self.create_data.update({'extattrs': extattrs})
        if disable:
            self.create_data.update({'disable': disable})


class InfobloxIPRangeV4(InfobloxIPRange):
    def __init__(self, netview_name, start_addr, end_addr,
                 cidr=None, disable=None, extattrs=None):
        super(InfobloxIPRangeV4, self).__init__(
            'range', 4, netview_name, start_addr, end_addr,
            cidr, disable, extattrs)


class InfobloxIPRangeV6(InfobloxIPRange):
    def __init__(self, netview_name, start_addr, end_addr,
                 cidr=None, disable=None, extattrs=None):
        super(InfobloxIPRangeV6, self).__init__(
            'ipv6range', 6, netview_name, start_addr, end_addr,
            cidr, disable, extattrs)


class InfobloxObjectManager(object):

    def __init__(self, condition):
        self.ib_condition = condition
        self.cloud_api_enabled = ib_utils.is_cloud_wapi(
            condition.grid_connection.wapi_version)
        self.connector = connector.HttpClient(condition) \
            if condition.ready else None

    def create_network_view(self, network_view, extattrs,
                            delegate_member=None):
        nv_obj = InfobloxNetworkView(network_view, extattrs)

        # no need to add delegate parameter
        # self._add_delegate_member(payload, delegate_member)

        return self._create_infoblox_object(nv_obj)

    def delete_network_view(self, network_view):
        # never delete default network view
        if network_view == 'default':
            return
        nv_obj = InfobloxNetworkView(network_view)
        self._delete_infoblox_object(nv_obj)

    def create_dns_view(self, network_view, dns_view):
        dv_obj = InfobloxDNSView(dns_view, network_view)
        return self._create_infoblox_object(dv_obj)

    def delete_dns_view(self, dns_view):
        dv_obj = InfobloxDNSView(dns_view)
        self._delete_infoblox_object(dv_obj)

    def create_network(self, net_view_name, cidr, nameservers=None,
                       members=None, gateway_ip=None, dhcp_trel_ip=None,
                       network_extattrs=None):

        network_obj = InfobloxNetwork(net_view_name, cidr, nameservers,
                                      members, gateway_ip, dhcp_trel_ip,
                                      network_extattrs)
        return self._create_infoblox_object(network_obj,
                                            check_if_exists=False)

    def get_network(self, network_view, cidr):
        network_obj = InfobloxNetwork(network_view, cidr)
        net = self.obj_man._get_infoblox_object_or_none(network_obj)
        if not net:
            raise ib_ex.InfobloxNetworkNotAvailable(
                net_view_name=network_view, cidr=cidr)
        return objects.Network.from_dict(net)

    def create_ip_range(self, network_view, start_ip, end_ip, network,
                        disable, range_extattrs):
        range_obj = InfobloxIPRange(network_view, start_ip, end_ip, network,
                                    extattrs=range_extattrs)
        range_obj.create_data = {'disable': disable}

        self._create_infoblox_object(range_obj)

    def delete_ip_range(self, network_view, start_ip, end_ip):
        range_obj = InfobloxIPRange(network_view, start_ip, end_ip)

        self._delete_infoblox_object(range_obj)

    def has_networks(self, network_view_name):
        payload = {'network_view': network_view_name}
        try:
            ib_network = self._get_infoblox_object_or_none('network', payload)
            return bool(ib_network)
        except ib_ex.InfobloxSearchError:
            return False

    def network_exists(self, network_view, cidr):
        ip_backend = IPBackendFactory.get(self, cidr)
        return ip_backend.network_exists(network_view, cidr)

    def create_network(self, network_view, cidr, nameservers=None,
                       dhcp_members=None, gateway_ip=None, relay_trel_ip=None,
                       extattrs=None):
        """Create subnet in infoblox backend

        :param network_view: infoblox network view name
        :param cidr: subnet cidr string
        :param nameservers: list of ip addresses for dns name servers
        :param dhcp_members: list of InfobloxGridMember objects
        :param gateway_ip: subnet gateway ip
        :param relay_trel_ip: network relay trel interface if dhcp/dns is used
        :param extattrs: network view ea
        :return: infoblox network object that is equivalent of neutron subnet
        """
        obj_type = self.ib_network_name
        payload = {'network_view': network_view,
                   'network': cidr,
                   'extattrs': extattrs}

        # WAPI takes anyone of 'name', 'ipv4addr', or 'ipv6addr'
        # we will use 'name' since 'ipv6addr' is not supported in
        # pre-hellfire nios
        members_struct = []
        for member in dhcp_members:
            members_struct.append({'name': member.member_name,
                                   '_struct': 'dhcpmember'})
        payload['members'] = members_struct

        dhcp_options = []
        if nameservers:
            dhcp_options.append({'name': 'domain-name-servers',
                                 'value': ",".join(nameservers)})
        if dhcp_options:
            payload['options'] = dhcp_options

        return self.ibom._create_infoblox_object(obj_type, payload,
                                                 check_if_exists=False)

    def create_network(self, network_view, cidr, nameservers=None,
                       dhcp_members=None, gateway_ip=None, relay_trel_ip=None,
                       extattrs=None):
        ip_backend = IPBackendFactory.get(self, cidr)
        ip_backend.create_network(network_view, cidr, nameservers,
                                  dhcp_members, gateway_ip, relay_trel_ip,
                                  extattrs)

    def delete_network(self, network_view, cidr):
        ip_backend = IPBackendFactory.get(self, cidr)
        ip_backend.delete_network(network_view, cidr)

    def create_network_from_template(self, network_view, cidr, template,
                                     extattrs):
        payload = {'network_view': network_view,
                   'network': cidr,
                   'template': template,
                   'extattrs': extattrs}
        return self._create_infoblox_object('network', payload,
                                            check_if_exists=False)

    def update_network_options(self, ib_network, extattrs=None):
        payload = {}
        if ib_network.options:
            payload['options'] = ib_network.options
        if extattrs:
            payload['extattrs'] = extattrs
        self._update_infoblox_object_by_ref(ib_network.ref, payload)

    def get_host_record(self, dns_view, ip):
        ip_backend = IPBackendFactory.get(self, ip)
        return ip_backend.get_host_record(dns_view, ip)

    def find_hostname(self, dns_view, hostname, ip):
        ip_backend = IPBackendFactory.get(self, ip)
        return ip_backend.find_hostname(dns_view, hostname)

    def create_host_record_for_given_ip(self, dns_view, zone_auth,
                                        hostname, mac, ip, extattrs,
                                        use_dhcp):
        ip_backend = IPBackendFactory.get(self, ip)

        hr = ip_backend.create_host_record(use_dhcp)
        hr.ip_version = ip_backend.ip_version
        hr.hostname = hostname
        hr.zone_auth = zone_auth
        hr.mac = mac
        hr.dns_view = dns_view
        hr.ip = ip
        hr.extattrs = extattrs

        new_hr = self._create_infoblox_ip_address(hr)
        return new_hr

    def create_host_record_from_range(self, dns_view, network_view_name,
                                      zone_auth, hostname, mac, first_ip,
                                      last_ip, extattrs, use_dhcp):
        ip_backend = IPBackendFactory.get(self, first_ip)

        hr = ip_backend.create_host_record(use_dhcp)
        hr.ip_version = ip_backend.ip_version
        hr.hostname = hostname
        hr.zone_auth = zone_auth
        hr.mac = mac
        hr.dns_view = dns_view
        hr.ip = ibo.IPAllocationObject.next_available_ip_from_range(
            network_view_name, first_ip, last_ip)
        hr.extattrs = extattrs

        new_hr = self._create_infoblox_ip_address(hr)
        return new_hr

    def delete_host_record(self, dns_view, ip_address):
        ip_backend = IPBackendFactory.get(self, ip_address)
        ip_backend.delete_host_record(dns_view, ip_address)

    def create_fixed_address_for_given_ip(self, network_view, mac, ip,
                                          extattrs):
        ip_backend = IPBackendFactory.get(self, ip)

        fa = ip_backend.get_fixed_address()
        fa.ip = ip
        fa.net_view = network_view
        fa.mac = mac
        fa.extattrs = extattrs

        new_fa = self._create_infoblox_ip_address(fa)
        return new_fa

    def create_fixed_address_from_range(self, network_view, mac, first_ip,
                                        last_ip, extattrs):
        ip_backend = IPBackendFactory.get(self, first_ip)

        fa = ip_backend.get_fixed_address()
        fa.ip = ibo.IPAllocationObject.next_available_ip_from_range(
            network_view, first_ip, last_ip)
        fa.net_view = network_view
        fa.mac = mac
        fa.extattrs = extattrs

        new_fa = self._create_infoblox_ip_address(fa)
        return new_fa

    def create_fixed_address_from_cidr(self, netview, mac, cidr, extattrs):
        ip_backend = IPBackendFactory.get(self, cidr)

        fa = ip_backend.get_fixed_address()
        fa.ip = ibo.IPAllocationObject.next_available_ip_from_cidr(netview,
                                                                   cidr)
        fa.mac = mac
        fa.net_view = netview
        fa.extattrs = extattrs

        new_fa = self._create_infoblox_ip_address(fa)
        return new_fa

    def delete_fixed_address(self, network_view, ip_address):
        ip_backend = IPBackendFactory.get(self, ip_address)
        ip_backend.delete_fixed_address(network_view, ip_address)

    def add_ip_to_record(self, host_record, ip, mac, use_dhcp=True):
        ip_backend = IPBackendFactory.get(self, ip)
        return ip_backend.add_ip_to_record(host_record, ip, mac, use_dhcp)

    def add_ip_to_host_record_from_range(self, host_record, network_view,
                                         mac, first_ip, last_ip,
                                         use_dhcp=True):
        ip = ibo.IPAllocationObject.next_available_ip_from_range(
            network_view, first_ip, last_ip)
        hr = self.add_ip_to_record(host_record, ip, mac, use_dhcp)
        return hr

    def delete_ip_from_host_record(self, host_record, ip):
        ip_backend = IPBackendFactory.get(self, ip)
        ip_backend.delete_ip_from_host_record(host_record, ip)

    def has_dns_zones(self, dns_view):
        zone_data = {'view': dns_view}
        try:
            zone = self._get_infoblox_object_or_none('zone_auth', zone_data)
            return bool(zone)
        except ib_ex.InfobloxSearchError:
            return False

    def create_dns_zone(self, dns_view, dns_zone,
                        primary_dns_members=None, secondary_dns_members=None,
                        zone_format=None, ns_group=None, prefix=None,
                        extattrs=None):
        dns_zone_data = {'fqdn': dns_zone,
                         'view': dns_view,
                         'extattrs': extattrs if extattrs else {}}
        zone_args = {}

        primary_members_structs = []
        for member in primary_dns_members:
            primary_members_structs.append({'name': member.member_name,
                                            '_struct': 'memberserver'})
        zone_args['grid_primary'] = primary_members_structs

        if secondary_dns_members:
            grid_secondaries = [{'name': member.member_name,
                                 '_struct': 'memberserver'}
                                for member in secondary_dns_members]
            zone_args['grid_secondaries'] = grid_secondaries

        if zone_format:
            zone_args['zone_format'] = zone_format

        if ns_group:
            zone_args['ns_group'] = ns_group

        if prefix:
            zone_args['prefix'] = prefix

        try:
            self._create_infoblox_object('zone_auth',
                                         dns_zone_data,
                                         additional_create_kwargs=zone_args,
                                         check_if_exists=True)
        except ib_ex.InfobloxCannotCreateObject:
            LOG.warning(_LW('Unable to create DNS zone %(dns_zone_fqdn)s '
                            'for %(dns_view)s'), {'dns_zone_fqdn': dns_zone,
                                                  'dns_view': dns_view})

    def delete_dns_zone(self, dns_view, dns_zone_fqdn):
        dns_zone_data = {'fqdn': dns_zone_fqdn,
                         'view': dns_view}
        self._delete_infoblox_object('zone_auth', dns_zone_data)

    def update_host_record_eas(self, dns_view, ip, extattrs):
        ip_backend = IPBackendFactory.get(self, ip)
        ip_backend.update_host_record_eas(dns_view, ip, extattrs)

    def update_fixed_address_eas(self, network_view, ip, extattrs):
        ip_backend = IPBackendFactory.get(self, ip)
        ip_backend.update_fixed_address_eas(network_view, ip, extattrs)

    def update_dns_record_eas(self, dns_view, ip, extattrs):
        ip_backend = IPBackendFactory.get(self, ip)
        ip_backend.update_dns_record_eas(dns_view, ip, extattrs)

    def bind_name_with_host_record(self, dns_view, ip, name, extattrs):
        ip_backend = IPBackendFactory.get(self, ip)
        ip_backend.bind_name_with_host_record(dns_view, ip, name, extattrs)

    def bind_name_with_record_a(self, dns_view, ip, name, bind_list,
                                extattrs):
        ip_backend = IPBackendFactory.get(self, ip)
        ip_backend.bind_name_with_record_a(dns_view, ip, name, bind_list,
                                           extattrs)

    def unbind_name_from_record_a(self, dns_view, ip, name, unbind_list):
        ip_backend = IPBackendFactory.get(self, ip)
        ip_backend.unbind_name_from_record_a(dns_view, ip, name, unbind_list)

    def get_member(self, member):
        return self.connector.get_object('member',
                                         {'host_name': member.member_name})

    def restart_all_services(self, member):
        ib_member = self.get_member(member)[0]
        self.connector.call_func('restartservices', ib_member['_ref'],
                                 {'restart_option': 'RESTART_IF_NEEDED',
                                  'service_option': 'ALL'})

    def get_object_refs_associated_with_a_record(self, a_record_ref):
        # record should in the format: {object_type, search_field}
        associated_with_a_record = [
            {'type': 'record:cname', 'search': 'canonical'},
            {'type': 'record:txt', 'search': 'name'}
        ]

        ib_obj_refs = []
        a_record = self.connector.get_object(a_record_ref)

        for rec_inf in associated_with_a_record:
            obj_type = rec_inf['type']
            payload = {'view': a_record['view'],
                       rec_inf['search']: a_record['name']}
            ib_objs = self.connector.get_object(obj_type, payload)
            if ib_objs:
                for ib_obj in ib_objs:
                    ib_obj_refs.append(ib_obj['_ref'])
        return ib_obj_refs

    def get_all_associated_objects(self, network_view, ip):
        ip_backend = IPBackendFactory.get(self, ip)
        return ip_backend.get_all_associated_objects(network_view, ip)

    def delete_all_associated_objects(self, network_view, ip, delete_list):
        del_ib_objs = []
        ib_obj_refs = self.get_all_associated_objects(network_view, ip)

        for ib_obj_ref in ib_obj_refs:
            del_ib_objs.append(ib_obj_ref)
            obj_type = self._get_object_type_from_ref(ib_obj_ref)
            if obj_type in ['record:a', 'record:aaaa']:
                del_ib_objs.extend(
                    self.get_object_refs_associated_with_a_record(ib_obj_ref))

        for ib_obj_ref in del_ib_objs:
            obj_type = self._get_object_type_from_ref(ib_obj_ref)
            if obj_type in delete_list:
                self.connector.delete_object(ib_obj_ref)

    def delete_object_by_ref(self, ref):
        try:
            self.connector.delete_object(ref)
        except ib_ex.InfobloxCannotDeleteObject as e:
            LOG.info(_LI("Failed to delete an object: %s"), e)

    def _create_infoblox_ip_address(self, ip_object):
        obj_type = ip_object.infoblox_type
        payload = ip_object.to_dict()
        try:
            created_ip_json = self._create_infoblox_object(
                obj_type,
                payload,
                check_if_exists=False,
                return_fields=ip_object.return_fields)

            return ip_object.from_dict(created_ip_json)
        except ib_ex.InfobloxCannotCreateObject as e:
            if "Cannot find 1 available IP" in e.response['text']:
                raise ib_ex.InfobloxCannotAllocateIp(ip_data=payload)
            else:
                raise e
        except ib_ex.HostRecordNotPresent:
            raise ib_ex.InfobloxHostRecordIpAddrNotCreated(ip=ip_object.ip,
                                                           mac=ip_object.mac)
        except ib_ex.InfobloxInvalidIp:
            raise ib_ex.InfobloxDidNotReturnCreatedIPBack()

    def _create_infoblox_object(self, create_obj,
                                check_if_exists=True,
                                update_if_exists=False,
                                delegate_member=None):
        obj_type = create_obj.object_type
        payload = create_obj.payload
        additional_create_kwargs = create_obj.create_data
        return_fields = create_obj.return_fields

        ib_obj = None
        if check_if_exists or update_if_exists:
            ib_obj = self._get_infoblox_object_or_none(create_obj)
            if ib_obj:
                LOG.info(_LI("Infoblox %(obj_type)s already exists: "
                             "%(ib_obj)s"),
                         {'obj_type': obj_type, 'ib_obj': ib_obj})

        if not ib_obj:
            payload.update(additional_create_kwargs)
            ib_obj = self.connector.create_object(obj_type,
                                                  payload,
                                                  return_fields)
            LOG.info(_LI("Infoblox %(obj_type)s was created: %(ib_obj)s"),
                     {'obj_type': obj_type, 'ib_obj': ib_obj})
        elif update_if_exists:
            self._update_infoblox_object_by_ref(ib_obj,
                                                additional_create_kwargs)

        return ib_obj

    def _get_infoblox_object_or_none(self, get_obj, proxy=False):
        # search_payload = {}
        obj_type = get_obj.object_type
        payload = get_obj.payload
        return_fields = get_obj.return_fields

        # The following should not be needed if we make sure that EA that
        # is only used for creating object is only added to create_data
        # attribute
        # for key in payload:
        #    if key is not 'extattrs':
        #        search_payload[key] = payload[key]
        ib_obj = self.connector.get_object(obj_type, payload,
                                           return_fields, proxy=proxy)
        if ib_obj:
            if return_fields:
                return ib_obj[0]
            else:
                return ib_obj[0]['_ref']
        return None

    def _update_infoblox_object(self, obj_type, payload, update_kwargs):
        ib_obj_ref = None
        warn_msg = _LW('Infoblox %(obj_type)s will not be updated because'
                       ' it cannot be found: %(payload)s')
        try:
            ib_obj_ref = self._get_infoblox_object_or_none(obj_type, payload)
            if not ib_obj_ref:
                LOG.warning(warn_msg, {'obj_type': obj_type,
                                       'payload': payload})
        except ib_ex.InfobloxSearchError as e:
            LOG.warning(warn_msg, obj_type, payload)
            LOG.info(e)

        if ib_obj_ref:
            self._update_infoblox_object_by_ref(ib_obj_ref, update_kwargs)

    def _update_infoblox_object_by_ref(self, ref, update_kwargs,
                                       return_fields=None):
        updated_object = self.connector.update_object(ref, update_kwargs,
                                                      return_fields)
        LOG.info(_LI('Infoblox object was updated: %s'), ref)
        return updated_object

    def _delete_infoblox_object(self, del_obj):
        obj_type = del_obj.object_type
        payload = del_obj.payload
        ib_obj_ref = None
        warn_msg = _LW('Infoblox %(obj_type)s will not be deleted because'
                       ' it cannot be found: %(payload)s')
        try:
            ib_obj_ref = self._get_infoblox_object_or_none(del_obj)
            if not ib_obj_ref:
                LOG.warning(warn_msg, {'obj_type': obj_type,
                                       'payload': payload})
        except ib_ex.InfobloxSearchError as e:
            LOG.warning(warn_msg, {'obj_type': obj_type, 'payload': payload})
            LOG.info(e)

        if ib_obj_ref:
            self.connector.delete_object(ib_obj_ref)
            LOG.info(_LI('Infoblox object was deleted: %s'), ib_obj_ref)

    def _update_host_record_ips(self, ipaddrs_name, host_record):
        ipaddrs = {ipaddrs_name: [ip.to_dict(add_host=False)
                                  for ip in host_record.ips]}
        return self._update_infoblox_object_by_ref(
            host_record.ref, ipaddrs, return_fields=[ipaddrs_name])

    def _add_delegate_member(self, payload, delegate_member):
        # adding delegate member parameter is not needed since it is done
        # automatically if the delegate member is a CP member. in fact this
        # will cause an issue if the delegate member happens to be not a CP
        # member. if delegation is for other CP member then this is required
        # but IOA does not have this case since a member reservation is picked
        # up by IOA and sends request directly to that member.
        # if the member is not CP member, the request must to be sent to a CP
        # member or GM. CP knows that dhcp member contains a normal member
        # then the network view is owned by GM so it proxies he request to GM.
        # but in our case, IOA shall send the request to GM to avoid an
        # unnecessary proxy. A normal member can serve only protocol.
        if self.cloud_api_enabled and delegate_member:
            delegate_member = {'cloud_info': {
                'delegated_member': {
                    '_struct': 'dhcpmember',
                    'name': delegate_member.member_name
                }
            }}
            payload.update(delegate_member)

    @staticmethod
    def _get_object_type_from_ref(ref):
        return ref.split('/', 1)[0]
