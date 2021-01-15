##################################################################################################
#                                                                                                #
#    Pure Storage Inc. (2021) SAP HANA Data Snapshot recovery script for Scale Up deployments    #
#                Works with Red Hat Enterprise Linux and SUSE Enterprise Linux.                  #       
#                  Recovers from  application consistent storage snapshots                       # 
#                       for SAP HANA systems on Flasharray block storage                         #  
#                                                                                                #
##################################################################################################


import sys
import argparse
import paramiko
import re
import purestorage_custom
import time
from passwords import DB_Password, OS_Password, SID_Password, vCenter_Password, FlashArray_Password
from hdbcli import dbapi
from datetime import datetime
from vsphere import vsphere_get_vvol_disk_identifiers

#Arguments
parser = argparse.ArgumentParser(description='Process the recovery of an SAP \
#     HANA system from an application consistent storage snapshot')
parser.add_argument('-ha','--hostaddress', help='Host address(IP) or hostname of the\
     SAP HANA Scale Up System', default='localhost')
parser.add_argument('-i','--instancenumber', help='SAP HANA instance number , \
    typically in the form 00',  default='00')
parser.add_argument('-du','--databaseuser', help='SAP HANA system database user with the \
    correct permissions to create a storage snapshot', required=True)
parser.add_argument('-dp','--databasepassword', help='SAP HANA system database password \
    with the correct permissions to create a storage snapshot', 
    default=DB_Password.DEFAULT_DB_Password, type=DB_Password)
parser.add_argument('-osu','--operatingsystemuser', help='A user with the permissions \
    to freeze the SAP HANA data volume and view volume information', \
         required=True)
parser.add_argument('-osp','--operatingsystempassword', help='Password for the user \
    with permissions to freeze the SAP HANA data volume and view volume information'\
        , default=OS_Password.DEFAULT_OS_Password, type=OS_Password)
parser.add_argument('-fa','--flasharray', help='The IP address or hostname of a Pure \
    Storage FlashArray with the SAP HANA systems volumes on it ', required=True)
parser.add_argument('-fau','--flasharrayuser', help='A user on the FlashArray with \
    permissions to create a volume snapshot', required=True)
parser.add_argument('-fap','--flasharraypassword', help='Password for the user with \
    permissions to create a volume snapshot on FlashArray', required=False, 
    default=FlashArray_Password.DEFAULT_FlashArray_Password, type=FlashArray_Password)
parser.add_argument('-sp','--sidadmpassword',\
     help='<sid>adm password for the <sid>adm user ', 
     default=SID_Password.DEFAULT_DB_SID_Password, type=SID_Password)
parser.add_argument('-ov','--overwritevolume', action="store_true", default=None,\
     help='Overwrite the original SAP HANA volume with the snapshot',required=False) 
parser.add_argument('-vca','--vcenteraddress', help='The IP address or hostname of a vCenter \
    Server managing the SAP HANA VM ', required=False, default=None)
parser.add_argument('-vcu','--vcenteruser', help='The Username of a user for the vCenter\
    Server managing the SAP HANA VM ', default=None)
parser.add_argument('-vcp','--vcenterpassword', type=vCenter_Password, help='The Password of a user for the vCenter\
    Server managing the SAP HANA VM ', default=vCenter_Password.DEFAULT_vCenter_Password)
parser.add_argument('--version', action='version', version='%(prog)s 0.5')

args = parser.parse_args()

hostaddress = args.hostaddress
instancenumber = args.instancenumber
databaseuser = args.databaseuser
databasepassword = args.databasepassword.value
operatingsystemuser = args.operatingsystemuser
operatingsystempassword = args.operatingsystempassword.value
flasharray = args.flasharray
flasharrayuser = args.flasharrayuser
flasharraypassword = args.flasharraypassword.value
sidadmpassword = args.sidadmpassword.value
overwritevolume = args.overwritevolume
vcenteraddress = args.vcenteraddress
vcenteruser = args.vcenteruser
vcenterpassword = args.vcenterpassword.value

# hostaddress = ""
# instancenumber = ""
databasename = "SYSTEMDB"
port = "13"
# databaseuser = ""
# databasepassword = ""
# operatingsystemuser = ""
# operatingsystempassword = ""
# flasharray = ""
# flasharrayuser = ""
# flasharraypassword = ""
# vcenteraddress = ""
# vcenteruser = ""
# vcenterpassword = ""
# sidadmpassword = ""
# overwritevolume = False

