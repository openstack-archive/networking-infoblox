===============================
networking-infoblox
===============================

Contains Neutron drivers for integration with Infoblox grids for IPAM and DNS.

* Free software: Apache license
* Source: http://git.openstack.org/cgit/openstack/networking-infoblox
* Bugs: http://bugs.launchpad.net/networking-infoblox
* Installation: https://github.com/openstack/networking-infoblox/blob/master/doc/source/installation.rst
* Configuration Guide: https://github.com/openstack/networking-infoblox/blob/master/doc/source/configuration_guide.rst

Changes to Versioning Scheme
----------------------------
Starting with this release, Infoblox uses new versioning scheme for the IPAM Driver,
as follows:

* To better align the IPAM Driver version with the Neutron version, the current release
is 7.0.0 (which supports Neutron Release 7, Liberty). Note that release 7.0.0 is the
subsequent release of 2.0.2.
* The major number in the IPAM Driver version matches the Neutron major number.
For example, in release 7.0.0, the major number '7' matches the Neutron major number '7.'.
* The minor number (the second digit in the release version) represents the functionality
level of the IPAM Driver. In other words, releases that have the same minor number will
have the same functionality.
* The patch number (the last digit in the release version) is used for releases that
contain resolved issues or bug fixes for a particular release version.
* Release 8.0.0 of the Infoblox IPAM Driver for OpenStack Neutron supports the Neutron
Mikata version while release 9.0.0 supports the Newton version.

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
