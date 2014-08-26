#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2011 Yesudeep Mangalapilly <yesudeep@gmail.com>
# Copyright 2012 Google, Inc.
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
:module: watchdog.observers.inotify
:synopsis: ``inotify(7)`` based emitter implementation.
:author: Sebastien Martini <seb@dbzteam.org>
:author: Luke McCarthy <luke@iogopro.co.uk>
:author: yesudeep@google.com (Yesudeep Mangalapilly)
:author: Tim Cuthbertson <tim+github@gfxmonk.net>
:platforms: Linux 2.6.13+.

.. ADMONITION:: About system requirements

    Recommended minimum kernel version: 2.6.25.

    Quote from the inotify(7) man page:

        "Inotify was merged into the 2.6.13 Linux kernel. The required library
        interfaces were added to glibc in version 2.4. (IN_DONT_FOLLOW,
        IN_MASK_ADD, and IN_ONLYDIR were only added in version 2.5.)"

    Therefore, you must ensure the system is running at least these versions
    appropriate libraries and the kernel.

.. ADMONITION:: About recursiveness, event order, and event coalescing

    Quote from the inotify(7) man page:

        If successive output inotify events produced on the inotify file
        descriptor are identical (same wd, mask, cookie, and name) then they
        are coalesced into a single event if the older event has not yet been
        read (but see BUGS).

        The events returned by reading from an inotify file descriptor form
        an ordered queue. Thus, for example, it is guaranteed that when
        renaming from one directory to another, events will be produced in
        the correct order on the inotify file descriptor.

        ...

        Inotify monitoring of directories is not recursive: to monitor
        subdirectories under a directory, additional watches must be created.

    This emitter implementation therefore automatically adds watches for
    sub-directories if running in recursive mode.

Some extremely useful articles and documentation:

.. _inotify FAQ: http://inotify.aiken.cz/?section=inotify&page=faq&lang=en
.. _intro to inotify: http://www.linuxjournal.com/article/8478

"""

from __future__ import with_statement

import os
import threading
from .inotify_buffer import InotifyBuffer, STOP_EVENT

from watchdog.observers.api import (
    EventEmitter,
    BaseObserver,
    DEFAULT_EMITTER_TIMEOUT,
    DEFAULT_OBSERVER_TIMEOUT
)

from watchdog.events import (
    DirDeletedEvent,
    DirModifiedEvent,
    DirMovedEvent,
    DirCreatedEvent,
    FileDeletedEvent,
    FileModifiedEvent,
    FileMovedEvent,
    FileCreatedEvent,
    generate_sub_moved_events,
    generate_sub_created_events,
)
from watchdog.utils import unicode_paths


class InotifyEmitter(EventEmitter):
    """
    inotify(7)-based event emitter.

    :param event_queue:
        The event queue to fill with events.
    :param watch:
        A watch object representing the directory to monitor.
    :type watch:
        :class:`watchdog.observers.api.ObservedWatch`
    :param timeout:
        Read events blocking timeout (in seconds).
    :type timeout:
        ``float``
    """

    def __init__(self, event_queue, watch, timeout=DEFAULT_EMITTER_TIMEOUT):
        EventEmitter.__init__(self, event_queue, watch, timeout)
        self._lock = threading.Lock()
        self._inotify = InotifyBuffer(unicode_paths.encode(watch.path),
                                      watch.is_recursive)

    def _decode_path(self, path):
        """ Decode path only if unicode string was passed to this emitter. """
        if isinstance(self.watch.path, bytes):
            return path
        return unicode_paths.decode(path)

    def run(self):
        self._inotify.start()
        return EventEmitter.run(self)

    @property
    def ready(self):
        return self._inotify.ready

    def on_thread_stop(self):
        self._inotify.close()

    def queue_events(self, timeout):
        with self._lock:
            event = self._inotify.read_event()

            if event is STOP_EVENT:
                return

            if isinstance(event, tuple):
                move_from, move_to = event
                src_path = self._decode_path(move_from.src_path)
                dest_path = self._decode_path(move_to.src_path)
                cls = DirMovedEvent if move_from.is_directory else FileMovedEvent
                self.queue_event(cls(src_path, dest_path))
                self.queue_event(DirModifiedEvent(os.path.dirname(src_path)))
                self.queue_event(DirModifiedEvent(os.path.dirname(dest_path)))
                if move_from.is_directory and self.watch.is_recursive:
                    for sub_event in generate_sub_moved_events(src_path, dest_path):
                        self.queue_event(sub_event)
                return

            src_path = self._decode_path(event.src_path)
            if event.is_moved_to:
                cls = DirCreatedEvent if event.is_directory else FileCreatedEvent
                self.queue_event(cls(src_path))
                self.queue_event(DirModifiedEvent(os.path.dirname(src_path)))
                if event.is_directory and self.watch.is_recursive:
                    for sub_event in generate_sub_created_events(src_path):
                        self.queue_event(sub_event)
            elif event.is_attrib:
                cls = DirModifiedEvent if event.is_directory else FileModifiedEvent
                self.queue_event(cls(src_path))
            elif event.is_modify:
                cls = DirModifiedEvent if event.is_directory else FileModifiedEvent
                self.queue_event(cls(src_path))
            elif event.is_delete_self:
                cls = DirDeletedEvent if event.is_directory else FileDeletedEvent
                self.queue_event(cls(src_path))
            elif event.is_delete or event.is_moved_from:
                cls = DirDeletedEvent if event.is_directory else FileDeletedEvent
                self.queue_event(cls(src_path))
                self.queue_event(DirModifiedEvent(os.path.dirname(src_path)))
            elif event.is_create:
                cls = DirCreatedEvent if event.is_directory else FileCreatedEvent
                self.queue_event(cls(src_path))
                self.queue_event(DirModifiedEvent(os.path.dirname(src_path)))


class InotifyObserver(BaseObserver):
    """
    Observer thread that schedules watching directories and dispatches
    calls to event handlers.
    """

    def __init__(self, timeout=DEFAULT_OBSERVER_TIMEOUT):
        BaseObserver.__init__(self, emitter_class=InotifyEmitter,
                              timeout=timeout)
