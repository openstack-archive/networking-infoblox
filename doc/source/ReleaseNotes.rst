Release Notes
-------------

10.0.1 (2018-03-05)
__________________

Enhancements
~~~~~~~~~~~~
* Support CP Member
* Support for pagination

Fixes
~~~~~
* Fixed issue of stale entry for dhcp ip if ip allocation strategy is fixed address.
* Fixed issue where IPAllocation fails and log trace not show reason of failure.
* Removed OS_REGION_NAME dependency from sync tools.
* Added filter of CMP Type on GET network
* Fix exception while grid sync when GM is disconnected
* Handled exception while restarting member services when cp member disconnected
* Added support for pagination and optimized mapping.sync() call
* Added force_proxy=True for member_object wapi call to support cp_member.
* Fixed issue where NIOS password was visible in infoblox plugin & agent logs.
* Fixed flags in GRID_CONFIGURATION EA'S for CP Member Support
* Fixed exceptions when uppercase name used for creating resources in openstack
* Fixed exception handling for case of conflict while creation of the ip object.
