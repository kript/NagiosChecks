#!/software/bin/python
# vim: tabstop=8 expandtab shiftwidth=4 softtabstop=4
"""
NetApp Nagios script using the official API to query the interface metrics 

IMPORTANT: an api enabled user must be defined on the system
This can be done on 7-Mode with;

(pre OnTAp 8.1)
useradmin role add api_only -c "created by jc18" -a api-*, login-http-admin
useradmin group add sandb_api -c "created by jc18 20140218" -r api_only
useradmin user add sandb_api_only -c "created by jc18 20140218" -g sandb_api

(post 8.1)

useradmin role add api_only -a api-*,login-http-admin
useradmin group add sandb_api -c "created by jc18 20140402" -r api_only
useradmin user add sandb_api_only  -c "created by jc18 20140402" -g sandb_api

jc18 20140331
$Id$
"""

import sys
from collections import defaultdict
import nagiosplugin
import argparse
import logging

#put the location of your sdk here
sys.path.append("/software/storage/NetApp/netapp-manageability-sdk-5.2/lib/python/NetApp")
from NaServer import *

_log = logging.getLogger('nagiosplugin')

def get_counter_values(filer, s, perf_obj, counter_values):
    """
    NetApp Manageability SDK/API code
    written against v5.2 of the library
    perf-object-get-instances-iter-* operation
    Usage: 
    perf_operation.py <filer> <user> <password> get-counter-values <objectname> [ <counter1> <counter2>...]
    changed from API example to handle just one performance object instance
    """

    max_records = 10
    interfaces =  defaultdict(dict) 


    perf_in = NaElement("perf-object-get-instances-iter-start")
    perf_in.child_add_string("objectname", perf_obj)
    counters = NaElement("counters")

    """
    uncomment the below to select which counters, otherwise it dumps them all
        if ( args > 1 ) :
        i = 3
        
        while(i < len(sys.argv)):
            counters.child_add_string("counter", sys.argv[i])
            i = i + 1
        perf_in.child_add(counters)
    """

    # Invoke API
    out = s.invoke_elem(perf_in)

    if(out.results_status() == "failed"):
        print(out.results_reason() + "\n")
        sys.exit(2)
    
    iter_tag = out.child_get_string("tag")
    num_records = 1

    while(int(num_records) != 0):
        perf_in = NaElement("perf-object-get-instances-iter-next")
        perf_in.child_add_string("tag", iter_tag)
        perf_in.child_add_string("maximum", max_records)
        out = s.invoke_elem(perf_in)

        if(out.results_status() == "failed"):
            print(out.results_reason() + "\n")
            sys.exit(2)

        num_records = out.child_get_int("records")
	
        if(num_records > 0) :
            instances_list = out.child_get("instances")            
            instances = instances_list.children_get()

            for inst in instances:
                inst_name = inst.child_get_string("name")
                counters_list = inst.child_get("counters")
                counters = counters_list.children_get()
                #force the creation of a list here, otherwise its a dict
                # thanks to defaultdict, above
                interfaces[inst_name] = defaultdict(dict)


                #import pprint
                #pp = pprint.PrettyPrinter(indent=4)
                #pp.pprint(interfaces)

                for counter in counters:
                    counter_name = counter.child_get_string("name")
                    counter_value = counter.child_get_string("value")
                    name = filer + "." + inst_name + "." + counter_name
                    """
                    OnTap >= 8.1 also has the additional counters of
                    instance_name
                    node_name
                    instance_uuid
                    so we can't assume its an integer
                    and as all the values are unicode, we can't use 
                    isinstance() to determine TheRightWay, so have to catch 
                    exceptions
                    """
                    
                    try:
                        interfaces[inst_name][str(counter_name)] = \
                                int(counter_value) 
                    except ValueError, e:
                        _log.debug(\
                                   'non int var found, must be an 8.1 system; trying str')
                        interfaces[inst_name][str(counter_name)] = \
                                str(counter_value) 


    perf_in= NaElement("perf-object-get-instances-iter-end")
    perf_in.child_add_string("tag", iter_tag)
    out = s.invoke_elem(perf_in)

    if(out.results_status() == "failed"):
            print(out.results_reason() + "\n")
            sys.exit(2)

    return(interfaces)

"""
nagios plugin class overrides here
"""
class Logging(nagiosplugin.Resource):
    """
    provide the debug and verbose functionality
    boiler platedothe docs..
    """
    def probe(self):
        _log.warning('warning message')
        _log.info('info message')
        _log.debug('debug message')
        return [nagiosplugin.Metric('zero', 0, context='default')]

