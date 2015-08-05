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

import abc
import six

from oslo_log import log as logging

from neutron.common import constants as n_const
from neutron.ipam.drivers.infoblox.common import config as ib_conf


LOG = logging.getLogger(__name__)


@six.add_metaclass(abc.ABCMeta)
class IPAllocator(object):
    def __init__(self, ib_obj_manager):
        self.ibom = ib_obj_manager

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
        # See OPENSTACK-181. In case hostname already exists on NIOS, update
        # host record which contains that hostname with the new IP address
        # rather than creating a separate host record object
        reserved_hostname_hr = self.ibom.find_hostname(dns_view, name, ip)
        reserved_ip_hr = self.ibom.get_host_record(dns_view, ip)

        if reserved_hostname_hr == reserved_ip_hr:
            return

        if reserved_hostname_hr:
            for hr_ip in reserved_ip_hr.ips:
                if hr_ip == ip:
                    self.ibom.delete_host_record(dns_view, ip)
                    self.ibom.add_ip_to_record(
                        reserved_hostname_hr, ip, hr_ip.mac)
                    break
        else:
            self.ibom.bind_name_with_host_record(
                dns_view, ip, name, extattrs)

    def unbind_names(self, network_view, dns_view, ip, name, extattrs):
        # Nothing to delete, all will be deleted together with host record.
        pass

    def allocate_ip_from_range(self, network_view, dns_view,
                               zone_auth, hostname, mac, first_ip, last_ip,
                               extattrs=None, use_dhcp=True):
        fqdn = hostname + '.' + zone_auth
        host_record = self.ibom.find_hostname(
            dns_view, fqdn, first_ip)
        if host_record:
            hr = self.ibom.add_ip_to_host_record_from_range(
                host_record, network_view, mac, first_ip, last_ip, use_dhcp)
        else:
            hr = self.ibom.create_host_record_from_range(
                dns_view, network_view, zone_auth, hostname, mac,
                first_ip, last_ip, extattrs, use_dhcp)
        return hr.ips[-1].ip

    def allocate_given_ip(self, network_view, dns_view, zone_auth,
                          hostname, mac, ip, extattrs=None, use_dhcp=True):
        hr = self.ibom.create_host_record_for_given_ip(
            dns_view, zone_auth, hostname, mac, ip, extattrs, use_dhcp)
        return hr.ips[-1].ip

    def deallocate_ip(self, network_view, dns_view_name, ip):
        host_record = self.ibom.get_host_record(dns_view_name, ip)
        if host_record and len(host_record.ips) > 1:
            self.ibom.delete_ip_from_host_record(host_record, ip)
        else:
            self.ibom.delete_host_record(dns_view_name, ip)


class FixedAddressIPAllocator(IPAllocator):

    def bind_names(self, network_view, dns_view, ip, name, extattrs):
        bind_cfg = ib_conf.CONF_IPAM.bind_dns_records_to_fixed_address
        if extattrs.get('Port Attached Device - Device Owner').\
                get('value') == n_const.DEVICE_OWNER_FLOATINGIP:
            self.ibom.update_fixed_address_eas(
                network_view, ip, extattrs)
            self.ibom.update_dns_record_eas(
                dns_view, ip, extattrs)
        if bind_cfg:
            self.ibom.bind_name_with_record_a(
                dns_view, ip, name, bind_cfg, extattrs)

    def unbind_names(self, network_view, dns_view, ip, name, extattrs):
        unbind_cfg = ib_conf.CONF_IPAM.unbind_dns_records_from_fixed_address
        if unbind_cfg:
            self.ibom.unbind_name_from_record_a(
                dns_view, ip, name, unbind_cfg)

    def allocate_ip_from_range(self, network_view, dns_view,
                               zone_auth, hostname, mac, first_ip, last_ip,
                               extattrs=None):
        fa = self.ibom.create_fixed_address_from_range(
            network_view, mac, first_ip, last_ip, extattrs)
        return fa.ip

    def allocate_given_ip(self, network_view, dns_view, zone_auth,
                          hostname, mac, ip, extattrs=None):
        fa = self.ibom.create_fixed_address_for_given_ip(
            network_view, mac, ip, extattrs)
        return fa.ip

    def deallocate_ip(self, network_view, dns_view_name, ip):
        delete_cfg = \
            ib_conf.CONF_IPAM.delete_dns_records_associated_with_fixed_address
        if delete_cfg:
            self.ibom.delete_all_associated_objects(network_view, ip,
                                                    delete_cfg)
        self.ibom.delete_fixed_address(network_view, ip)


class IPAllocatorFactory(object):

    host_record = None
    fixed_address = None

    def __init__(self, ib_obj_manager):
        self.host_record = HostRecordIPAllocator(ib_obj_manager)
        self.fixed_address = FixedAddressIPAllocator(ib_obj_manager)

    @property
    def default(self):
        if ib_conf.CONF_IPAM.use_host_records_for_ip_allocation:
            return self.host_record
        else:
            return self.fixed_address
