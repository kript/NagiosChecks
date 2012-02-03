#!/bin/sh

# ========================================================================================
# Brocade Fibre Channel Hardware monitor plugin for Nagios
# 
# Written by         	: John Constable (john.constable@sanger.ac.uk)
# Release               : 1.0
# Creation date		: 03 February 2011
# Revision date         : 03 February 2011
# Package               : DTB Plugins
# Description           : Nagios plugin to monitor LSI OnStor hardware with SNMP. 
#                         You must have ONSTOR-NASGW-MIB and ONSTOR-SYSSTAT-MIB from LSI.
#							based on the check_FCBrocade_hardware.sh script written by Steve Bosek (steve.bosek@ephris.net)
#							 from nagios-exchange.org
#
#                         Status Results:
#                         1 unknown
#                         2 faulty
#                         3 below-min
#                         4 nominal
#                         5 above-max
#                         6 absent
#                         For Sensors, valid values include ok(1), informational(2), warning(3), nonoperational(4), notavailable(5)
#						
# Usage                 : ./check_OnStor_hardware.sh [-H | --hostname HOSTNAME] [-c | --community COMMUNITY ] [-h | --help] | [-v | --version]
# Supported Type        : Test with ONS-SYS-6520/EverON-4.0.2.18CG
# -----------------------------------------------------------------------------------------
#
# TODO :  - Add Perfdata 
#         - Add SNMP v2 and 3 if necessary
#         
#		  
# =========================================================================================
#
# HISTORY :
#     Release	|     Date	|    Authors	| 	Description
# --------------+---------------+---------------+------------------------------------------
# 1.0		|   02.02.2012 |  John Constable	|	Creation
# =========================================================================================


# Nagios return codes
STATE_OK=0
STATE_WARNING=1
STATE_CRITICAL=2
STATE_UNKNOWN=3

# Plugin variable description
PROGNAME=$(basename $0)
RELEASE="Revision 1.0"
AUTHOR="(c) 2012 John Constable (john.constable@sanger.ac.uk)"

# Functions plugin usage
print_release() {
    echo "$RELEASE $AUTHOR"
}

print_usage() {
	echo ""
	echo "$PROGNAME $RELEASE - OnStor Hardware monitor"
	echo ""
	echo "Usage: $PROGNAME [-H | --hostname HOSTNAME] | [-c | --community COMMUNITY ] | [-h | --help] | [-v | --version]"
	echo ""
	echo "		-h  Show this page"
	echo "		-v  Plugin Version"
	echo "    -H  IP or Hostname of OnStor Head"
	echo "    -c  SNMP Community"
  echo ""
}

print_help() {
		print_usage
        echo ""
        print_release $PROGNAME $RELEASE
        echo ""
        echo ""
		exit 0
}

# Make sure the correct number of command line arguments have been supplied
if [ $# -lt 2 ]; then
    print_usage
    exit $STATE_UNKNOWN
fi

# Grab the command line arguments
while [ $# -gt 0 ]; do
    case "$1" in
        -h | --help)
            print_help
            exit $STATE_OK
            ;;
        -v | --version)
                print_release
                exit $STATE_OK
                ;;
        -H | --hostname)
                shift
                HOSTNAME=$1
                ;;
        -c | --community)
               shift
               COMMUNITY=$1
               ;;
        *)  echo "Unknown argument: $1"
            print_usage
            exit $STATE_UNKNOWN
            ;;
        esac
shift
done

TYPE=$(snmpwalk -v 1 -c $COMMUNITY $HOSTNAME SNMPv2-SMI::mib-2.47.1.1.1.1.2.1 | sed "s/.*STRING:\(.*\)$/\1/")
if [ $? == 1 ]; then
    echo "UNKNOWN - Could not connect to SNMP server $hostname.";
    exit $STATE_UNKNOWN;
fi

NBR_INDEX=$(snmpwalk -v 1 -c $COMMUNITY $HOSTNAME .1.3.6.1.4.1.1588.2.1.1.1.1.22.1.1 | wc -l )
i=1