class Toaster(nagiosplugin.Resource):
    """
    Determines the system Network interface stats
    The `probe` method returns the following for all interfaces
    'recv_packets'
    'recv_errors'
    'send_packets'
    'send_errors'
    'collisions'
    'recv_data'
    'send_data'
    'recv_mcasts'
    'send_mcasts'
    'recv_drop_packets
    """

    def __init__(self, filer, user, pw, interface=False):
        self.filer = filer
        self.user = user
        self.pw = pw
        self.specific_interface = interface
        self.perf_obj = "ifnet"
        self.counter_values = ["recv_packets",
                  "recv_errors",
                  "send_packets",
                  "send_errors",
                  "collisions",
                  "recv_data", 
                  "send_data",
                  "recv_mcasts", 
                  "send_mcasts",
                  "recv_drop_packets"
                 ]


    def Connect(self):
        """
        connect to the netapp via the API
        """

        #self.s = NaServer(self.filer, 1, 3)
        self.s = NaServer(self.filer, 1, 9)
        self.out = self.s.set_transport_type('HTTPS')
        _log.debug("attempting to connect to filer via HTTPS")

        if (self.out and self.out.results_errno() != 0) :
            r = self.out.results_reason()
            _log.warn("Connection to filer failed: " + r + "\n")
            sys.exit(3)

        self.out = self.s.set_style('LOGIN')
        _log.debug("attempting to login to " + self.filer + "\n")
    
        if (self.out and self.out.results_errno() != 0) :
            r = self.out.results_reason()
            _log.warn("Connection to filer failed: " + r + "\n")
            sys.exit(3)

        self.out = self.s.set_admin_user(self.user, self.pw)
        _log.debug("set admin user to" + self.user + "\n")


    def cpus(self):
        _log.info('counting cpus with "nproc"')
        cpus = int(subprocess.check_output(['nproc']))
        _log.debug('found %i cpus in total', cpus)
        return cpus



    def probe(self):
        """
        use the netapp API and connection object
        to extract the specified counters for the object
        and return in a dictionary of dictionaries
        in the self.data var e.g.
        print self.data[self.specific_interface]["send_data"]
        This is implicity used by the nagiosplugin class to generate the metrics
        if an interface is specified, it returns that, otherwise returns 
        all interfaces, skipping the 'filername' aggregate metric, which seems
        to be a 'since boot' set of counters

        """


        #turn the filer FQDN into something more Graphite Friendly
        self.filername = self.filer.split(".")[0]
        self.Connect()

        _log.info('attempting to grab all interface data')

        self.data = \
                get_counter_values(self.filername, 
                                   self.s, 
                                   self.perf_obj, 
                                   self.counter_values,
                                  )
        #import pprint
        #pp = pprint.PrettyPrinter(indent=4)
        #pp.pprint(self.data)

        if self.specific_interface:
            #print self.data[self.specific_interface]["send_data"]
            metricname = \
                    self.filer + "_" + self.specific_interface + "_" + "send_errors"
            testm = nagiosplugin.Metric( metricname,
                                self.data[self.specific_interface]["send_errors"],
                                'c', 
                                min=0, 
                                context='errors', # set this to errors
                               )
            #import pprint
            #pp = pprint.PrettyPrinter(indent=4)
            #pp.pprint(testm)
            yield testm

        else:
            for metric in ["send_errors", "recv_errors", "collisions",
                           "recv_drop_packets" ]:
                _log.debug('reporting on %s', metric)
                # a number of interfaces are provided by the API as totals since
                # boot, which isn't useful for point in time alerting, so ignore
                # them
                for instance in self.data:
                    _log.debug('reporting on if %s', instance)

                    #skip the api provided filenamed interface thats just totals
                    if self.filername in instance:

                        _log.debug('skipping totaled interface: %s',\
                                   str(instance))
                        continue 
                   #skip the interface groups, just look at individual if's
                   # pre OnTAP 8.1
                    if "ifgrp" in instance:
                        _log.debug('skipping ifgrp interface: %s',\
                                   str(instance))
                        continue
                   #skip the virtual interface (vif) groups, just look at individual if's
                   # pre OnTAP 8.1
                    if "vif" in instance:
                        _log.debug('skipping vif interface: %s',\
                                   str(instance))
                        continue
                    
                    #print "interface: " + str(instance) + " errors: " + \
                    #        str(self.data[instance][metric])
                    metricname = \
                        self.filer + "_" + instance + "_" + metric
                    yield nagiosplugin.Metric( \
                                            metricname,
                                            self.data[instance][metric],
                                            min=0,
                                            context='errors',
                                            )





        #_log.debug('raw load is %s', load)
        #cpus = self.cpus() if self.percpu else 1
        #load = [float(l) / cpus for l in load]
        #for i, period in enumerate([1, 5, 15]):
        #    yield nagiosplugin.Metric('load%d' % period, load[i], min=0,
        #                              context='load')





@nagiosplugin.guarded
def main() :
    """
    Takes care of the argument parsing and nagios command line returning
    """
    argp = argparse.ArgumentParser(description=__doc__)
    argp.add_argument('-w', '--warning', metavar='RANGE', default='',
                      help='return warning if interface is outside RANGE')
    argp.add_argument('-c', '--critical', metavar='RANGE', default='',
                      help='return critical if interface is outside RANGE')
    argp.add_argument('-i', '--interface', default=False, type=str,
                        help="specify interface to monitor")
    argp.add_argument('-v', '--verbose', action='count', default=0,
                      help='increase output verbosity (use up to 3 times)')
    argp.add_argument('-l', '--logname', default=False, type=str,
                        help="NetApp API username")
    argp.add_argument('-p', '--password', default=False, type=str,
                        help="NetApp API password")
    argp.add_argument('-H', '--hostname', default=False, type=str,
                        help="NetApp filer to query (FQDN pls)")
    args = argp.parse_args()

    check = nagiosplugin.Check(
        Toaster(args.hostname, args.logname, args.password, args.interface),
        nagiosplugin.ScalarContext('errors', args.warning, args.critical),
        #LoadSummary(args.percpu),
    )
    #now make all the checks actually happen
    check.main(verbose=args.verbose)

    #print args

    #netapp = Toaster(args.hostname, args.logname, args.password, args.interface)
    ##netapp.Connect()
    #netapp.probe()
    ##netapp.report()

    
"""  
start here
"""


if __name__ == '__main__':
    main()
