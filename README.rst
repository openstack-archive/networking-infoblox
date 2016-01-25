===============================
networking-infoblox
===============================

Contains Neutron drivers for integration with Infoblox grids for IPAM and DNS.

* Free software: Apache license
* Documentation: http://docs.openstack.org/developer/networking-infoblox
* Source: http://git.openstack.org/cgit/openstack/networking-infoblox
* Bugs: http://bugs.launchpad.net/networking-infoblox

Features
--------

This release of the driver supports:

* IPv4 and IPv6 Subnet creation, update and deletion
* IPv4 and IPv6 address allocation and deallocation
* Support for fixed and floating IP addresses
* Creation and deletion of Host, A, AAAA, and PTR records during IP allocation
* Creation of authoritative zones
* Support for GM and CP members and Cloud API
* Flexible mapping of OpenStack entities to network view
* Set EAs to populate the Cloud tab in the Infoblox UI

Overview
--------

The IPAM driver consists of two components: the ``networking_infoblox`` Python
module, and the ``infoblox-ipam-agent``. Each of these depend upon the
``infoblox-client`` [#]_ library.

The IPAM driver will be consulted by Neutron whenever subnet or IP allocation
is needed. The driver will use RESTful API calls (aka, "Web-API" or "WAPI") to
perform these operations in Infoblox. Additionally, the driver will tag each
of these entities in Infoblox with various meta-data from OpenStack, such as
the tenant and the corresponding OpenStack IDs for the objects. This tagging
allows the entities to show up in the Cloud tab of the UI (which is available
with the Cloud Network Automation license), giving full visibility into the
OpenStack cloud from within Infoblox.

The agent serves a few functions. First, it will populate the local Neutron
database with data about the Infoblox grid. This enables the selection
of the member and the network view to be made when allocating subnets and IP
addresses, without additional WAPI calls. Second, it listens for events on
the OpenStack message bus, and makes WAPI calls related to objects that are
not directly part of the IPAM function. 

Installation and Configuration
------------------------------

See the documentation link above for details on Installation and Configuration.

Limitations
-----------

When a change is made to the EAs within Infoblox that are used to control the
IPAM driver configuration, those changes are not automatically synchronized
to OpenStack. They will be syncrhonized during subnet or network creation or
when the IPAM agent is restarted.

Currently there is no script to migrate existing OpenStack installation
data into Infoblox, apart from the built-in vDiscovery in Infoblox 7.2.4
or later.

Known issues
------------

1. Subnet deletion when using the ML2 plugin will delete the subnet from Neutron
but leave the subnet in Infoblox due to Neutron bug 1510653 [#]_. This is fixed
in the stable/liberty branch of Neutron.

.. [#] https://pypi.python.org/pypi/infoblox-client
.. [#] https://launchpad.net/bugs/1510653

2. Once the IPAM driver create a Network View on Infoblox, the name of the Network
   View should not be changed. Changing Network View name on Infoblox would result
   in data synchronization issue. This will be addressed in a future release of the
   IPAM driver.

3. If the ``Default Domain Name Pattern`` includes one of the following patterns:
   ``{tenant_name}``, ``{network_name}`` or ``{subnet_name}``, the names of
   of the corresponding objects should not be changed in OpenStack once they are
   created. Changing them would result in data synchronization issue. This will be
   addressed in a future release of the IPAM driver.
