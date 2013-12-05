#!/usr/bin/python2
# Copyright 2013 Maksim Podlesniy <root at nightbook.info>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston,
# MA 02110-1301, USA.
'''
Process monitor prototype

    config file example:

        [cron]
        pid_file = /var/run/crond.pid
        start_exec = /etc/init.d/cronie start

        [syslog]
        pid_file = /var/run/rsyslogd.pid
        start_exec = /etc/init.d/rsyslog start

    or more...

        [cron]
        cmdline = crond
        pid_file = /var/run/crond.pid
        start_exec = /etc/init.d/cronie start
        stop_exec = /etc/init.d/cronie stop ; /etc/init.d/cronie zap
        interval = 15
        bad_interval = 2

        [syslog]
        pid_file = /var/run/rsyslogd.pid
        start_exec = /etc/init.d/rsyslog start
        bad_interval = 2
'''

from __future__ import print_function
from ConfigParser import ConfigParser, MissingSectionHeaderError, NoOptionError
from time import time, sleep
from sys import stderr, argv
from os import access, X_OK, system
from os.path import isfile
from string import find


class ProcessSentinel():
    '''Some sentinel
    '''
    __bad = False

    def __init__(self, inspection, pid_file, start_exec, cmdline=None, bad_interval=3, interval=10, stop_exec=None, unix_socket=None):
        self.__inspection = inspection
        self.__pid_file = pid_file
        self.__check_exec__(start_exec)
        self.__start_exec = start_exec
        self.__cmdline = cmdline
        if stop_exec:
            self.__check_exec__(stop_exec)
        self.__stop_exec = stop_exec
        self.__unix_socket = unix_socket
        try:
            self.__interval = int(interval)
            self.__bad_interval = int(bad_interval)
        except ValueError:
            self.exception('interval must be integer')
        if self.__interval <= 0 or self.__bad_interval <= 0:
            self.exception('interval must be more 0')
        self.__diary = 0

    def exception(self, message):
        print('Inspection [%s]. %s' % (self.__inspection, message), file=stderr)
        exit(1)

    def __check_exec__(self, some_exec):
        '''Executable test
        '''
        some_exec = some_exec.split(' ')[0]
        if not isfile(some_exec):
            self.exception('%s exec not found' % some_exec)
        elif not access(some_exec, X_OK):
            self.exception('%s executable' % some_exec)

    def pid(self):
        '''Return pid
        '''
        try:
            with open(self.__pid_file) as f:
                _pid = f.read()
        except Exception, e:
            self.restart(e)
        else:
            try:
                return int(_pid)
            except ValueError:
                self.restart('Cannot read pid file from %s' % self.__pid_file)

    def __call__(self):
        if self.__bad:
            interval = self.__bad_interval
        else:
            interval = self.__interval

        if (time() - self.__diary) > interval:
            self.__diary = time()
            if self.health():
                self.__bad = True
            else:
                self.__bad = False

    def health(self):
        '''Check health status
        '''
        _pid = self.pid()
        if _pid:
            try:
                with open('/proc/%s/cmdline' % _pid) as cmdline:
                    cmd = cmdline.read()
            except Exception, e:
                self.restart(e)
                return 1
            else:
                if self.__cmdline and find(cmd, self.__cmdline) == -1:
                    self.restart('Not match cmdline \'%s\'' % self.__cmdline)
                    return 1
                elif self.__unix_socket and not isfile(self.__unix_socket):
                    self.restart('Socket \'%s\' not exists' % self.__unix_socket)
                    return 1
        else:
            return 1

    def restart(self, reason):
        '''Check health status
        '''
        print('%s restart. Reason - %s' % (self.__inspection, reason))
        if self.__stop_exec:
            system(self.__stop_exec)
        system(self.__start_exec)

class ScheduleInspections():
    __required_config_fields = [
            'pid_file',
            'start_exec'
            ]
    __unrequired_config_fields = [
            'cmdline',
            'interval',
            'bad_interval',
            'stop_exec',
            'unix_socket',
        ]
    __miss_opt_message = r'Config option error in %s. Section [%s], option "%s" not found'

    def __init__(self, config_file):
        self.__config_file = config_file

    def __config__(self):
        '''Get config from file
        '''
        config = {}
        cfg = ConfigParser()
        cfg.read(self.__config_file)
        for inspection in cfg.sections():
            inspection_params = {}
            for field in self.__required_config_fields:
                try:
                    inspection_params[field] = cfg.get(inspection, field)
                except NoOptionError:
                    print(self.__miss_opt_message % (self.__config_file, inspection, field), file=stderr)
                    exit(1)
            for field in self.__unrequired_config_fields:
                try:
                    inspection_params[field] = cfg.get(inspection, field)
                except NoOptionError:
                    pass
            config[inspection] = ProcessSentinel(inspection, **inspection_params)

        return config

    def __call__(self):
        config = self.__config__()
        inspectors = list(config.keys())
        while 1:
            for sentinel in inspectors:
                config[sentinel]()
            sleep(1)

if __name__ == '__main__':
    if len(argv) < 2:
        print('Second argument must be config file', file=stderr)
        print(__doc__, file=stderr)
        exit(1)
    else:
        inspector = ScheduleInspections(argv[1])
        inspector()

