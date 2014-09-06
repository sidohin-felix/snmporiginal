from threading import Thread
import time

from shinken.log import logger
from pysnmp.entity.rfc3413.oneliner import cmdgen


class SNMPWorker(Thread):
    def __init__(self, mapping_queue):
        Thread.__init__(self)
        self.cmdgen = cmdgen.AsynCommandGenerator()
        self.mapping_queue = mapping_queue
        self.must_run = False
    
    def run(self):
        self.must_run = True
        while self.must_run:
            task_prepared = 0
            
            while (not self.mapping_queue.empty()) and task_prepared <= 1:
                task_prepared += 1
                snmp_task = self.mapping_queue.get()
                if snmp_task['type'] == 'bulk':
                    # dict keys:
                        # authData: cmdgen.CommunityData('ERS8600-1')
                        # transportTarget: cmdgen.UdpTransportTarget((transportTarget, 1161))
                        # nonRepeaters: 0
                        # maxRepetitions: 
                        # varNames: ( '1.3.6.1.2.1.2.2.1.2.0', )
                        # cbInfo: (cbFun, None)
                    self.cmdgen.asyncBulkCmd(**snmp_task['data'])
                elif snmp_task['type'] == 'next':
                    # dict keys:
                        # authData: cmdgen.CommunityData('ERS8600-1')
                        # transportTarget: cmdgen.UdpTransportTarget((transportTarget, 1161))
                        # varNames: ( '1.3.6.1.2.1.2.2.1.2.0', )
                        # cbInfo: (cbFun, None)
                    self.cmdgen.asyncNextCmd(**snmp_task['data'])
                elif snmp_task['type'] == 'get':
                    # dict keys:
                        # authData: cmdgen.CommunityData('ERS8600-1')
                        # transportTarget: cmdgen.UdpTransportTarget((transportTarget, 1161))
                        # varNames: ( '1.3.6.1.2.1.2.2.1.2.0', )
                        # cbInfo: (cbFun, None)
                    self.cmdgen.asyncGetCmd(**snmp_task['data'])
#                if snmp_task['type'] in ['bulk', 'next', 'get']:
#                    getattr(self.cmdgen, "async" + snmp_task['type'].capitalize() + "GetCmd")(**snmp_task['data'])
#                else:
                    # errrrrrror
#                    pass

                self.mapping_queue.task_done()

            if task_prepared > 0:
                self.cmdgen.snmpEngine.transportDispatcher.runDispatcher()
            time.sleep(0.5)


    def stop_worker(self):
        self.must_run = False


def callback_get(sendRequestHandle, errorIndication, errorStatus, errorIndex,
                 varBinds, cbCtx):
    #print sendRequestHandle, errorIndication, errorStatus, errorIndex, varBinds, cbCtx
    print 5*"callback_get"
    results = cbCtx[0]
    service_result = cbCtx[1]
    result_queue = cbCtx[2]
    for oid, value in varBinds:
        oid = "." + oid.prettyPrint()
        if oid in results:
            results[oid]['value'] = value
            results[oid]['check_time'] = time.time()

    # Check if we get all values
    if not any([True for oid in results.values() if oid['value'] is None]):
        # Yes
        result_queue.put(results)
        # Prepare datas for the current service
        tmp_results = [r for r in results.values() if r['key']['host'] == service_result['host'] and r['key']['service'] == service_result['service']]
        for tmp_result in tmp_results:
            key = tmp_result.get('key')
            # ds name
            ds_name = key.get('ds_name')
            # Last value
            last_value_key = ".".join(("ds", key.get('ds_name'), key.get('oid_type') + "_value_last"))
            # New value
            value_key = ".".join(("ds", key.get('ds_name'), key.get('oid_type') + "_value"))
            # Set last value
            service_result['db_data']['ds'][ds_name][last_value_key] = tmp_result.get('value_last')
            # Set value
            service_result['db_data']['ds'][ds_name][value_key] = tmp_result.get('value')
        ## Set last check time
        service_result['db_data']['last_check_time'] = service_result['db_data']['check_time']
        ## Set check time
        service_result['db_data']['check_time'] = time.time()
        ## set as received
        service_result['state'] = 'received'

    else:
        print "datamissing"
        print [oid for oid in results.values() if oid['value'] is None]
        #print [oid['value'] for oid in results.values()]

def callback_mapping_next(sendRequestHandle, errorIndication,
                          errorStatus, errorIndex, varBinds, cbCtx):
    mapping_oid = cbCtx[0]
    result = cbCtx[1]
    for tableRow in varBinds:
        for oid, instance_name in tableRow:
            oid = "." + oid.prettyPrint()
            # Test if we are not in the mapping oid
            if not oid.startswith(mapping_oid):
                # We are not in the mapping oid
                result['finished'] = True
                return False
            instance = oid.replace(mapping_oid + ".", "")
            #print "OID", oid
            #print "MAPPING", mapping_oid
            #print "VAL", instance_name.prettyPrint()
            if instance_name in result['data']:
                result['data'][instance_name] = instance
            # Check if mapping is finished
            if all(result.values()):
                result['finished'] = True
                return False

    return True


def callback_mapping_bulk(sendRequestHandle, errorIndication,
                          errorStatus, errorIndex, varBinds, cbCtx):
    print "callback_mapping_bulk"
    cbCtx[0]
    print sendRequestHandle, errorIndication, errorStatus, errorIndex, varBinds, cbCtx


