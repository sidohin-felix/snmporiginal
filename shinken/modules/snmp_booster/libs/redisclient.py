# -*- coding: utf-8 -*-

# Copyright (C) 2012-2014:
#    Thibault Cohen, thibault.cohen@savoirfairelinux.com
#
# This file is part of SNMP Booster Shinken Module.
#
# Shinken is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Shinken is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with SNMP Booster Shinken Module.
# If not, see <http://www.gnu.org/licenses/>.


""" This module contains database/cache abstraction class """

import ast
import re

from shinken.log import logger

try:
    from redis import StrictRedis
except ImportError as exp:
    logger.error("[SnmpBooster] [code 1201] Import error. Redis seems missing.")
    raise ImportError(exp)

from utils import merge_dicts


class DBClient(object):
    """ Class used to abstract the use of the database/cache """

    def __init__(self, db_host, db_port=6379, db_name=None):
        self.db_host = db_host
        self.db_port = db_port

        self.db_conn = None

    def connect(self):
        """ This function inits the connection to the database """
        try:
            self.db_conn = StrictRedis(host=self.db_host, port=self.db_port)
        except Exception as exp:
            logger.error("[SnmpBooster] [code 1202] Redis Connection error:"
                         " %s" % str(exp))
            return False
        return True

    def disconnect(self):
        """ This function kills the connection to the database """
        #self.db_conn.client_kill(self.db_host + ":" + str(self.db_port))
        pass

    @staticmethod
    def build_key(part1, part2):
        """ Build Redis key

        >>> build_key("part1", "part2")
        'part1:part2'
        """
        return ":".join((str(part1), str(part2)))

        

    @staticmethod
    def handle_error(result, context=""):
        """ This function handles mongodb errors """
        # NOTE make a decorator of it ...
        # If error
        if result['err'] is not None:
            # Prepare error context
            context_str = ""
            if context and isinstance(context, dict):
                # NOTE: warning what append with unicode ?
                context_str = ",".join(["%s:%s" % (key, val)
                                        for key, val in context.items()])
                context_str = "[" + context_str + "]"
            elif context and isinstance(context, str):
                context_str = context
            elif context:
                context_str = str(context_str)
            # Prepare error message
            error_message = ("[SnmpBooster] [code 1203] %s error putting "
                             "data in cache: %s" % (context_str,
                                                    str(result['err'])))
            logger.error(error_message)
            return True
        return False

    def update_service_init(self, host, service, data):
        # We need to generate key for redis :
         # Like host:3 => ['service', 'service2'] that link check interval to a service list
        key_ci = self.build_key(host, data["check_interval"])
        # Get services

        try:
            self.db_conn.sadd(key_ci, service)
        except Exception as exp:
            logger.error("[SnmpBooster] [code 1204] [%s, %s] "
                         "%s" % (host,
                                 service,
                                 str(exp)))
            return (None, True)


        # Then update propely host:service keys
        self.update_service(host, service, data)

    def update_service(self, host, service, data):
        """ This function updates/inserts a service
        It used by arbiter in hook_late_configuration
        to put the configuration in the database
        Return
        * query_result: None
        * error: bool
        """
        key = self.build_key(host, service)
        old_dict = self.db_conn.get(key)
        if old_dict is not None:
            old_dict = ast.literal_eval(old_dict)

        data = merge_dicts(old_dict, data)

        if data is None:
            return (None, True)

        # Save in redis
        try:
            self.db_conn.set(key, data)
        except Exception as exp:
            logger.error("[SnmpBooster] [code 1204] [%s, %s] "
                         "%s" % (host,
                                 service,
                                 str(exp)))
            return (None, True)

        return (None, False)
        #TODO : Handle error
        #return (None, self.handle_error(mongo_res, mongo_filter))

    def get_service(self, host, service):
        """ This function gets one service from the database
        Return
        :query_result: dict
        """
        key = self.build_key(host, service)
        # Get service
        try:
            data = self.db_conn.get(key)
        except Exception as exp:
            logger.error("[SnmpBooster] [code 1207] [%s, %s] "
                         "%s" % (host,
                                 service,
                                 str(exp)))
            return None
        #TODO : Test None?
        return ast.literal_eval(data) if data is not None else None

    def get_services(self, host, check_interval):
        """ This function Gets all services with the same host
        and check_interval
        Return
        :query_result: list of dicts
        """
        key_ci = self.build_key(host, check_interval)
        # Get services
        try:
            servicelist = self.db_conn.smembers(key_ci)

        except Exception as exp:
            logger.error("[SnmpBooster] [code 1208] [%s] "
                         "%s" % (host,
                                 str(exp)))
            return None

        if servicelist is None:
            #TODO : Bailout properly
            return None

        dict_list = []
        for service in servicelist:
            try:
                key = self.build_key(host, service)
                data = self.db_conn.get(key)
                if data is None:
                    logger.error("[SnmpBooster] [code 1209] [%s] Unknown service %s", host, service)
                    continue
                dict_list.append(ast.literal_eval(data))
            except Exception as exp:
                logger.error("[SnmpBooster] [code 1210] [%s] "
                             "%s" % (host,
                                     str(exp)))

        return dict_list

#For Debug

    def show_keys(self):
        return self.db_conn.keys()

    def get_hosts_from_service(self, service):
        results = []
        for key in self.db_conn.keys():
            if re.search(service, key) is None:
                # Look for service
                continue
            results.append(ast.literal_eval(self.db_conn.get(key)))

        return results

    def get_services_from_host(self, host):
        results = []
        for key in self.db_conn.keys():
            if re.match(host, key)is None:
                # Look for host
                continue
            if re.search(":[0-9]+$", key) is not None:
                # we skip host:interval
                continue
            results.append(ast.literal_eval(self.db_conn.get(key)))

        return results

