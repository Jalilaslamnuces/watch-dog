# coding: utf-8
#
# Copyright 2011 Yesudeep Mangalapilly <yesudeep@gmail.com>
# Copyright 2012 Google, Inc & contributors.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
:module: watchdog.observers
:synopsis: Observer that picks a native implementation if available.
:author: yesudeep@google.com (Yesudeep Mangalapilly)
:author: contact@tiger-222.fr (Mickaël Schoentgen)

Classes
=======
.. autoclass:: Observer
   :members:
   :show-inheritance:
   :inherited-members:

Observer thread that schedules watching directories and dispatches
calls to event handlers.

You can also import platform specific classes directly and use it instead
of :class:`Observer`.  Here is a list of implemented observer classes.:

============== ================================ ==============================
Class          Platforms                        Note
============== ================================ ==============================
|Inotify|      Linux 2.6.13+                    ``inotify(7)`` based observer
|FSEvents|     macOS                            FSEvents based observer
|Kqueue|       macOS and BSD with kqueue(2)     ``kqueue(2)`` based observer
|WinApi|       MS Windows                       Windows API-based observer
|Polling|      Any                              fallback implementation
============== ================================ ==============================

.. |Inotify|     replace:: :class:`.inotify.InotifyObserver`
.. |FSEvents|    replace:: :class:`.fsevents.FSEventsObserver`
.. |Kqueue|      replace:: :class:`.kqueue.KqueueObserver`
.. |WinApi|      replace:: :class:`.read_directory_changes.WindowsApiObserver`
.. |Polling|     replace:: :class:`.polling.PollingObserver`

"""

import warnings
from watchdog.utils import platform
from watchdog.utils import UnsupportedLibc

def getPollingObserver():
    from .polling import PollingObserver
    return PollingObserver

def getLinuxObserver():
    try:
        from .inotify import InotifyObserver
        return InotifyObserver
    except UnsupportedLibc:
        return getPollingObserver()

def getDarwinObserver():
    try:
        from .fsevents import FSEventsObserver
        return FSEventsObserver
    except Exception:
        try:
            from .kqueue import KqueueObserver
            warnings.warn("Failed to import fsevents. Fall back to kqueue")
            return KqueueObserver
        except Exception:
            warnings.warn("Failed to import fsevents and kqueue. Fall back to polling.")
            return getPollingObserver()

def getBsdObserver():
    from .kqueue import KqueueObserver
    return KqueueObserver

def getWindowsObserver():
    try:
        from .read_directory_changes import WindowsApiObserver
        return WindowsApiObserver
    except Exception:
        warnings.warn("Failed to import read_directory_changes. Fall back to polling.")
        return getPollingObserver()


platformModuleMap = {
    "bsd": getBsdObserver,
    "linux": getLinuxObserver,
    "darwin": getDarwinObserver,
    "windows": getWindowsObserver,
    "polling": getPollingObserver,
}

if platform.is_linux():
    platformName = "linux"
elif platform.is_darwin():
    platformName = "darwin"
elif platform.is_bsd():
    platformName = "bsd"
elif platform.is_windows():
    platformName = "windows"
else:
    platformName = "polling"

Observer = platformModuleMap[platformName]()

__all__ = ["Observer"]
