##################################################################################################
#                                                                                                #
#      Pure Storage Inc. (2021) SAP HANA Data Snapshot creation script for Scale Out deployments #
#            Works with Red Hat Enterprise Linux and SUSE Enterprise Linux.                      #       
#     Creates both crash consistent and application consistent storage snapshots for SAP HANA    # 
#                             systems on Flasharray block storage                                #  
#                                                                                                #
##################################################################################################

import sys
import argparse
import paramiko
import re
import purestorage_custom
from passwords import DB_Password, OS_Password, SID_Password, vCenter_Password, FlashArray_Password
from hdbcli import dbapi
from datetime import datetime
from vsphere import vsphere_get_vvol_disk_identifiers

#Arguments
parser = argparse.ArgumentParser(description='Process the creation of an SAP \
    HANA application consistent storage snapshot for a Scale Out deployment')
parser.add_argument('-ha','--hostaddress', help='Host address (hostname) of an SAP \
    HANA Scale Out worker', default='localhost')
parser.add_argument('-d','--domainname', help='Domain name of domain where SAP \
    HANA scale out nodes are located', required=True)
parser.add_argument('-i','--instancenumber', help='SAP HANA instance number , \
    typically in the form 00',  default='00')
parser.add_argument('-dn','--databasename', help='SAP HANA database or tenant name', \
    required=True)
parser.add_argument('-p','--port', help='SAP HANA port number , typically in the \
    form 15,41 taken from the final two digits of the port number', default=15)
parser.add_argument('-du','--databaseuser', help='SAP HANA database user with the \
    correct permissions to create a storage snapshot', required=True)
