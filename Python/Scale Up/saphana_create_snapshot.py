import sys
import argparse
import paramiko
import re
import purestorage
from hdbcli import dbapi
from datetime import datetime

#Arguments
parser = argparse.ArgumentParser(description='Process the creation of an SAP \
    HANA application consistent storage snapshot')
parser.add_argument('-ha','--hostaddress', help='Host address(IP) or hostname of the\
     SAP HANA Scale Up System', default='localhost')
parser.add_argument('-i','--instancenumber', help='SAP HANA instance number , \
    typically in the form 00',  default=00)
parser.add_argument('-dn','--databasename', help='SAP HANA database or tenant name', \
    required=True)
parser.add_argument('-p','--port', help='SAP HANA port number , typically in the \
    form 15,41 taken from the final two digits of the port number', default=15)
parser.add_argument('-du','--databaseuser', help='SAP HANA database user with the \
    correct permissions to create a storage snapshot', required=True)
parser.add_argument('-dp','--databasepassword', help='SAP HANA database password \
    with the correct permissions to create a storage snapshot', required=True)
parser.add_argument('-osu','--operatingsystemuser', help='A user with the permissions \
    to freeze the SAP HANA data volume and view volume information', \
         required=True)
parser.add_argument('-osp','--operatingsystempassword', help='Password for the user \
    with permissions to freeze the SAP HANA data volume and view volume information'\
        , required=True)
parser.add_argument('-fa','--flasharray', help='The IP address or hostname of a Pure \
    Storage FlashArray with the SAP HANA systems volumes on it ', required=True)
parser.add_argument('-fau','--flasharrayuser', help='A user on the FlashArray with \
    permissions to create a volume snapshot', required=True)
parser.add_argument('-fap','--flasharraypassword', help='Password for the user with \
    permissions to create a volume snapshot on FlashArray', required=True)
parser.add_argument('-cc','--crashconsistent', action="store_false", default=None,\
     help='Create a crash consistent snapshot in a protection group',required=False)   
parser.add_argument('--version', action='version', version='%(prog)s 0.2')

args = parser.parse_args()

hostaddress = args.hostaddress
instancenumber = args.instancenumber
databasename = args.databasename
port = args.port
databaseuser = args.databaseuser
databasepassword = args.databasepassword
operatingsystemuser = args.operatingsystemuser
operatingsystempassword = args.operatingsystempassword
flasharray = args.flasharray
flasharrayuser = args.flasharrayuser
flasharraypassword = args.flasharraypassword
crashconsistent = args.crashconsistent

# hostaddress = ""
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
# crashconsistent = False


def check_pythonversion():
    if sys.version_info[0] < 3:
        print("Minimum version of python required to run this script is python 3")
        return False
    else:
        return True

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



def check_saphana_system_type():
    hdbsqlCheckSAPHANASystemType = "SELECT VALUE FROM M_INIFILE_CONTENTS WHERE FILE_NAME \
        = 'global.ini' AND SECTION = 'multidb' AND KEY = 'mode'"
    systemtype = execute_saphana_command(hdbsqlCheckSAPHANASystemType, port)
    if "multidb" in systemtype[0]:
        multidb = True
        return multidb
    else:
        multidb = False
        return multidb

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

def freeze_filesystem(volume_mount):
    sshclient = prepare_ssh_connection()
    get_volumemountpoint_command = "/sbin/fsfreeze --freeze" + str(volume_mount)
    stdin, stdout, stderr = sshclient.exec_command(get_volumemountpoint_command)
    opt = stdout.readlines()
    sshclient.close()

def unfreeze_filesystem(volume_mount):
    sshclient = prepare_ssh_connection()
    get_volumemountpoint_command = "/sbin/fsfreeze --unfreeze" + str(volume_mount)
    stdin, stdout, stderr = sshclient.exec_command(get_volumemountpoint_command)
    opt = stdout.readlines()
    sshclient.close()

def create_flasharray_volume_snapshot(serialnumber,snapshot_suffix):
    array = purestorage.FlashArray(flasharray,flasharrayuser, flasharraypassword,verify_https=False)
    volumes =  array.list_volumes()
    for key in volumes:
        volname = key.get("name")
        volserial = str(key.get("serial")).lower()
        found = volserial in serialnumber
        if found:
           snapshot_id = array.create_snapshot(volname, suffix=snapshot_suffix)
           snapserial = str(snapshot_id.get("serial"))
           return snapserial


def prepare_saphana_storage_snapshot():
    now = datetime.now()
    dt_string = now.strftime("%d/%m/%Y %H:%M:%S")
    hdbPrepareStorageSnapshot = "BACKUP DATA FOR FULL SYSTEM CREATE SNAPSHOT COMMENT \
        'SNAPSHOT-" + dt_string +"';"
    hdbRetrieveStorageSnapshotID = "SELECT BACKUP_ID, COMMENT FROM M_BACKUP_CATALOG \
        WHERE ENTRY_TYPE_NAME = 'data snapshot' AND STATE_NAME = 'prepared' AND COMMENT = 'SNAPSHOT-" + dt_string +"';"
    multidb = check_saphana_system_type()
    if multidb:
        execute_saphana_command(hdbPrepareStorageSnapshot, 13)
        saphana_snapshot_id = execute_saphana_command(hdbRetrieveStorageSnapshotID, 13)
    else:
        execute_saphana_command(hdbPrepareStorageSnapshot, port)
    saphana_snapshot_id = saphana_snapshot_id[0].column_values[0]
    return saphana_snapshot_id