while [ $i -le $NBR_INDEX ]; do
        SENSOR_VALUE=$(snmpwalk -v 1 -c $COMMUNITY $HOSTNAME .1.3.6.1.4.1.1588.2.1.1.1.1.22.1.4.$i | sed "s/.*INTEGER:\(.*\)$/\1/"| sed "s/ //g")
        SENSOR_STATUS=$(snmpwalk -v 1 -c $COMMUNITY $HOSTNAME .1.3.6.1.4.1.1588.2.1.1.1.1.22.1.3.$i | sed "s/.*INTEGER:\(.*\)$/\1/")
        SENSOR_INFO=$(snmpwalk -v 1 -c $COMMUNITY $HOSTNAME .1.3.6.1.4.1.1588.2.1.1.1.1.22.1.5.$i | sed "s/.*STRING:\(.*\)$/\1/" | sed "s/\"/\:/g" | sed "s/\://g"| sed "s/ //g")
        SENSOR_TYPE=$(snmpwalk -v 1 -c $COMMUNITY $HOSTNAME .1.3.6.1.4.1.1588.2.1.1.1.1.22.1.2.$i | sed "s/.*INTEGER:\(.*\)$/\1/")
        
        if [ $SENSOR_TYPE -eq 1 ]; then 
                SENSOR_TYPE="C"
        elif [ $SENSOR_TYPE -eq 2 ]; then
                SENSOR_TYPE="RPM"
        else
                SENSOR_TYPE=""
        fi


        case `echo $SENSOR_STATUS` in
                0) warn_array=( ${array[@]} ${SENSOR_INFO}=${SENSOR_VALUE}${SENSOR_TYPE}, "status=absent"  )
                   perfdata=( ${perfdata[@]}${SENSOR_VALUE}";" )
                ;;
                1) array=( ${array[@]} ${SENSOR_INFO}=${SENSOR_VALUE}${SENSOR_TYPE}, )
                   perfdata=( ${perfdata[@]}${SENSOR_VALUE}";" )
                ;;
                2) fault_array=( ${array[@]} ${SENSOR_INFO}=${SENSOR_VALUE}${SENSOR_TYPE}, "status=faulty" )
                   perfdata=( ${perfdata[@]}${SENSOR_VALUE}";" )
                ;;
                3) warn_array=( ${array[@]} ${SENSOR_INFO}=${SENSOR_VALUE}${SENSOR_TYPE}, "status=below-min" )
                   perfdata=( ${perfdata[@]}${SENSOR_VALUE}";" )  
                ;;
                4) array=( ${array[@]} ${SENSOR_INFO}=${SENSOR_VALUE}${SENSOR_TYPE}, )
                   perfdata=( ${perfdata[@]}${SENSOR_VALUE}";" )  
                ;;
                5) warn_array=( ${array[@]} ${SENSOR_INFO}=${SENSOR_VALUE}${SENSOR_TYPE}, "status=above-max" )
                   perfdata=( ${perfdata[@]}${SENSOR_VALUE}";" )
                ;;
# not all blades are populated, so we don't want to alert on this
#                6) fault_array=( ${array[@]} ${SENSOR_INFO}=${SENSOR_VALUE}${SENSOR_TYPE}, "status=absent"  )
#                   perfdata=( ${perfdata[@]}${SENSOR_VALUE}";" )
#                ;;
        esac
let $[ i += 1 ]
done



if [ ${#fault_array[@]} != 0 ] ; then
    echo "HARDWARE CRITICAL : "${fault_array[@]}"|"${perfdata[@]}
    exit $STATE_CRITICAL
elif [ ${#warn_array[@]} != 0 ] ; then
     echo "HARDWARE WARNING : "${warn_array[@]}"|"${perfdata[@]}  
     exit $STATE_CRITICAL
else
    echo "HARDWARE OK : "${array[@]}"|"${perfdata[@]}
    exit $STATE_OK
fi