# This method is responsible for ensuring that the version of Python be used is 3 or higher
def check_pythonversion():
    if sys.version_info[0] < 3:
        raise NameError('Minimum version of python required to run this operation is python 3')

# This method takes any SQL command for SAP HANA and sends it to the relevant service. 
# The port number is included to ensure connections are made to the SYSTEMDB
def execute_saphana_command(command, port_number):
    portvalue = "3" + str(instancenumber) + str(port_number)
    connection = dbapi.connect(address=hostaddress,
                port=portvalue,
                user=databaseuser,
                password=databasepassword)
    if(connection.isconnected):
        cursor = connection.cursor()
        cursor.execute(command)
        responses = list()
        if cursor.description is not None:
            for row in cursor:
                responses.append(row)
            return responses
        else:
            pass
    else:
            print("Database connection not possible")

# When the instance ID is required this method returnes the 3 character SID of the HANA platform
def get_saphana_instanceid():
    hdbsqlGetSAPHANAInstanceID = "SELECT VALUE from SYS.M_SYSTEM_OVERVIEW WHERE NAME = 'Instance ID'"
    instanceid =  execute_saphana_command(hdbsqlGetSAPHANAInstanceID,port)
    return instanceid

# When bash commands need to be run this method is triggered
def prepare_ssh_connection():
    sshclient = paramiko.SSHClient()
    sshclient.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    sshclient.connect(
        hostaddress,
        port=22,
        username=operatingsystemuser,
        password=operatingsystempassword
    )
    return sshclient

# When bash commands for the SID<adm> environment need to be run this method is triggered
def prepare_ssh_connection_sidadm(user):
    sshclient = paramiko.SSHClient()
    sshclient.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    sshclient.connect(
        hostaddress,
        port=22,
        username=user,
        password=sidadmpassword
    )
    return sshclient

# In order to match the volume presented to the operating system the serial number is identified from the mount point
# udev is queried to look at volume information
def get_volume_serialno(volume_mount):
    sshclient = prepare_ssh_connection()
    get_volumemountpoint_command = "df -h | grep " + str(volume_mount)
    stdin, stdout, stderr = sshclient.exec_command(get_volumemountpoint_command)
    opt = stdout.readlines()
    parsedvolume_location = re.search("([^[']\S+)",str(opt))
    get_volumeserialno_command = "udevadm info --query=all --name=" + \
        str(parsedvolume_location.group()) + " | grep DM_SERIAL"
    stdin, stdout, stderr = sshclient.exec_command(get_volumeserialno_command)
    opt = stdout.readlines()
    volumeserial_toparse = opt
    sshclient.close()
    volumeserial_toparse = re.split("=",str(volumeserial_toparse))
    volumeserial_toparse = volumeserial_toparse[1]
    volumeserial_toparse = re.split("\\\\",str(volumeserial_toparse))
    volumeserial = volumeserial_toparse[0]
    return volumeserial

# When and if the volume conforms to a non FlashArray world wide id (for example with VMware vvols) this method can be 
# used to retrieve the device mounted at the relevant location
def get_volume_device(volume_mount):
    sshclient = prepare_ssh_connection()
    get_volumemountpoint_command = "df -h | grep " + str(volume_mount)
    stdin, stdout, stderr = sshclient.exec_command(get_volumemountpoint_command)
    opt = stdout.readlines()
    parsed_device_location = re.search("([^[']\S*)",str(opt))
    parsed_device_location = parsed_device_location.group()
    return parsed_device_location

# SAP HANA keeps track of the data and log volumes , this method will query the platform to return the location of the log and data volumes 
# When using an application consistent data snapshot only the data volume is needed as the process will trigger a savepoint 
# Recovery will nullify all transaction logs 
def get_saphana_data_volume_mount():
    hdbGetHANADataVolumeMount = "SELECT VALUE FROM M_INIFILE_CONTENTS WHERE FILE_NAME = \
        'global.ini' AND SECTION = 'persistence' AND KEY = 'basepath_datavolumes'  AND VALUE NOT LIKE '$%'"
    data_volume = execute_saphana_command(hdbGetHANADataVolumeMount, port)
    instanceid = get_saphana_instanceid()
    data_volume = data_volume[0].column_values
    data_volume = str(data_volume[0]).replace("/" + str(instanceid[0].column_values[0]), "")
    return data_volume

