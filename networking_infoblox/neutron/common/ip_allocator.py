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

import abc
import netaddr
import six

from networking_infoblox.neutron.common import constants as const


@six.add_metaclass(abc.ABCMeta)
class IPAllocator(object):
    """Base class for ip allocation actions"""

    DEFAULT_OPTIONS = {
        'use_host_record': True,
        'configure_for_dhcp': True,
        'configure_for_dns': True,
        'dns_record_binding_types': [],
        'dns_record_unbinding_types': [],
        'dns_record_removable_types': []}

    def __new__(cls, ib_obj_manager, options):
        cls._validate_and_set_default_options(options)
        return super(IPAllocator, cls).__new__(
            cls._get_ip_allocator_class(options))

    def __init__(self, ib_obj_manager, options):
        self.manager = ib_obj_manager
        self.opts = options

    @classmethod
    def _validate_and_set_default_options(cls, options):
        if not isinstance(options, dict):
            raise ValueError('Options should be passed as dict')
        for key in cls.DEFAULT_OPTIONS:
            if key not in options:
                options[key] = cls.DEFAULT_OPTIONS[key]

    @staticmethod
    def _get_ip_allocator_class(options):
        if options['use_host_record']:
            return HostRecordIPAllocator
        else:
            return FixedAddressIPAllocator

    @abc.abstractmethod
    def allocate_ip_from_range(self, network_view, dns_view, zone_auth,
                               hostname, mac, first_ip, last_ip,
                               extattrs=None):
        pass

    @abc.abstractmethod
    def allocate_given_ip(self, network_view, dns_view, zone_auth,
                          hostname, mac, ip, extattrs=None):
        pass

    @abc.abstractmethod
    def deallocate_ip(self, network_view, dns_view_name, ip):
        pass

    @abc.abstractmethod
    def bind_names(self, network_view, dns_view, ip, name, extattrs):
        pass

    @abc.abstractmethod
    def unbind_names(self, network_view, dns_view, ip, name, extattrs):
        pass


class HostRecordIPAllocator(IPAllocator):

    def bind_names(self, network_view, dns_view, ip, name, extattrs):
        # Don't use network view for DNS hosts
        net_view = None
        if not self.opts['configure_for_dns']:
            if network_view == 'default':
                # Non-dns records placed in special dns view
                # '.non_DNS_host_root' which has special name ' '
                dns_view = ' '
            else:
                # Each network_view has separate non_DNS_host_root dns view
                # Unfortunatelly all non_DNS_host_root except the 'default'
                # network view has same display name - '  ' which brakes WAPI
                # code. So network view should be used instead of dns view for
                # non-DNS hosts which is belongs to non-default network views
                dns_view = None
                net_view = network_view
        # See OPENSTACK-181. In case hostname already exists on NIOS, update
        # host record which contains that hostname with the new IP address
        # rather than creating a separate host record object
        reserved_hostname_hr = self.manager.find_hostname(
            dns_view, name, ip, net_view)
        reserved_ip_hr = self.manager.get_host_record(
            dns_view, ip, net_view)

        if (reserved_hostname_hr and reserved_ip_hr and
                reserved_hostname_hr.ref == reserved_ip_hr.ref):
            reserved_hostname_hr.extattrs = extattrs
            reserved_hostname_hr.update()
            return

        if reserved_hostname_hr:
            for hr_ip in reserved_ip_hr.ips:
                if hr_ip == ip:
                    reserved_ip_hr.delete()
                    reserved_hostname_hr.extattrs = extattrs
                    self.manager.add_ip_to_record(
                        reserved_hostname_hr, ip, hr_ip.mac)
                    break
        else:
            self.manager.bind_name_with_host_record(
                dns_view, ip, name, extattrs, net_view)

    def unbind_names(self, network_view, dns_view, ip, name, extattrs):
        # Nothing to delete, all will be deleted together with host record.
        pass

    def allocate_ip_from_range(self, network_view, dns_view,
                               zone_auth, hostname, mac, first_ip, last_ip,
                               extattrs=None):
        use_dhcp = self.opts['configure_for_dhcp']
        use_dns = self.opts['configure_for_dns']
        fqdn = hostname + '.' + zone_auth
        host_record = self.manager.find_hostname(
            dns_view, fqdn, first_ip)

        if host_record:
            hr = self.manager.add_ip_to_host_record_from_range(
                host_record, network_view, mac, first_ip, last_ip, use_dhcp)
        else:
            # First search hosts with same MAC and if exists address within
            # given range - use it instead of creating new one
            # https://bugs.launchpad.net/networking-infoblox/+bug/1628517
            hosts = self.manager.find_host_records_by_mac(dns_view,
                                                          mac.lower(),
                                                          network_view)
            if hosts:
                ip_range = netaddr.IPRange(first_ip, last_ip)
                ip_version = netaddr.IPAddress(first_ip).version
                for host in hosts:
                    if host.ip_version != ip_version:
                        continue
                    for ip in host.ips:
                        ip_mac = ip.mac if ip_version == 4 else ip.duid
                        if ip_mac != mac:
                            continue
                        ip_addr = netaddr.IPAddress(ip.ip)
                        if ip_addr in ip_range:
                            self.manager.update_host_record_eas(dns_view,
                                                                ip.ip,
                                                                extattrs)
                            return ip.ip
            hr = self.manager.create_host_record_from_range(
                dns_view, network_view, zone_auth, hostname, mac,
                first_ip, last_ip, extattrs, use_dhcp, use_dns)
        return hr.ip[-1].ip

    def allocate_given_ip(self, network_view, dns_view, zone_auth,
                          hostname, mac, ip, extattrs=None):
        use_dhcp = self.opts['configure_for_dhcp']
        use_dns = self.opts['configure_for_dns']
        # First search hosts with same MAC and if exists address with
        # same IP - use it instead of creating new one
        # https://bugs.launchpad.net/networking-infoblox/+bug/1628517
        hosts = self.manager.find_host_records_by_mac(dns_view,
                                                      mac.lower(),
                                                      network_view)
        if hosts:
            ip_version = netaddr.IPAddress(ip).version
            for host in hosts:
                if host.ip_version != ip_version:
                    continue
                for host_ip in host.ips:
                    ip_mac = host_ip.mac if ip_version == 4 else ip.duid
                    if ip_mac != mac:
                        continue
                    if host_ip.ip == ip:
                        self.manager.update_host_record_eas(dns_view,
                                                            host_ip.ip,
                                                            extattrs)
                        return host_ip.ip
        hr = self.manager.create_host_record_for_given_ip(
            dns_view, zone_auth, hostname, mac, ip, extattrs, use_dhcp,
            use_dns)
        return hr.ip[-1].ip

    def deallocate_ip(self, network_view, dns_view_name, ip):
        host_record = self.manager.get_host_record(dns_view_name, ip)
        if host_record:
            if len(host_record.ip) > 1:
                self.manager.delete_ip_from_host_record(host_record, ip)
            else:
                host_record.delete()


