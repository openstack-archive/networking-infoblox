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

from neutron.common import constants as n_const
from neutron.plugins.common import constants as p_const


CLOUD_WAPI_MAJOR_VERSION = 2
EA_CLOUD_MGMT_PLATFORM_TYPE = 'CMP Type'

NEXT_AVAILABLE_MEMBER = '<next-available-member>'

# A CP member can own network view, dhcp network, and dns primary
# A regular member can only serve protocols and all containers are
# owned by GM.
MEMBER_TYPE_GRID_MASTER = 'GM'
MEMBER_TYPE_CP_MEMBER = 'CPM'
MEMBER_TYPE_REGULAR_MEMBER = 'REGULAR'

MEMBER_STATUS_ON = 'ON'
MEMBER_STATUS_OFF = 'OFF'

MAPPING_SCOPE_TENANT_ID = 'TENANT_ID'
MAPPING_SCOPE_NETWORK_NAME = 'NETWORK_NAME'
MAPPING_SCOPE_NETWORK_ID = 'NETWORK_ID'
MAPPING_SCOPE_NETWORK_VIEW = 'NETWORK_VIEW'

MAPPING_RELATION_CP = 'CP'
MAPPING_RELATION_GM = 'GM'
MAPPING_RELATION_GM_DISTRIBUTED = 'GM-DISTRIBUTED'

SERVICE_TYPE_DHCP = 'DHCP'
SERVICE_TYPE_DNS = 'DNS'

NETWORK_META_TYPE_PHYSICAL_NETWORK = 'physical network'

NEUTRON_DEVICE_OWNER_TO_PATTERN_MAP = {
    n_const.DEVICE_OWNER_DHCP: 'dhcp-port-{ip_address}',
    n_const.DEVICE_OWNER_ROUTER_INTF: 'router-iface-{ip_address}',
    n_const.DEVICE_OWNER_ROUTER_GW: 'router-gw-{ip_address}',
    n_const.DEVICE_OWNER_FLOATINGIP: 'floating-ip-{ip_address}',
    'neutron:' + p_const.LOADBALANCER: 'lb-vip-{ip_address}'
}

NEUTRON_INTERNAL_SERVICE_DEVICE_OWNERS = [
    n_const.DEVICE_OWNER_DHCP,
    n_const.DEVICE_OWNER_ROUTER_INTF,
    n_const.DEVICE_OWNER_ROUTER_GW,
    'neutron:' + p_const.LOADBALANCER
]