parser.add_argument('-dp','--databasepassword', help='SAP HANA database password \
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
parser.add_argument('-cc','--crashconsistent', action="store_false", default=None,\
     help='Create a crash consistent snapshot in a protection group',required=False) 
parser.add_argument('-ff','--freezefilesystem', action="store_false", default=None,\
     help='Freeze the filesystem to avoid any IO going to the volume',required=False)
parser.add_argument('-vca','--vcenteraddress', help='The IP address or hostname of a vCenter \
    Server managing the SAP HANA VM ', required=False, default=None)
parser.add_argument('-vcu','--vcenteruser', help='The Username of a user for the vCenter\
    Server managing the SAP HANA VM ', required=False, default=None)
parser.add_argument('-vcp','--vcenterpassword', type=vCenter_Password, help='The Password of a user for the vCenter\
    Server managing the SAP HANA VM ', default=vCenter_Password.DEFAULT_vCenter_Password)
parser.add_argument('--version', action='version', version='%(prog)s 0.4')

args = parser.parse_args()

hostaddress = args.hostaddress
domainname = args.domainname
instancenumber = args.instancenumber
databasename = args.databasename
port = args.port
databaseuser = args.databaseuser
databasepassword = args.databasepassword.value
operatingsystemuser = args.operatingsystemuser
operatingsystempassword = args.operatingsystempassword.value
flasharray = args.flasharray
flasharrayuser = args.flasharrayuser
flasharraypassword = args.flasharraypassword.value
crashconsistent = args.crashconsistent
freezefilesystem = args.freezefilesystem
vcenteraddress = args.vcenteraddress
vcenteruser = args.vcenteruser
vcenterpassword = args.vcenterpassword.value

# hostaddress = ""
# domainname = ""
# instancenumber = ""
# databasename = ""
# port = ""
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
# crashconsistent = False
# freezefilesystem = False

# This method is responsible for ensuring that the version of Python be used is 3 or higher
def check_pythonversion():
    if sys.version_info[0] < 3:
        raise NameError('Minimum version of python required to run this operation is python 3')

# This method takes any SQL command for SAP HANA and sends it to the relevant service. 
# The port number is included for legacy purposes with single container databases
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

# This method is responsible for checking the type of SAP HANA database being used 
# The two possible variants are a single tenant database(SDC) with no nameserver and a multi-tenant database (MDC)
def check_saphana_system_type():
    hdbsqlCheckSAPHANASystemType = "SELECT VALUE FROM M_INIFILE_CONTENTS WHERE \
        FILE_NAME = 'global.ini' AND SECTION = 'multidb' AND KEY = 'mode'"
    systemtype = execute_saphana_command(hdbsqlCheckSAPHANASystemType, port)
    if "multidb" in systemtype[0]:
        multidb = True
        return multidb
    else:
        multidb = False
        return multidb

# When bash commands need to be run this method is triggered
def prepare_ssh_connection(host):
    sshclient = paramiko.SSHClient()
    sshclient.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    sshclient.connect(
        host,
        port=22,
        username=operatingsystemuser,
        password=operatingsystempassword
    )
    return sshclient

# This method helps to identify the volume name 
# To create a block storage snapshot the volume name is used with the Pure Storage RESTFul API
def get_volume_serialno(host,volume_mount):
    sshclient = prepare_ssh_connection(host)
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

# If specific the filesystem can have IO frozen to ensure no further write operations occur while the snapshot is being taken
def freeze_filesystem(host,volume_mount):
    sshclient = prepare_ssh_connection(host)
    get_volumemountpoint_command = "sudo /sbin/fsfreeze --freeze" + str(volume_mount)
    stdin, stdout, stderr = sshclient.exec_command(get_volumemountpoint_command)
    opt = stdout.readlines()
    sshclient.close()

def unfreeze_filesystem(host,volume_mount):
    sshclient = prepare_ssh_connection(host)
    get_volumemountpoint_command = "sudo /sbin/fsfreeze --unfreeze" + str(volume_mount)
    stdin, stdout, stderr = sshclient.exec_command(get_volumemountpoint_command)
    opt = stdout.readlines()
    sshclient.close()

# This method takes the volume serial number , matches it against a volume on the selected flasharray and then takes a storage snapshot
# If the volume world wide ID string matches the VMware vendor string , then the vcenter credentials are used to check if vvols are being used
# VMFS based virtual disks are not supported - only vVols
def create_flasharray_volume_snapshot(serialnumber,snapshot_suffix):
    array = purestorage_custom.FlashArray(flasharray,flasharrayuser, flasharraypassword,verify_https=False)
    snapserial = None
    vendor_string = serialnumber[0 : 8]
    # This is a disk directly attached to the host
    if(vendor_string == '3624a937'):
        volumes =  array.list_volumes()
        for key in volumes:
            volname = key.get("name")
            volserial = str(key.get("serial")).lower()
            found = volserial.lower() in serialnumber.lower()
            if found:
                snapshot_id = array.create_snapshot(volname, suffix=snapshot_suffix)
                snapserial = str(snapshot_id.get("serial"))
                return snapserial
    elif(vendor_string == '36000c29'):
        # Then this is a VMware vdisk volume ,need to check if it is vvol based
        vm_disk_info = None
        if(vcenteraddress is not None and vcenteruser is not None and vcenterpassword is not None):
            vcenter_dict = {'address':vcenteraddress,'vc_user':vcenteruser,'vc_pass':vcenterpassword}
        else:
            raise NameError('The volume has been detected to be a virtual disk but no vCenter credentials have been supplied to further parse the request')
        vm_disk_info = vsphere_get_vvol_disk_identifiers(serialnumber,vcenter_dict)
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
                                snapshot_id = array.create_snapshot(volname, suffix=snapshot_suffix)
                                snapserial = str(snapshot_id.get("serial"))
                                return snapserial
    if(snapserial is None):
         raise NameError('The volume was not found on this array or this is not a supported volume for a data snapshot')

# The SAP HANA data snapshot must be prepared before taking a block volume snapshot , this sends the SQL command to the platform to do so. 
def prepare_saphana_storage_snapshot():
    now = datetime.now()
    dt_string = now.strftime("%d/%m/%Y %H:%M:%S")
    hdbPrepareStorageSnapshot = "BACKUP DATA FOR FULL SYSTEM CREATE SNAPSHOT COMMENT 'SNAPSHOT-" \
    + dt_string +"';"
    hdbRetrieveStorageSnapshotID = "SELECT BACKUP_ID, COMMENT FROM M_BACKUP_CATALOG WHERE \
        ENTRY_TYPE_NAME = 'data snapshot' AND STATE_NAME = 'prepared' AND COMMENT = 'SNAPSHOT-" + dt_string +"';"
    multidb = check_saphana_system_type()
    if multidb:
        execute_saphana_command(hdbPrepareStorageSnapshot, 13)
        saphana_snapshot_id = execute_saphana_command(hdbRetrieveStorageSnapshotID, 13)
    else:
        execute_saphana_command(hdbPrepareStorageSnapshot, port)
    saphana_snapshot_id = saphana_snapshot_id[0].column_values[0]
    return saphana_snapshot_id

# Once the block volume snapshot has been taken the storage snapshot must be confirmed , this includes the operation in the backup catalog
def confirm_saphana_storage_snapshot(BackupID, EBID):
    hdbConfirmStorageSnapshot = "BACKUP DATA FOR FULL SYSTEM CLOSE SNAPSHOT BACKUP_ID " \
    + str(BackupID) + " SUCCESSFUL '" + "FlashArray Snapshot ID :" + str(EBID) + "';"
    multidb = check_saphana_system_type()
    if multidb:
        execute_saphana_command(hdbConfirmStorageSnapshot, 13)

    else:
        execute_saphana_command(hdbConfirmStorageSnapshot, port)

# If anything goes wrong during the process this method is called to ensure the storage snapshot has not been successful. 
def abandon_saphana_storage_snapshot(BackupID, EBID):
    hdbAbandonStorageSnapshot = "BACKUP DATA FOR FULL SYSTEM CLOSE SNAPSHOT BACKUP_ID " \
    + str(BackupID) + " UNSUCCESSFUL '" + str(EBID) + "';"
    multidb = check_saphana_system_type()
    if multidb:
        execute_saphana_command(hdbAbandonStorageSnapshot, 13)

    else:
        execute_saphana_command(hdbAbandonStorageSnapshot, port)

# This method helps to identify the volume name 
# To create a block storage snapshot the volume name is used with the Pure Storage RESTFul API
# This method will use the vendor string to check if the volume is direct attached from the FlashArray 
# or if it is a VMware virtua disk
def get_volume_name(serialno):
    array = purestorage_custom.FlashArray(flasharray,flasharrayuser, flasharraypassword,verify_https=False)
    vendor_string = serialno[0 : 8]
    volname = None
    if(vendor_string == '3624a937'):
        volumes =  array.list_volumes()
        for key in volumes:
            volname = key.get("name")
            volserial = str(key.get("serial")).lower()
            found = volserial in serialno
            if found:
                return volname
    elif(vendor_string == '36000c29'):
             # Then this is a VMware vdisk volume ,need to check if it is vvol based
            vm_disk_info = None
            array = purestorage_custom.FlashArray(flasharray,flasharrayuser, flasharraypassword,verify_https=False)
            if(vcenteraddress is not None and vcenteruser is not None and vcenterpassword is not None):
                vcenter_dict = {'address':vcenteraddress,'vc_user':vcenteruser,'vc_pass':vcenterpassword}
            else:
                raise NameError('The volume has been detected to be a virtual disk but no vCenter credentials have been supplied to further parse the request')
            vm_disk_info = vsphere_get_vvol_disk_identifiers(serialno,vcenter_dict)
            if vm_disk_info is not None:
                volume = array.list_virtual_volume(vm_disk_info.get('backingObjectId'))
                if(volume.__len__() != 0):
                    for attr in volume:
                        if(attr.get('key') == 'PURE_VVOL_ID'):
                            volname = attr.get('name')
                            vol = array.get_volume(volname)
                            vvolvolserial = vol.get('serial')
                            volumes_toparse =  array.list_volumes()
                            for key in volumes_toparse:
                                thisvolname = key.get("name")
                                thisvolserial = str(key.get("serial")).lower()
                                found = thisvolserial.lower() in vvolvolserial.lower()
                                if found:
                                    volname = thisvolname
                                    return volname
    return volname

# SAP HANA keeps track of the data volumes , this method will query the platform to return the location of the data volumes 
# When using an application consistent data snapshot only the data volume is needed as the process will trigger a savepoint 
# Recovery will nullify all transaction logs 
def get_saphana_data_volume_and_hosts():
    hdbGetHANADataVolumeAndHosts = "SELECT HOST, STORAGE_ID, PATH, KEY, VALUE FROM SYS.M_ATTACHED_STORAGES WHERE KEY = \
    'WWID' AND PATH LIKE (SELECT CONCAT(VALUE,'%') FROM M_INIFILE_CONTENTS WHERE FILE_NAME = 'global.ini' AND SECTION = \
    'persistence' AND KEY = 'basepath_datavolumes' AND VALUE NOT LIKE '$%')"
    multidb = check_saphana_system_type()
    if multidb:
        global hostaddress 
        hostaddress = get_saphana_nameserver_host() + "." +  domainname
        hosts_data_volumes = execute_saphana_command(hdbGetHANADataVolumeAndHosts,13)
    else:
        hosts_data_volumes = execute_saphana_command(hdbGetHANADataVolumeAndHosts, port)
    return hosts_data_volumes

# In a scale out environment the nameserver needs to be identified as that is where the SystemDB runs
def get_saphana_nameserver_host():
    hdbGetNameServerhost = "SELECT HOST FROM SYS.M_SERVICES WHERE DETAIL = 'master' AND SERVICE_NAME = 'nameserver'"
    nameserver_host = execute_saphana_command(hdbGetNameServerhost, port)
    nameserver_host = nameserver_host[0].column_values[0]
    return nameserver_host

# SAP HANA keeps track of the data and log volumes , this method will query the platform to return the location of the log and data volumes 
# When using a crash consistent storage snapshot both the data and log volumes are required
def get_persistence_volumes_location():
    hdbGetPersistenceDataVolumesLocation = "SELECT HOST, STORAGE_ID, PATH, KEY, VALUE FROM SYS.M_ATTACHED_STORAGES \
                WHERE KEY = 'WWID' AND PATH LIKE (SELECT CONCAT(VALUE,'%') FROM M_INIFILE_CONTENTS WHERE FILE_NAME \
                = 'global.ini' AND SECTION = 'persistence' AND KEY = 'basepath_datavolumes' AND VALUE NOT LIKE '$%')"
    hdbGetPersistenceLogVolumesLocation = "SELECT HOST, STORAGE_ID, PATH, KEY, VALUE FROM SYS.M_ATTACHED_STORAGES \
                WHERE KEY = 'WWID' AND PATH LIKE (SELECT CONCAT(VALUE,'%') FROM M_INIFILE_CONTENTS WHERE FILE_NAME\
                = 'global.ini' AND SECTION = 'persistence' AND KEY = 'basepath_logvolumes' AND VALUE NOT LIKE '$%')"
    persistenceDataVolumes = execute_saphana_command(hdbGetPersistenceDataVolumesLocation, port)
    persistenceLogVolumes = execute_saphana_command(hdbGetPersistenceLogVolumesLocation, port)
    volumes = []
    for item in persistenceDataVolumes:
        mount = item.column_values[2]
        serialNumber = get_volume_serialno(item.column_values[0],mount)
        volname = get_volume_name(serialNumber)
        if (volname == None):
            raise NameError('The volume was not found on this array')
        else:
            volumedata = {'host' : item[0], 'mountpoint': mount, \
            'serialnumber': serialNumber, 'volumename' : volname}
            volumes.append(volumedata)
    for item in persistenceLogVolumes:
        mount = item.column_values[2]
        serialNumber = get_volume_serialno(item.column_values[0],mount)
        volname = get_volume_name(serialNumber)
        if (volname == False):
            raise NameError('The volume was not found on this array')
        else:
            volumedata = {'host' : item[0], 'mountpoint': mount, \
            'serialnumber': serialNumber, 'volumename' : volname}
            volumes.append(volumedata)
    return volumes

# If using crash consistency then the volumes are added to a protection group and a protection group snap is created
def create_protection_group_snap(volumes):
    pgname = "SAPHANA-" + databasename + "-CrashConsistency"
    array = purestorage_custom.FlashArray(flasharray,flasharrayuser, flasharraypassword,verify_https=False)
    try:
        pgroup = array.get_pgroup(pgname)
    except Exception:
        array.create_pgroup(pgname)
    for vol in volumes:
        protectiongroups = array.add_volume(vol.get('volumename'), pgname)
    pgsnap = array.create_pgroup_snapshot(pgname)
    return pgsnap


# This is the equivalent of the "Main" method where execution is run
try:
    if(crashconsistent == False):
        hosts_and_vols = get_saphana_data_volume_and_hosts()
        saphana_backup_id = prepare_saphana_storage_snapshot()
        volume_snapshot_id = ""
        for h_v in hosts_and_vols:
            host = h_v.column_values[0] + "."  + domainname
            mount_point = h_v.column_values[2]
            if(freezefilesystem == True):
                freeze_filesystem(host, mount_point)
            mount_point_parse = mount_point.replace('/',"")
            vol_snap_suffix = "SAPHANA-" + h_v.column_values[0] + "-" + mount_point_parse + "-"  + str(saphana_backup_id)
            print("Creating storage snapshot for mount point : " + mount_point_parse + " on host : " + host)
            volume_snapshot_id = volume_snapshot_id + "-" + vol_snap_suffix + "-" + \
            create_flasharray_volume_snapshot(get_volume_serialno(host, mount_point),vol_snap_suffix)
            if(freezefilesystem == True):
                unfreeze_filesystem(host, mount_point)
        if saphana_backup_id is not None and volume_snapshot_id is not None:
            print("Confirming storage snapshot with SAP HANA Backup ID : " + str(saphana_backup_id))
            confirm_saphana_storage_snapshot(saphana_backup_id, volume_snapshot_id)
        else:
            print("Abandoning storage snapshot with SAP HANA Backup ID : " + str(saphana_backup_id))
            abandon_saphana_storage_snapshot(saphana_backup_id, "no_value")
    else:
        formattedvolumes = get_persistence_volumes_location()
        for volume in formattedvolumes:
            if(freezefilesystem == True):
                freeze_filesystem(volume.get('host'),volume.get('mountpoint'))
        snapname = create_protection_group_snap(formattedvolumes)
        for volume in formattedvolumes:
            if(freezefilesystem == True):
                unfreeze_filesystem(volume.get('host'),volume.get('mountpoint'))
        print ("Crash consistent storage snapshot " + snapname.get('name') + " created")
except Exception as e:
    print(e)
    if(crashconsistent == False):
        if saphana_backup_id is not None and crashconsistent == False:
            try:
                print("Abandoning storage snapshot with SAP HANA Backup ID : " + str(saphana_backup_id))
                abandon_saphana_storage_snapshot(saphana_backup_id, "no_value")
            except Exception as e:
                print(e)
    