def confirm_saphana_storage_snapshot(BackupID, EBID):
    hdbConfirmStorageSnapshot = "BACKUP DATA FOR FULL SYSTEM CLOSE SNAPSHOT BACKUP_ID " + \
        str(BackupID) + " SUCCESSFUL '" + "FlashArray Snapshot ID :" + str(EBID) + "';"
    multidb = check_saphana_system_type()
    if multidb:
        execute_saphana_command(hdbConfirmStorageSnapshot, 13)

    else:
        execute_saphana_command(hdbConfirmStorageSnapshot, port)


def abandon_saphana_storage_snapshot(BackupID, EBID):
    hdbAbandonStorageSnapshot = "BACKUP DATA FOR FULL SYSTEM CLOSE SNAPSHOT BACKUP_ID " \
        + str(BackupID) + " UNSUCCESSFUL '" + str(EBID) + "';"
    multidb = check_saphana_system_type()
    if multidb:
        execute_saphana_command(hdbAbandonStorageSnapshot, 13)

    else:
        execute_saphana_command(hdbAbandonStorageSnapshot, port)

def get_saphana_data_volume_mount():
    hdbGetHANADataVolumeMount = "SELECT VALUE FROM M_INIFILE_CONTENTS WHERE FILE_NAME = \
        'global.ini' AND SECTION = 'persistence' AND KEY = 'basepath_datavolumes'  AND VALUE NOT LIKE '$%'"
    data_volume = execute_saphana_command(hdbGetHANADataVolumeMount, port)
    data_volume = data_volume[0].column_values
    data_volume = str(data_volume[0]).replace("/" + databasename, "")
    return data_volume

def get_volume_name(serialno):
    array = purestorage.FlashArray(flasharray,flasharrayuser, flasharraypassword,verify_https=False)
    volumes =  array.list_volumes()
    for key in volumes:
        volname = key.get("name")
        volserial = str(key.get("serial")).lower()
        found = volserial in serialno
        if found:
            return volname
    return False

def get_persistence_volumes_location():
    hdbGetPersistenceVolumesLocation = "SELECT VALUE,KEY FROM M_INIFILE_CONTENTS WHERE FILE_NAME = 'global.ini' \
        AND SECTION = 'persistence' AND (KEY = 'basepath_datavolumes' OR KEY = 'basepath_logvolumes') \
        AND VALUE NOT LIKE '$%'"
    persistenceVolumes = execute_saphana_command(hdbGetPersistenceVolumesLocation, port)
    volumes = []
    for item in persistenceVolumes:
        mount = item.column_values[0]
        mount = str(mount).replace("/" + databasename, "")
        serialNumber = get_volume_serialno(mount)
        volname = get_volume_name(serialNumber)
        if (volname == False):
            raise NameError('The volume was not found on this array')
        else:
            volumedata = {'mountpoint': mount, 'serialnumber': serialNumber, 'volumename' : volname}
            volumes.append(volumedata)
    return volumes

def create_protection_group_snap(volumes):
    pgname = "SAPHANA-" + databasename + "-CrashConsistency"
    array = purestorage.FlashArray(flasharray,flasharrayuser, flasharraypassword,verify_https=False)
    try:
        pgroup = array.get_pgroup(pgname)
    except Exception:
        array.create_pgroup(pgname)
    for vol in volumes:
        protectiongroups = array.add_volume(vol.get('volumename'), pgname)
    pgsnap = array.create_pgroup_snapshot(pgname)
    return pgsnap

 
try:
    if(crashconsistent == False):
        data_volume = get_saphana_data_volume_mount()
        saphana_backup_id = prepare_saphana_storage_snapshot()
        freeze_filesystem(data_volume)
        volume_snapshot_id = create_flasharray_volume_snapshot(get_volume_serialno(data_volume), \
            "SAP-HANA-Backup-ID-" + str(saphana_backup_id))
        print("Volume Snapshot serial number : " + str(volume_snapshot_id))
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
           freeze_filesystem(volume.get('mountpoint'))
       snapname  = create_protection_group_snap(formattedvolumes)
       for volume in formattedvolumes:
           unfreeze_filesystem(volume.get('mountpoint'))
       print ("Crash consistent storage snapshot " + snapname.get('name') + " created")
except Exception as e:
    print(e)
    if saphana_backup_id is not None and crashconsistent == False:
        print("Abandoning storage snapshot with SAP HANA Backup ID : " + str(saphana_backup_id))
        abandon_saphana_storage_snapshot(saphana_backup_id, "no_value")

