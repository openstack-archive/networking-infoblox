Release Notes
-------------

10.0.0 (2017-08-09)
__________________

Enhancements
~~~~~~~~~~~~
* Authentication
    - Support for keystone v3 configuration
      1) Support for Domain scope authentication
      2) Support for Project scope authentication
    - Support for keystone SSL configuation

Fixes
~~~~~
* Fix issue of infoblox client raising exception when dns_support=False.
* Handled exception in ip allocation for IPV6.
* Update infoblox-client requirement
* Fixed issue related to A record creation failure with tenant_info in DNS pattern
* Added validation for incorrect Domain Patterns
* Fixed issue related to syncing of port information in NIOS using sync tool.
* Fixed issue of Zones not adding in specified DNS View
* Fix issue in the rollback mechanism causes DNS zone delete in NIOS
* Fix for sync tool failure after deleting a network from NIOS.
* Enabled domain-level authorization scope
* Fix for DuplicateKey error when inserting to infoblox_tenants table.
* Fix tox.ini to use upper-contraints.txt for dependency packages
* Switch topic to topics and Fixed import UT's failure
* Describe new versioning scheme in README
* Specify branch name in tox_install.sh
