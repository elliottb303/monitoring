#!/usr/bin/env python
#8/15/2012
###########################################
# Check local NFS mounts for correct setup in mtab / fstab,
# and check all for any hangs by using threaded approach
# intended to be used as Nagios plugin

#Return codes:
# CRITICAL 2
# WARNING 1
# OK 0


#usage:
# ./check_nfs24.py

################################

import subprocess
import threading
import os, sys
from time import sleep

FSTABERR=False
NOTMOUNTEDERR=False
NFSHANGERR=False
HUNGMOUNTLIST = []
NOTINFSTAB = []
NOTMOUNTED = []
QUICKWAIT = 4
EXTENDEDWAIT=16

# Function to check if df hangs ; adding mountpoint for each call
def df(mountpoint):     
    os.system("df -h " + mountpoint + " > /dev/null")

# Thread class that initiates with mountpoint and spawns child df check
# waits TIMEOUT secs for child df call process before completing 
class parallelcheck(threading.Thread):   

    def __init__ ( self, mountpoint ):
        self.mountpoint = mountpoint
        threading.Thread.__init__ ( self )
    
    def run ( self ):        
        global NFSHANGERR
        global HUNGMOUNTLIST
        
        #different way of calling the thread - inline call for child df call            
        t = threading.Thread(target=df, args = (self.mountpoint,))
        t.setDaemon(True)
        t.start()
        #Most df call should complete within 4 seconds
        sleep(QUICKWAIT)
        
        # if still alive give extended wait then mark as a hung mount  
        if t.isAlive():
            sleep(EXTENDEDWAIT)
            if t.isAlive():
                NFSHANGERR = True
                HUNGMOUNTLIST.append(self.mountpoint) 

#  ------------- Loop through fstab and find real NFS mounts to check  ------------
# If one is found loop for matching mtab entry
def hungcheck():
    #array to hold pool of threads
    nfsmounts = []
    #set mountpoint to default for case of missing mounts (shouldn't happen and will not result in hang)     
    mountpoint = "/dev/sda1"
    #open mtab into a array for later use
    f = open("/etc/mtab")
    mtab = []
    for line in f:
        mtab.append(line)
    f.close()
        
    fstab_content=open('/etc/fstab','r')
    for line in fstab_content:
        if '#' not in line and len(line) > 2 and 'nfs' in line:
            (fstabfs,fstabmountpt,fstabtype,fstaboptions,fstabdump,fstabpass)=line.strip().split()
            for line in mtab:
                ((procfs,procmountpt,proctype,procoptions,procdump,procpass))=line.strip().split()
                if fstabtype == 'nfs' and proctype == 'nfs':

                    if fstabmountpt == procmountpt:
                        mountpoint = procmountpt
            #start each fstab nfs entry hung mount check as a thread
            nfsmounts.append(parallelcheck(mountpoint))
    fstab_content.close()
            
    for thread in nfsmounts:
        #thread.setDaemon(True)
        thread.start()
        
    #wait each line check to complete
    for thread in nfsmounts:
        thread.join()

#  ------------ Loop through mtab/fstab and look for differences -----------
def diffcheck():
    global NOTMOUNTEDERR
    global FSTABERR
    global NOTMOUNTED
    global NOTINFSTAB
    
    MOUNTED=False
    
    #          ------- Run for NOT MOUNTED issue -------------
    #open mtab into a array for later use
    m = open("/etc/mtab")
    mtab = []
    for line in m:
        mtab.append(line)
    m.close()
        
    fstab_content=open('/etc/fstab','r')
    for line in fstab_content:
        if '#' not in line and len(line) > 2 and 'nfs' in line:
            (fstabfs,fstabmountpt,fstabtype,fstaboptions,fstabdump,fstabpass)=line.strip().split()
            for line in mtab:
                ((mtabfs,mtabmountpt,mtabtype,mtaboptions,mtabdump,mtabpass))=line.strip().split()
                if fstabtype == 'nfs' and mtabtype == 'nfs':

                    if fstabmountpt == mtabmountpt:
                        MOUNTED=True
            if not MOUNTED:
                NOTMOUNTEDERR=True
                NOTMOUNTED.append(fstabmountpt)
                #print "found an mtab discrpancy"
                #return 1
            MOUNTED = False
    fstab_content.close()
    
    #  --------- Run for not entered in FSTAB ------------------        
    #open fstab into a array for later use
    f = open("/etc/fstab")
    fstab = []
    for line in f:
        fstab.append(line)
    f.close()
        
    mtab_content=open('/etc/mtab','r')
    for line in mtab_content:
        #look for NFS mounts, skipping nfsd and sunrpc
        if 'nfs' in line and 'nfsd' not in line and 'sunrpc' not in line:
            (mtabfs,mtabmountpt,mtabtype,mtaboptions,mtabdump,mtabpass)=line.strip().split()
            for line in fstab:
                if '#' not in line and len(line) > 2 and 'nfs' in line:
                    ((fstabfs,fstabmountpt,fstabtype,fstaboptions,fstabdump,fstabpass))=line.strip().split()
                    if mtabtype == 'nfs' and fstabtype == 'nfs':
                        if mtabmountpt == fstabmountpt:
                            MOUNTED=True
            if not MOUNTED:
                FSTABERR=True
                NOTINFSTAB.append(mtabmountpt)
                #print "found an mtab discrpancy"
                #return 1
            MOUNTED = False
    mtab_content.close()
            
if __name__ == '__main__':
    
    #check for hung mounts; critical if so a list hung mounts
    hungcheck()
    if NFSHANGERR:
        print "CRITICAL: Hung NFS mount: " + str(HUNGMOUNTLIST[0:]) + " detected"
        sys.exit(2)
    
    #check to see if there are differences in the mountpoints; warn if so
    diffcheck()
    if NOTMOUNTEDERR and not FSTABERR:
        print "WARN: No mount for" + str(NOTMOUNTED[0:]) + " FSTAB entry (ies)" 
        sys.exit(1) 
    if FSTABERR and not NOTMOUNTEDERR:
        print "WARN: No entry in FSTAB for mount" + str(NOTINFSTAB[0:]) + "; currently mounted"
        sys.exit(1)
    if NOTMOUNTEDERR and FSTABERR:
        print "WARN: No mount for" + str(NOTMOUNTED[0:]) + "; not in FSTAB: " + str(NOTINFSTAB[0:]) 
        sys.exit(1)   
    
    print "OK: No NFS mount problems"
    sys.exit(0)

