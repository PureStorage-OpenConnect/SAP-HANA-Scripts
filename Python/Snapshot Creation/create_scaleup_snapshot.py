##################################################################################################
#                                                                                                #
#      Pure Storage Inc. (2021) SAP HANA Data Snapshot creation script for Scale Up deployments  #
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
    HANA application consistent storage snapshot for a Scale Up deployment')
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
parser.add_argument('-cc','--crashconsistent', action="store_true",\
     help='Create a crash consistent snapshot in a protection group',required=False)
parser.add_argument('-ff','--freezefilesystem', action="store_true",\
     help='Freeze the filesystem to avoid any IO going to the volume',required=False)  
parser.add_argument('-vca','--vcenteraddress', help='The IP address or hostname of a vCenter \
    Server managing the SAP HANA VM ', required=False, default=None)
parser.add_argument('-vcu','--vcenteruser', help='The Username of a user for the vCenter\
    Server managing the SAP HANA VM ', required=False, default=None)
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
crashconsistent = args.crashconsistent
freezefilesystem = args.freezefilesystem
vcenteraddress = args.vcenteraddress
vcenteruser = args.vcenteruser
vcenterpassword = args.vcenterpassword.value

# hostaddress = "l"
# instancenumber = """
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
# crashconsistent = False
# freezefilesystem = False

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
    instanceid = instanceid[0].column_values[0]
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

# If specific the filesystem can have IO frozen to ensure no further write operations occur while the snapshot is being taken
def freeze_filesystem(volume_mount):
    sshclient = prepare_ssh_connection()
    get_volumemountpoint_command = "sudo /sbin/fsfreeze --freeze" + str(volume_mount)
    stdin, stdout, stderr = sshclient.exec_command(get_volumemountpoint_command)
    opt = stdout.readlines()
    sshclient.close()
# If specific the filesystem can have IO unforzen to ensure write operations can continue. Only used if the filesystem is frozen first
def unfreeze_filesystem(volume_mount):
    sshclient = prepare_ssh_connection()
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
    execute_saphana_command(hdbPrepareStorageSnapshot, port)
    saphana_snapshot_id = execute_saphana_command(hdbRetrieveStorageSnapshotID, port)
    saphana_snapshot_id = saphana_snapshot_id[0].column_values[0]
    return saphana_snapshot_id

# Once the block volume snapshot has been taken the storage snapshot must be confirmed , this includes the operation in the backup catalog
def confirm_saphana_storage_snapshot(BackupID, EBID):
    hdbConfirmStorageSnapshot = "BACKUP DATA FOR FULL SYSTEM CLOSE SNAPSHOT BACKUP_ID " + \
        str(BackupID) + " SUCCESSFUL '" + "FlashArray Snapshot ID :" + str(EBID) + "';"
    execute_saphana_command(hdbConfirmStorageSnapshot, port)

# If anything goes wrong during the process this method is called to ensure the storage snapshot has not been successful. 
def abandon_saphana_storage_snapshot(BackupID, EBID):
    hdbAbandonStorageSnapshot = "BACKUP DATA FOR FULL SYSTEM CLOSE SNAPSHOT BACKUP_ID " \
        + str(BackupID) + " UNSUCCESSFUL '" + str(EBID) + "';"
    execute_saphana_command(hdbAbandonStorageSnapshot, port)

# SAP HANA keeps track of the data volumes , this method will query the platform to return the location of the data volumes 
# When using an application consistent data snapshot only the data volume is needed as the process will trigger a savepoint 
# Recovery will nullify all transaction logs 
def get_saphana_data_volume_mount():
    hdbGetHANADataVolumeMount = "SELECT VALUE FROM M_INIFILE_CONTENTS WHERE FILE_NAME = \
        'global.ini' AND SECTION = 'persistence' AND KEY = 'basepath_datavolumes'  AND VALUE NOT LIKE '$%'"
    data_volume = execute_saphana_command(hdbGetHANADataVolumeMount, port)
    instanceid = get_saphana_instanceid()
    data_volume = data_volume[0].column_values
    data_volume = str(data_volume[0]).replace("/" + instanceid, "")
    return data_volume