class FixedAddressIPAllocator(IPAllocator):

    def bind_names(self, network_view, dns_view, ip, name, extattrs):
        bind_cfg = self.opts['dns_record_binding_types']
        device_owner = extattrs.get(const.EA_PORT_DEVICE_OWNER)
        if device_owner in const.NEUTRON_FLOATING_IP_DEVICE_OWNERS:
            self.manager.update_fixed_address_eas(network_view, ip, extattrs)
            if self.opts['configure_for_dns']:
                self.manager.update_dns_record_eas(dns_view, ip, extattrs)
        if bind_cfg and self.opts['configure_for_dns']:
            self.manager.bind_name_with_record_a(
                dns_view, ip, name, bind_cfg, extattrs)

    def unbind_names(self, network_view, dns_view, ip, name, extattrs):
        unbind_cfg = self.opts['dns_record_unbinding_types']
        if unbind_cfg and self.opts['configure_for_dns']:
            self.manager.unbind_name_from_record_a(
                dns_view, ip, name, unbind_cfg)

    def allocate_ip_from_range(self, network_view, dns_view,
                               zone_auth, hostname, mac, first_ip, last_ip,
                               extattrs=None):
        # First search addresses with same MAC and if exists address within
        # given range - use it instead of creating new one
        # https://bugs.launchpad.net/networking-infoblox/+bug/1628517
        fixed_addrs = self.manager.get_fixed_addresses_by_mac(network_view,
                                                              mac.lower())
        if fixed_addrs:
            ip_range = netaddr.IPRange(first_ip, last_ip)
            for fixed_addr in fixed_addrs:
                ip_addr = netaddr.IPAddress(fixed_addr.ip)
                if ip_addr in ip_range:
                    self.manager.update_fixed_address_eas(network_view,
                                                          fixed_addr.ip,
                                                          extattrs)
                    return fixed_addr.ip
        fa = self.manager.create_fixed_address_from_range(
            network_view, mac, first_ip, last_ip, extattrs)
        return fa.ip

    def allocate_given_ip(self, network_view, dns_view, zone_auth,
                          hostname, mac, ip, extattrs=None):
        # First search addresses with same MAC and if exists address with
        # same IP - use it instead of creating new one
        # https://bugs.launchpad.net/networking-infoblox/+bug/1628517
        fixed_addrs = self.manager.get_fixed_addresses_by_mac(network_view,
                                                              mac.lower())
        if fixed_addrs:
            for fixed_addr in fixed_addrs:
                if fixed_addr.ip == ip:
                    self.manager.update_fixed_address_eas(network_view, ip,
                                                          extattrs)
                    return fixed_addr.ip
        fa = self.manager.create_fixed_address_for_given_ip(
            network_view, mac, ip, extattrs)
        return fa.ip

    def deallocate_ip(self, network_view, dns_view_name, ip):
        delete_cfg = self.opts['dns_record_removable_types']
        if delete_cfg and self.opts['configure_for_dns']:
            self.manager.unbind_name_from_record_a(dns_view_name, ip,
                                                   None, delete_cfg)
        self.manager.delete_fixed_address(network_view, ip)