# The backup catalog is used to decide which backup will be used. Only confirmed application consistent snapshots will be shown
def get_saphana_backup_catalog():
    hdbGetSAPHANABackupCatalog = "SELECT BACKUP_ID,UTC_START_TIME FROM SYS.M_BACKUP_CATALOG WHERE \
    ENTRY_TYPE_NAME = 'data snapshot' ORDER BY SYS_END_TIME desc"
    catalog = execute_saphana_command(hdbGetSAPHANABackupCatalog, port)
    catalogitems = []
    catalogcounter = 1
    for entry in catalog:
        catalogid = catalogcounter
        backupid = entry.column_values[0]
        date = entry.column_values[1]
        catalogentry = {'catalogid' : catalogid, 'backupid' : backupid , \
             'date' : date}
        catalogitems.append(catalogentry)
        catalogcounter+=1
    return catalogitems

# Before proceeding with any operations the storage snapshot needs to be verified to be on the FlashArray 
def check_storage_snapshot(backupid):
    array = purestorage_custom.FlashArray(flasharray,flasharrayuser, flasharraypassword,verify_https=False)
    volumes =  array.list_volumes()
    for key in volumes:
        volname = key.get("name")
        snaps =  array.get_volume(volname, snap=True)
        for snap in snaps:
            found = str(backupid) in snap.get("name")
            if found:
                return snap

# During the recovery process the instance needs to be fully stopped
def stop_saphana_instance(mount_point):
    sshclient = prepare_ssh_connection()
    shutdown_instance_string = "/usr/sap/hostctrl/exe/sapcontrol -nr " + instancenumber + \
        " -function Stop"
    get_instance_state_string = "/usr/sap/hostctrl/exe/sapcontrol -nr " + instancenumber + \
        " -function GetProcessList"
    umount_data_volume = "umount " + mount_point
    stdin, stdout, stderr = sshclient.exec_command(shutdown_instance_string)
    opt = stdout.readlines()
    running = True
    while(running):
        stdin, stdout, stderr = sshclient.exec_command(get_instance_state_string)
        check = stdout.readlines()
        checkval = "hdbdaemon, HDB Daemon, GRAY, Stopped"
        found = checkval in check[5]
        if(found):
            stdin, stdout, stderr = sshclient.exec_command(umount_data_volume)
            sshclient.close()
            running = False

# During recovery the volume will be overwritten with the storage snapshot 
# In a vvol scenario without multipathing it may be necessary to know where the volume needs to be mounted to
# This method will also handle remounting of the data volume after overwriting the volume 
def restore_overwrite_volume(snapshot, mount_point, backupid, serialno, virtual_disk, data_vol_mount_point,
    block_device):
    array = purestorage_custom.FlashArray(flasharray,flasharrayuser, flasharraypassword,verify_https=False)
    volumes =  array.list_volumes()
    new_volume = None
    if(virtual_disk):
        vm_disk_info = None
        if(vcenteraddress is not None and vcenteruser is not None and vcenterpassword is not None):
            vcenter_dict = {'address':vcenteraddress,'vc_user':vcenteruser,'vc_pass':vcenterpassword}
        else:
            raise NameError('The volume has been detected to be a virtual disk but no vCenter credentials \
                have been supplied to further parse the request')
        vm_disk_info = vsphere_get_vvol_disk_identifiers(serialno,vcenter_dict)
        if vm_disk_info is not None:
            volume = array.list_virtual_volume(vm_disk_info.get('backingObjectId'))
            if(volume.__len__() != 0):
                for attr in volume:
                    if(attr.get('key') == 'PURE_VVOL_ID'):
                        volname = attr.get('name')
                        vol = array.get_volume(volname)
                        vvolvolserial = vol.get('serial')
                        volumes =  array.list_volumes()
                        for key in volumes:
                            volname = key.get("name")
                            volserial = str(key.get("serial")).lower()
                            found = volserial.lower() in vvolvolserial.lower()
                            if found:
                                new_volume = array.copy_volume(snapshot.get("name"), volname, overwrite=True)
                                break
    else:
        for key in volumes:
            volname = key.get("name")
            volserial = str(key.get("serial")).lower()
            found = volserial in serialno 
            if(found):
                new_volume = array.copy_volume(snapshot.get("name"), volname, overwrite=True)
                break
        if(new_volume is None):
            raise NameError('There was an error location the source volume on the array')
    #operating system rescan for new device 
    sshclient = prepare_ssh_connection()
    rescan_scsi_bus_add_string = "sudo rescan-scsi-bus.sh -a"
    stdin, stdout, stderr = sshclient.exec_command(rescan_scsi_bus_add_string)
    time.sleep(30)
    opt = stdout.readlines()
    #mount new volume 
    device_mount_string = None
    if(data_vol_mount_point is not None and block_device is not None):
         device_mount_string = "mount " + block_device + " " + mount_point
    else:
        device_mount_string = "mount /dev/mapper/3624a9370" + new_volume.get("serial").lower() + " " + mount_point
    stdin, stdout, stderr = sshclient.exec_command(device_mount_string)
    time.sleep(30)
    sshclient.close()
    returned_serial_number = get_volume_serialno(mount_point)
    foundfinal = returned_serial_number in serialno
    if(foundfinal):
        return True
    else:
        return False

