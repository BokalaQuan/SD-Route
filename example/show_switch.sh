#!/bin/sh
# brief: command file for openvswitch in
#        virtual network(vnet)
#
# author: warcyzhu
# time:   Mar 02 2015

########## function define ##########################################
switchCmdTable() {
	sudo ovs-ofctl $ofMask dump-flows $switchCode
	#case $switchCode in
	#"s1")
	#	sudo ovs-ofctl $ofMask dump-flows s1
	#;;
	
	#"s2")
	#	ovs-ofctl $ofMask dump-flows s2
	#;;
	
	
	#*)
	#echo "please select pre-define topo name like \"s1\"."
	#	;;
	#esac
}

ofSetup() {
	if [ "$ofCode" = "of13" ]; then
		ofMask="-O OpenFlow13"		
	elif [ "$ofCode" = "of10" ]; then
		ofMask=""
	else
		ofMask="-O OpenFlow13"
	fi
}

brief()	{
	echo "Choose a switch and protocol(default with OpenFlow 1.3)"
	echo "such as:"
	echo "./show_switch.sh s1"
	echo "./show_switch.sh s1 of13"
	echo
}

######### command start #############################################
switchCode=0

brief
#read switchCode
switchCode=$1
ofCode="$2"

ofSetup
switchCmdTable

