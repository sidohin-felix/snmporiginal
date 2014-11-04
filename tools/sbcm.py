#!/usr/bin/python
#SNMP Booster Cache Manager

import argparse
import sys
import pprint
from shinken.log import logger
import importlib


printer = pprint.PrettyPrinter()


# Argument parsing
parser = argparse.ArgumentParser(description='SNMP Booster Cache Manager')
parser.add_argument('-d', '--db-name', type=str, default='booster_snmp',
                    help='Database name. Default=booster_snmp')
parser.add_argument('-b', '--backend', type=str, default='redis',
                    help='Backend. Supported : redis, mongodb, memcache')
# Search
subparsers = parser.add_subparsers(help='sub-command help')
search_parser = subparsers.add_parser('search', help='search help')
search_parser.add_argument('-H', '--host-name', type=str,
                    help='Host name')
search_parser.add_argument('-S', '--service-name', type=str,
                    help='Service name')
search_parser.add_argument('-t', '--show-triggers',
                    default=False, action='store_true',
                    help='Show triggers')
search_parser.add_argument('-d', '--show-datasource',
                    default=False, action='store_true',
                    help='Show datasource')
search_parser.set_defaults(command='search')
# Delete
delete_parser = subparsers.add_parser('delete', help='delete help')
del_subparsers = delete_parser.add_subparsers(help='delete sub-command help')
# Delete host
delhost_parser = del_subparsers.add_parser('host', help='delete host help')
delhost_parser.add_argument('-H', '--host-name', type=str, required=True,
                    help='Host name')
delhost_parser.set_defaults(command='delete-host')
# Delete service
delservice_parser = del_subparsers.add_parser('service', help='delete service help')
delservice_parser.add_argument('-H', '--host-name', type=str, required=True,
                    help='Host name')
delservice_parser.add_argument('-S', '--service-name', type=str, required=True,
                    help='Service name')
delservice_parser.set_defaults(command='delete-service')
# Clear
clear_parser = subparsers.add_parser('clear', help='clear help')
clear_subparsers = clear_parser.add_subparsers(help='clear sub-command help')
# Clear mapping
clearservice_parser = clear_subparsers.add_parser('mapping', help='Clear service(s) mapping')
clearservice_parser.set_defaults(command='clear-mapping')
clearservice_parser.add_argument('-H', '--host-name', type=str,
                    help='Host name')
clearservice_parser.add_argument('-S', '--service-name', type=str,
                    help='Service name')
# Clear ALL cache
clearcache_parser = clear_subparsers.add_parser('cache', help='clear cache help')
clearcache_parser.set_defaults(command='clear-cache')
# Clear old service in cache
clearold_parser = clear_subparsers.add_parser('old', help='clear old help')
clearold_parser.set_defaults(command='clear-old')
clearold_parser.add_argument('-H', '--hour', type=str,
                    help='No data since ... hours')



def search(host=None, service=None, show_ds=False, show_triggers=False):
    if host is not None and service is not None:
        results = [db_client.get_service(host, service)]
    elif service is not None:
        results = db_client.get_hosts_from_service(service)
    # Prepare columns
    elif host is not None:
        results = db_client.get_services_from_host(host)
    # Both none, show keys
    else:
        results = db_client.show_keys()
        printer.pprint(results)
        exit()

    if results == [None]:
        print "No results found in DB!"

    else:
        if not show_ds:
            for r in results: del r['ds']
        if not show_triggers:
            for r in results: del r['triggers']


        for result in results:
            print "=" * 79
            print "== %s" % result['host']
            print "== %s" % result['service']
            print "=" * 79
            printer.pprint(result)
     

def clear(host=None, service=None):
    if host is not None and service is not None:
        results = [db_client.get_service(host, service)]

    elif service is not None:
        results = db_client.get_hosts_from_service(service)
    # Prepare columns
    elif host is not None:
        results = db_client.get_services_from_host(host)
    # Both none, show keys
    else:
        results = db_client.get_all_services()

    for result in results:
        if 'instance_name' in result and 'instance' in result:
            del result['instance']
            db_client.update_service(result['host'], result['service'], result, force=True)
            print "Instance cleared for '%s' and service '%s'" % (result['host'], result['service'])
        else:
            print "Nothing to do for host '%s' and service '%s'" % (result['host'], result['service'])


def delete(host=None, service=None):
    if service is not None:
        nb_del = db_client.delete_services([(host, service)])
    else:
        nb_del = db_client.delete_host(host)

    print "%d key(s) deleted in database" % nb_del

args = parser.parse_args()
#print(args.accumulate(args.integers))

#print(args)

try:
    dbmodule = importlib.import_module("shinken.modules.snmp_booster.libs.%sclient" % args.backend)
except ImportError as exp:
    logger.error("[SBCM] [code 0001] Import error. %s seems missing." % args.backend)
    raise ImportError(exp)



db_client = dbmodule.DBClient("localhost")
if not db_client.connect():
    logger.critical("Impossible to connect to %s DB" % args.backend)

if args.command == 'search':
    search(args.host_name, args.service_name, args.show_datasource, args.show_triggers)

#import pdb;pdb.set_trace()

elif args.command == "clear-cache":
    # Drop database
    db_client.clear_cache()

elif args.command == "clear-mapping":
    # Remove 'instance' if 'instance_name' for service(s)
    clear(args.host_name, args.service_name)

elif args.command == "clear-old":
    # Remove all keys not in members
    #db_client.clear_old()
    pass

elif args.command.startswith("delete"):
    # Remove host:* key
    if not 'service_name' in args:
        args.service_name = None
    delete(args.host_name, args.service_name)

else:
    print "Unknown command %s" % args.commmand