# During recovery the volume will be copied to a new volume and that volume mounted to the relevant mount point 
def restore_copyvolume(snapshot, mount_point, backupid, serialno):
    array = purestorage_custom.FlashArray(flasharray,flasharrayuser, flasharraypassword,verify_https=False)
    new_volume = array.copy_volume(snapshot.get("name"), snapshot.get("source") + "-" + str(backupid))
    hosts = array.list_hosts()
    for host in hosts:
        host_volumes = array.list_host_connections(host.get("name"))
        for hostvol in host_volumes:
            if(hostvol.get("vol") != 'pure-protocol-endpoint'):
                volume = array.get_volume(hostvol.get("vol"))
                found = str(volume.get("serial")).lower() in serialno
                if found:
                    #disconnect existing data volume from host 
                    array.disconnect_host(host.get("name"), volume.get("name"))
                    #operating system remove device maps
                    sshclient = prepare_ssh_connection()
                    rescan_scsi_bus_remove_string = "sudo rescan-scsi-bus.sh -r"
                    stdin, stdout, stderr = sshclient.exec_command(rescan_scsi_bus_remove_string)
                    time.sleep(30)
                    opt = stdout.readlines()
                    #connect new data volume to host
                    array.connect_host(host.get("name"), new_volume.get("name"))
                    #operating system rescan for new device 
                    rescan_scsi_bus_add_string = "sudo rescan-scsi-bus.sh -a"
                    stdin, stdout, stderr = sshclient.exec_command(rescan_scsi_bus_add_string)
                    time.sleep(30)
                    opt = stdout.readlines()
                    #mount new volume 
                    device_mount_string = "mount /dev/mapper/3624a9370" + new_volume.get("serial").lower() + " " + mount_point
                    stdin, stdout, stderr = sshclient.exec_command(device_mount_string)
                    time.sleep(30)
                    sshclient.close()
                    returned_serial_number = get_volume_serialno(mount_point)
                    foundfinal = str(new_volume.get("serial")).lower() in returned_serial_number
                    if(foundfinal):
                        return True
                    else:
                        return False
# Once each storage operation has been completed SAP HANA can be instructed to restore the System Database
def restore_systemdb(sid):
    sidadmuser = sid[0].column_values[0].lower() + "adm"
    sshclient = prepare_ssh_connection_sidadm(sidadmuser)
    recover_systemdb_string = "/usr/sap/" + sid[0].column_values[0] + "/HDB" + instancenumber + \
        "/HDBSettings.sh /usr/sap/" + sid[0].column_values[0] + "/HDB" + instancenumber + \
        "/exe/python_support/recoverSys.py --command=\"RECOVER DATA  USING SNAPSHOT  CLEAR LOG\""
    stdin, stdout, stderr = sshclient.exec_command(recover_systemdb_string)
    time.sleep(10)
    opt = stdout.readlines()
    sshclient.close()

# Before any proceeding operation can occur after recovering the system database the instance must be fully running
def check_running_instance():
    sshclient = prepare_ssh_connection()
    get_instance_state_string = "/usr/sap/hostctrl/exe/sapcontrol -nr " + instancenumber + \
        " -function GetProcessList"
    running = True
    while(running):
        stdin, stdout, stderr = sshclient.exec_command(get_instance_state_string)
        check = stdout.readlines()
        checkval = "hdbdaemon, HDB Daemon, GREEN, Running"
        found = checkval in check[5]
        if(found):
            sshclient.close()
            running = False

# For the final restore operation each tenant is retrieved before running the restore operation
def get_tenants_to_restore():
    hdb_get_tenants_to_restore = "SELECT DATABASE_NAME FROM M_DATABASES WHERE ACTIVE_STATUS = 'NO'"
    tenants = execute_saphana_command(hdb_get_tenants_to_restore, port)
    return tenants