# This method helps to identify the volume name 
# To create a block storage snapshot the volume name is used with the Pure Storage RESTFul API
def get_volume_name(serialno):
    array = purestorage_custom.FlashArray(flasharray,flasharrayuser, flasharraypassword,verify_https=False)
    volumes =  array.list_volumes()
    for key in volumes:
        volname = key.get("name")
        volserial = str(key.get("serial")).lower()
        found = volserial in serialno
        if found:
            return volname
    return False

# SAP HANA keeps track of the data and log volumes , this method will query the platform to return the location of the log and data volumes 
# When using a crash consistent storage snapshot both the data and log volumes are required
def get_persistence_volumes_location():
    hdbGetPersistenceVolumesLocation = "SELECT VALUE,KEY FROM M_INIFILE_CONTENTS WHERE FILE_NAME = 'global.ini' \
        AND SECTION = 'persistence' AND (KEY = 'basepath_datavolumes' OR KEY = 'basepath_logvolumes') \
        AND VALUE NOT LIKE '$%'"
    persistenceVolumes = execute_saphana_command(hdbGetPersistenceVolumesLocation, port)
    instanceid = get_saphana_instanceid()
    volumes = []
    for item in persistenceVolumes:
        mount = item.column_values[0]
        mount = str(mount).replace("/" + instanceid, "")
        serialNumber = get_volume_serialno(mount)
        vendor_string = serialNumber[0 : 8]
        volname = None
        if(vendor_string == '3624a937'):
            # This is a direct attached volume 
            volname = get_volume_name(serialNumber)
        elif(vendor_string == '36000c29'):
            # Then this is a VMware vdisk volume ,need to check if it is vvol based
            vm_disk_info = None
            array = purestorage_custom.FlashArray(flasharray,flasharrayuser, flasharraypassword,verify_https=False)
            if(vcenteraddress is not None and vcenteruser is not None and vcenterpassword is not None):
                vcenter_dict = {'address':vcenteraddress,'vc_user':vcenteruser,'vc_pass':vcenterpassword}
            else:
                raise NameError('The volume has been detected to be a virtual disk but no vCenter credentials have been supplied to further parse the request')
            vm_disk_info = vsphere_get_vvol_disk_identifiers(serialNumber,vcenter_dict)
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
        if (volname == None):
            raise NameError('The volume was not found on this array or this is not a supported volume for a data snapshot')
        else:
            volumedata = {'mountpoint': mount, 'serialnumber': serialNumber, 'volumename' : volname}
            volumes.append(volumedata)
    return volumes

# If using crash consistency then the volumes are added to a protection group and a protection group snap is created
def create_protection_group_snap(volumes):
    instanceid = get_saphana_instanceid()
    pgname = "SAPHANA-" + instanceid + "-CrashConsistency"
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
    check_pythonversion()
    if(crashconsistent == False):
        data_volume = get_saphana_data_volume_mount()
        saphana_backup_id = prepare_saphana_storage_snapshot()
        if(freezefilesystem == True):
            freeze_filesystem(data_volume)
        volume_snapshot_id = create_flasharray_volume_snapshot(get_volume_serialno(data_volume), \
             "SAPHANA-" + str(saphana_backup_id))
        print("Volume Snapshot serial number : " + str(volume_snapshot_id))
        if(freezefilesystem == True):
            unfreeze_filesystem(data_volume)
        if saphana_backup_id is not None and volume_snapshot_id is not None:
            print("Confirming storage snapshot with SAP HANA Backup ID : " + str(saphana_backup_id))
            confirm_saphana_storage_snapshot(saphana_backup_id, volume_snapshot_id)
        else:
            print("Abandoning storage snapshot with SAP HANA Backup ID : " + str(saphana_backup_id))
            abandon_saphana_storage_snapshot(saphana_backup_id, "no_value")
    else:
       formattedvolumes =  get_persistence_volumes_location()
       for volume in formattedvolumes:
            if(freezefilesystem == True):
                freeze_filesystem(volume.get('mountpoint'))
       snapname  = create_protection_group_snap(formattedvolumes)
       for volume in formattedvolumes:
            if(freezefilesystem == True):
                unfreeze_filesystem(volume.get('mountpoint'))
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

