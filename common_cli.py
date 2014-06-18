# Copyright 2014 Google Inc. All rights reserved.
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
"""Common code for ADB and Fastboot CLI.

Usage introspects the given class for methods, args, and docs to show the user.

StartCli handles connecting to a device, calling the expected method, and
outputting the results.
"""

import cStringIO
import inspect
import re
import sys

import gflags

import usb_exceptions

gflags.DEFINE_integer('timeout_ms', 200, 'Timeout in milliseconds.')

FLAGS = gflags.FLAGS

_BLACKLIST = {
    'Connect',
    'Close',
    'ConnectDevice',
    'DeviceIsAvailable',
}


def Uncamelcase(name):
  parts = re.split(r'([A-Z][a-z]+)', name)[1:-1:2]
  return ('-'.join(parts)).lower()


def Camelcase(name):
  return name.replace('-', ' ').title().replace(' ', '')


def Usage(adb_dev):
  methods = inspect.getmembers(adb_dev, inspect.ismethod)
  print 'Methods:'
  for name, method in methods:
    if name.startswith('_'):
      continue
    if not method.__doc__:
      continue
    if name in _BLACKLIST:
      continue

    argspec = inspect.getargspec(method)
    args = argspec.args[1:] or ''
    # Surround default'd arguments with []
    defaults = argspec.defaults or []
    if args:
      args = (args[:-len(defaults)] +
              ['[%s]' % arg for arg in args[-len(defaults):]])

      args = ' ' + ' '.join(args)

    print '  %s%s:' % (Uncamelcase(name), args)
    print '    %s' % method.__doc__


def StartCli(argv, connect_callback, kwarg_callback=None, **connect_kwargs):
  """Starts a common CLI interface for this usb path and protocol."""
  argv = argv[1:]

  try:
    dev = connect_callback(
        default_timeout_ms=FLAGS.timeout_ms, **connect_kwargs)
  except usb_exceptions.DeviceNotFoundError as e:
    print >> sys.stderr, 'No device found: %s' % e
    return
  except usb_exceptions.CommonUsbError as e:
    print >> sys.stderr, 'Could not connect to device: %s' % e
    raise

  if not argv:
    Usage(dev)
    return

  kwargs = {}

  # CamelCase method names, eg reboot-bootloader -> RebootBootloader
  method_name = Camelcase(argv[0])
  method = getattr(dev, method_name)
  argspec = inspect.getargspec(method)
  num_args = len(argspec.args) - 1  # self is the first one.
  num_args -= len(argspec.defaults or [])
  # Handle putting the remaining command line args into the last normal arg.
  argv.pop(0)

  # Flags -> Keyword args
  if kwarg_callback:
    kwarg_callback(kwargs, argspec)

  try:
    if num_args == 1:
      # Only one argument, so join them all with spaces
      result = method(' '.join(argv), **kwargs)
    else:
      result = method(*argv, **kwargs)
  except Exception as e:  # pylint: disable=broad-except
    sys.stdout.write(str(e))
    return
  finally:
    dev.Close()

  if result is not None:
    if isinstance(result, cStringIO.OutputType):
      result = result.getvalue()
    elif isinstance(result, list):
      result = '\n'.join(str(r) for r in result)
    sys.stdout.write(result)
  sys.stdout.write('\n')