try:
    check_pythonversion()
    data_volume = get_saphana_data_volume_mount()
    instanceid = get_saphana_instanceid()
    catalog = get_saphana_backup_catalog()
    restore_menu = True
    while(restore_menu):
        print(" ------------------------------------------------ ")
        print("|    SAP HANA Backup Catalog : Data Snapshots    |")
        print("|          Select a Catalog ID to restore        |")
        print(" ------------------------------------------------ ") 
        print(" -------------         ----------          ------")
        print("| Catalog ID |        | BackupID |        | Date |")
        print(" -------------         ----------          ------")

        for backups in catalog:
            catalogid = str(backups.get('catalogid'))
            backupid = str(backups.get('backupid'))
            date = str(backups.get('date'))
            print(str("      " + catalogid + "               " + str(backupid) + \
                "         " + str(date)))
        choice = input("Enter the catalog ID of the backup to restore --> ")
        for backups in catalog:
            if(backups.get('catalogid') == int(choice)):
                backupid = backups.get('backupid')
                snap = check_storage_snapshot(backups.get('backupid'))
                if(snap is not None):
                    print(" ------------------------------------------------ ")
                    print("|    Volume Snapshot is  present on the Array    |")
                    print(" ------------------------------------------------ ") 
                    print("")
                    serial_number = get_volume_serialno(data_volume)
                    # Check if the volume is a vdisk or a direct attached disk
                    virtual_disk = False
                    volume_device = None
                    vendor_string = serial_number[0 : 8]
                    # This is a disk directly attached to the host
                    if(vendor_string == '3624a937'):
                        virtual_disk = False
                    elif(vendor_string == '36000c29'):
                        virtual_disk = True
                        overwritevolume = True
                        volume_device = get_volume_device(data_volume)
                    print(" ------------------------------------------------ ")
                    print("|        This is a disruptive process!!!         |")
                    if(virtual_disk == True):
                        print("|      A virtual disk has been detected          |")
                        print("|    Recovery will overwrite existing volume     |")
                    print("| Do you want to proceed with the recovery ? y/n |")
                    print(" ------------------------------------------------ ") 
                    confirm_menu = True
                    while(confirm_menu):
                        choice2 = input("Continue ? -->: ")
                        if(choice2 == "y"):
                            print(" ------------------------------------------------ ")
                            print("|         Shutting down SAP HANA Instance        |")
                            print(" ------------------------------------------------ ")
                            stop_saphana_instance(data_volume)
                            restore_storage_sucess = False
                            if(overwritevolume == False):
                                print(" ------------------------------------------------ ")
                                print("|          Copying volume from snapshot          |")
                                print("|        Updating operating system storage       |")
                                print(" ------------------------------------------------ ") 
                                restore_storage_sucess = restore_copyvolume(snap, data_volume,\
                                    backupid, serial_number)
                            else:
                                print(" ------------------------------------------------ ")
                                print("|          Overwriting existing volume           |")
                                print("|        Updating operating system storage       |")
                                print(" ------------------------------------------------ ")
                                restore_storage_sucess = restore_overwrite_volume(snap, data_volume,\
                                    backupid, serial_number, virtual_disk, data_volume, volume_device)
                            if(restore_storage_sucess):
                                print(" ------------------------------------------------ ")
                                print("|                Restoring SystemDB              |")
                                print(" ------------------------------------------------ ") 
                                restore_systemdb(instanceid)
                                check_running_instance()
                                tenants_to_restore = get_tenants_to_restore()
                                for tenant in tenants_to_restore:
                                    hdbrestoreString = "RECOVER DATA FOR " + \
                                        tenant[0] + "  USING SNAPSHOT  CLEAR LOG"
                                    print(" ------------------------------------------------ ")
                                    print("|                Restoring Tenant " + tenant[0] + "            |")
                                    print(" ------------------------------------------------ ") 
                                    execute_saphana_command(hdbrestoreString, 13)
                                    confirm_menu = False
                                    restore_menu = False
                                print(" ------------------------------------------------ ")
                                print("|                 System Restored                |")
                                if(overwritevolume == False):
                                    print("|          Remember to update /etc/fstab         |")
                                print(" ------------------------------------------------ ")
                            else:
                                print(" ------------------------------------------------ ")
                                print("|              An Error has occured              |")
                                print("|          Continue manual recovery              |")
                                print(" ------------------------------------------------ ")
                                confirm_menu = False
                                restore_menu = False
                        elif(choice2 == "n"):
                            confirm_menu = False
                        else:
                            pass
                else:
                    print(" ------------------------------------------------ ")
                    print("|   Volume Snapshot is not present on the Array  |")
                    print(" ------------------------------------------------ ")
except Exception as e:
    print(e)

            