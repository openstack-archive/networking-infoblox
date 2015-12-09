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

from collections import deque
import time


class MiniCache(object):
    """Caching class that keeps track of record age.

    Maintain age of added values and cleanup outdated records.
    """

    def __init__(self, timeout=300):
        self._timeout = timeout
        self._cache = {}
        # collections.deque has O(1) time for append and append left,
        # as well as for pop and pop left
        self._insert_log = deque()

    def set(self, key, value):
        """Store key value mapping.

        If value is not in cache then add log_record for keepeing track
        of record age.
        Complexity O(1).
        """
        if key not in self._cache:
            log_record = (time.time(), key)
            self._insert_log.append(log_record)
        # Update cached value independently from updating record age
        self._cache[key] = value

    def remove_outdated_values(self):
        """Checks _insert_log and removes values older then timeout.

        Removing single outdated element is O(1), so total complexity
        is O(k), where k - count of outdated elements.
        Average case: O(1).
        Worst case: O(n).
        """
        curr_time = time.time()
        while True:
            # Test the log record timestamp starting from oldest one
            # and remove all outdated records
            # Tested records that are not expired are added back.
            try:
                log_record = self._insert_log.popleft()
                if log_record[0] < curr_time - self.timeout:
                    del self._cache[log_record[1]]
                else:
                    self._insert_log.appendleft(log_record)
                    break
            except IndexError:
                break

    def get(self, key):
        """Get stored value for key.

        Complexity O(k) + O(1) = O(k), refer to remove_outdated_values
        for details.
        """
        self.remove_outdated_values()
        if key in self._cache:
            return self._cache[key]
