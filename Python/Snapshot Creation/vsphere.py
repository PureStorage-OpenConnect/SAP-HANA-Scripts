##################################################################################################
#                                                                                                #
#                       Pure Storage Inc. (2021) vSphere helper module                           #
#  Helps to identify a volume on FlashArray for which a virtual machine is using vVol storage    #  
#                                                                                                #
##################################################################################################

import requests
import urllib3
from pyVmomi import vim 
from pyVim.connect import SmartConnect, Disconnect
import ssl

# This method logs into the vCenter server and traverses the resource tree looking for objects with the attribute 
# "backing" to match that attribute against the serial number presented to the operating system
def vsphere_get_vvol_disk_identifiers(serialno, vcenter):
    requests.packages.urllib3.disable_warnings()
    context = ssl._create_unverified_context()

    si = SmartConnect(host=vcenter.get('address'),
                    port=443,
                    user=vcenter.get('vc_user'),
                    pwd=vcenter.get('vc_pass'),
                    sslContext=context)

    client = si.RetrieveContent()

    global vmmuuidlist 
    vmmuuidlist = []
    for child in client.rootFolder.childEntity:
      if hasattr(child, 'vmFolder'):
         datacenter = child
         vmFolder = datacenter.vmFolder
         vmList = vmFolder.childEntity
         for vm in vmList:
             PrintVmInfo(vm)   

    for uuid in vmmuuidlist:
        vm = client.searchIndex.FindByUuid(uuid=uuid, vmSearch=True)
        config = vm.config.hardware.device
        for conf in config:
             if hasattr(conf, 'backing'):
                 if hasattr(conf.backing, 'uuid'):
                    formatteduuid = ("3" + str((conf.backing.uuid).replace("-",""))).lower()
                    #print('comparing ' + serialno + ' with ' + formatteduuid)
                    if serialno == formatteduuid:
                        if hasattr(conf.backing, 'backingObjectId'):
                            vm_storage_properties = {'uuid':conf.backing.uuid, 'backingObjectId':conf.backing.backingObjectId}
                            return vm_storage_properties
                            #break

# This is a helper method that attempts to keep track of where in the vCenter resourse tree (or folder) that the method is
def PrintVmInfo(vm, depth=1):
    """
    Print information for a particular virtual machine or recurse into a folder
    or vApp with depth protection
    """
    maxdepth = 10
    # if this is a group it will have children. if it does, recurse into them
    # and then return
    if hasattr(vm, 'childEntity'):
        if depth > maxdepth:
            return
        vmList = vm.childEntity
        for c in vmList:
            PrintVmInfo(c, depth+1)
        return 

    # if this is a vApp, it likely contains child VMs
    # (vApps can nest vApps, but it is hardly a common usecase, so ignore that)
    if isinstance(vm, vim.VirtualApp):
        vmList = vm.vm
        for c in vmList:
            PrintVmInfo(c, depth + 1)
        return 
    summary = vm.summary
    uuid = summary.config.uuid 
    vmmuuidlist.append(uuid)