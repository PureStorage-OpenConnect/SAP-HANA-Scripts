# SAP-HANA-Scripts

This repository is a collection of scripts aimed at automating storage functions with Pure Storage FlashArray and SAP HANA.

The following functionality can be achieved with the latest versions of these scripts :

- Create application consistent storage snapshots for SAP HANA systems on FlashArray
- Create crash consistent storage snapshots for SAP HANA systems on FlashArray
- Recover from application consistent data snapshots for SAP HANA Scale Up systems on FlashArray 

SAP HANA systems deployed on VMware , using virtual volumes (vVols) can have application consistent storage snapshots created (Scale Up and Scale Out) and recovered(Scale Up only) from when using the PowerShell scripts. 

If a user other than root is specified to be used for connections to the operation system , then the following needs to be added using visudo -
     <user> ALL=NOPASSWD: /sbin/fsfreeze,/usr/bin/rescan-scsi-bus.sh 

## PowerShell Scripts 

**Create an application consistent storage snapshot for Scale Up systems** 

A volume snapshot is only created for the SAP HANA data volume. Log backups are used to roll the database forward during the recovery process. See [blog post](https://www.andrewsillifant.com/new-sap-hana-scripts-for-automating-storage-operations/) for more details.

<u>Location</u> - Powershell/Scale Up/New-StorageSnapshot.ps1

`New-StorageSnapshot -HostAddress <IP address of host> -InstanceNumber <InstanceNumber (00)> -DatabaseName <Database Name (HN1)> -DatabaseUser <DBUser> -OperatingSystemUser <OS-User> -PureFlashArrayAddress <Pure FlashArray IP or hostname> -PureFlashArrayUser <pure FA User> -DatabasePort <Port> `

**Create a crash consistent storage snapshot for Scale Up systems** 

A volume snapshot is created for both the data and log volumes for the SAP HANA Scale Up system.

<u>Location</u> - Powershell/Scale Up/New-StorageSnapshot.ps1

`New-StorageSnapshot -HostAddress <IP address of host> -InstanceNumber <Instance Number (00)> -DatabaseName <Database Name (HN1)> -DatabaseUser <DBUser> -OperatingSystemUser <OS-User> -PureFlashArrayAddress <Pure FlashArray IP or hostname> -PureFlashArrayUser <pure FA User> -DatabasePort <Port> -CrashConsistentSnapshot`

**Create an application consistent storage snapshot for Scale Up systems on VMware with vVols** 

A volume snapshot is only created for the SAP HANA data volume. Log backups are used to roll the database forward during the recovery process. See [blog post](https://www.andrewsillifant.com/new-sap-hana-scripts-for-automating-storage-operations/) for more details.

<u>Location</u> - Powershell/Scale Up/New-StorageSnapshot.ps1

`New-StorageSnapshot -HostAddress <IP address of host> -InstanceNumber <InstanceNumber (00)> -DatabaseName <Database Name (HN1)> -DatabaseUser <DBUser> -OperatingSystemUser <OS-User> -PureFlashArrayAddress <Pure FlashArray IP or hostname> -PureFlashArrayUser <pure FA User> -DatabasePort <Port> -vCenterAddress <vCenter hostname or IP> -vCenterUser <vCenter User> -vCenterPassword <vCenter users password>`

**Create an application consistent storage snapshot for Scale Out systems** 

A volume snapshot is only created for the SAP HANA data volume on each worker host. Log backups are used to roll the database forward during the recovery process. See [blog post](https://www.andrewsillifant.com/new-sap-hana-scripts-for-automating-storage-operations/) for more details.

<u>Location</u> - Powershell/Scale Out/New-StorageSnapshot.ps1

`New-StorageSnapshot -HostAddress <IP address of host> -InstanceNumber <Instance Number (00)> -DatabaseName <Database Name (HN1)> -DatabaseUser <DBUser>  -OperatingSystemUser <OS-User> -PureFlashArrayAddress <Pure FlashArray IP or hostname> -PureFlashArrayUser <pure FA User> -DatabasePort <Port> -DomainName <Name of domain in FQDN>`

**Create a crash consistent storage snapshot for Scale Out systems** 

A volume snapshot is created for both the data and log volumes on each worker for the SAP HANA Scale Out system.

<u>Location</u> - Powershell/Scale Out/New-StorageSnapshot.ps1

`New-StorageSnapshot -HostAddress <IP address of host> -InstanceNumber <Instance Number (00)> -DatabaseName <Database Name (HN1)> -DatabaseUser <DBUser>  -OperatingSystemUser <OS-User> -PureFlashArrayAddress <Pure FlashArray IP or hostname> -PureFlashArrayUser <pure FA User> -DatabasePort <Port> -DomainName <Name of domain in FQDN> -crashconsistent`

**Recover from an application consistent storage snapshot for Scale Up systems (copy to new volume)** 

Running this script with the arguments will bring up an interactive ASCII menu , allowing for a specific point in time data snapshot to be rolled back to. The script will also check that the data snapshot is still present on the array. This script assumes the snapshot is on the same array as the running SAP HANA data volumes.This will also copy the snapshot to an entirely new volume. 

<u>Location</u> - Powershell/Scale Up/Restore-StorageSnapshot.ps1

`Restore-StorageSnapshot -HostAddress <IP address of host> -InstanceNumber <InstanceNumber (00)> -DatabaseName <Database Name (HN1)> -DatabaseUser <DBUser> -OperatingSystemUser <OS-User> -PureFlashArrayAddress <Pure FlashArray IP or hostname> -PureFlashArrayUser <pure FA User> -DatabasePort <Port> `

**Recover from an application consistent storage snapshot for Scale Up systems (overwriting existing volume)** 

Running this script with the arguments will bring up an interactive ASCII menu , allowing for a specific point in time data snapshot to be rolled back to. The script will also check that the data snapshot is still present on the array. This script assumes the snapshot is on the same array as the running SAP HANA data volumes.This will overwrite the existing volume with the snapshot. 

<u>Location</u> - Powershell/Scale Up/Restore-StorageSnapshot.ps1

`Restore-StorageSnapshot -HostAddress <IP address of host> -InstanceNumber <InstanceNumber (00)> -DatabaseName <Database Name (HN1)> -DatabaseUser <DBUser> -OperatingSystemUser <OS-User> -PureFlashArrayAddress <Pure FlashArray IP or hostname> -PureFlashArrayUser <pure FA User> -DatabasePort <Port> -OverwriteVolume`

**Recover from an application consistent storage snapshot for Scale Up systems on VMware using vVols (overwriting existing volume)** 

Running this script with the arguments will bring up an interactive ASCII menu , allowing for a specific point in time data snapshot to be rolled back to. The script will also check that the data snapshot is still present on the array. This script assumes the snapshot is on the same array as the running SAP HANA data volumes.This will overwrite the existing volume with the snapshot. 

<u>Location</u> - Powershell/Scale Up/Restore-StorageSnapshot.ps1

`Restore-StorageSnapshot -HostAddress <IP address of host> -InstanceNumber <InstanceNumber (00)> -DatabaseName <Database Name (HN1)> -DatabaseUser <DBUser> -OperatingSystemUser <OS-User> -PureFlashArrayAddress <Pure FlashArray IP or hostname> -PureFlashArrayUser <pure FA User> -DatabasePort <Port> -vCenterAddress <vCenter hostname or IP> -vCenterUser <vCenter User> -vCenterPassword `

## Python Scripts

All scripts are created to support Python 3.6 and later. The following packages are required for the scripts :

- argparse
- paramkio
- regex
- purestorage
- Datetime

The SAP HANA Python library also needs to be installed. [This process](https://help.sap.com/viewer/0eec0d68141541d1b07893a39944924e/2.0.04/en-US/39eca89d94ca464ca52385ad50fc7dea.html) is a good reference to use for the installation of the HANA client and the python library. 

**Create an application consistent storage snapshot for Scale Up systems** 

A volume snapshot is only created for the SAP HANA data volume. Log backups are used to roll the database forward during the recovery process. See [blog post](https://www.andrewsillifant.com/new-sap-hana-scripts-for-automating-storage-operations/) for more details.

<u>Location</u> - Python/Scale Up/saphana_create_snapshot.py

`saphana_create_snapshot.py --hostaddress<Host Address of SAP HANA system> --instancenumber <instancenumber> --databasename <databasename> --port<last two digits of the SAP HANA port>  --databaseuser <user with permissions to create storage snapshot> --databasepassword <password of databaseuser> --operatingsystemuser <user with permissions to freeze and unfreeze filesystems and query device information> --operatingsystempassword <password of operatingsystemuser> --flasharray <flasharray IP or FQDN of the SAP HANA block storage provider> --flasharrayuser <flasharrayuser> --flasharraypassword <flasharraypassword>`

**Create a crash consistent storage snapshot for Scale Up systems** 

A volume snapshot is created for both the data and log volumes for the SAP HANA Scale Up system

<u>Location</u> - Python/Scale Up/saphana_create_snapshot.py

`saphana_create_snapshot.py --hostaddress<Host Address of SAP HANA system> --instancenumber <instancenumber> --databasename <databasename> --port<last two digits of the SAP HANA port>  --databaseuser <user with permissions to create storage snapshot> --databasepassword <password of databaseuser> --operatingsystemuser <user with permissions to freeze and unfreeze filesystems and query device information> --operatingsystempassword <password of operatingsystemuser> --flasharray <flasharray IP or FQDN of the SAP HANA block storage provider> --flasharrayuser <flasharrayuser> --flasharraypassword <flasharraypassword> --crashconsistent`

**Create an application consistent storage snapshot for Scale Out systems** 

A volume snapshot is only created for the SAP HANA data volume on each worker host. Log backups are used to roll the database forward during the recovery process. See [blog post](https://www.andrewsillifant.com/new-sap-hana-scripts-for-automating-storage-operations/) for more details.

<u>Location</u> - Python/Scale Out/saphana_create_snapshot.py

`saphana_create_snapshot.py --hostaddress<Host Address of a worker node in the SAP HANA system> --instancenumber <instancenumber> --databasename <databasename> --port<last two digits of the SAP HANA port>  --databaseuser <user with permissions to create storage snapshot> --databasepassword <password of databaseuser> --operatingsystemuser <user with permissions to freeze and unfreeze filesystems and query device information> --operatingsystempassword <password of operatingsystemuser> --flasharray <flasharray IP or FQDN of the SAP HANA block storage provider> --flasharrayuser <flasharrayuser> --flasharraypassword <flasharraypassword>`

**Create a crash consistent storage snapshot for Scale Out systems** 

A volume snapshot is created for both the data and log volumes on each worker for the SAP HANA Scale Out system.

<u>Location</u> - Python/Scale Out/saphana_create_snapshot.py

`saphana_create_snapshot.py --hostaddress<Host Address of a worker node in the SAP HANA system> --instancenumber <instancenumber> --databasename <databasename> --port<last two digits of the SAP HANA port>  --databaseuser <user with permissions to create storage snapshot> --databasepassword <password of databaseuser> --operatingsystemuser <user with permissions to freeze and unfreeze filesystems and query device information> --operatingsystempassword <password of operatingsystemuser> --flasharray <flasharray IP or FQDN of the SAP HANA block storage provider> --flasharrayuser <flasharrayuser> --flasharraypassword <flasharraypassword> --crashconsistent`

**Recover from an application consistent storage snapshot for Scale Up systems (copy to new volume)** 

Running this script with the arguments will bring up an interactive ASCII menu , allowing for a specific point in time data snapshot to be rolled back to. The script will also check that the data snapshot is still present on the array. This script assumes the snapshot is on the same array as the running SAP HANA data volumes.This will also copy the snapshot to an entirely new volume. 

<u>Location</u> - Python/Scale Up/saphana_recoverfrom_snapshot.py

`saphana_recoverfrom_snapshot.py --hostaddress<Host Address of SAP HANA system> --instancenumber <instancenumber> --databasename <databasename> --port<last two digits of the SAP HANA port>  --databaseuser <user with permissions to create storage snapshot> --databasepassword <password of databaseuser> --operatingsystemuser <user with permissions to freeze and unfreeze filesystems and query device information> --operatingsystempassword <password of operatingsystemuser> --flasharray <flasharray IP or FQDN of the SAP HANA block storage provider> --flasharrayuser <flasharrayuser> --flasharraypassword <flasharraypassword>`

**Recover from an application consistent storage snapshot for Scale Up systems (overwrite existing volume)** 

Running this script with the arguments will bring up an interactive ASCII menu , allowing for a specific point in time data snapshot to be rolled back to. The script will also check that the data snapshot is still present on the array. This script assumes the snapshot is on the same array as the running SAP HANA data volumes.This will also overwrite the original SAP HANA Data Volume with the storage snapshot. 

<u>Location</u> - Python/Scale Up/saphana_recoverfrom_snapshot.py

`saphana_recoverfrom_snapshot.py --hostaddress<Host Address of SAP HANA system> --instancenumber <instancenumber> --databasename <databasename> --port<last two digits of the SAP HANA port>  --databaseuser <user with permissions to create storage snapshot> --databasepassword <password of databaseuser> --operatingsystemuser <user with permissions to freeze and unfreeze filesystems and query device information> --operatingsystempassword <password of operatingsystemuser> --flasharray <flasharray IP or FQDN of the SAP HANA block storage provider> --flasharrayuser <flasharrayuser> --flasharraypassword <flasharraypassword> --overwritevolume`

## Known Issues
 - POSH-SSH returns issues with Renci.SshNet - use the workaround proposed in the comment - https://github.com/darkoperator/Posh-SSH/issues/284#issuecomment-531736793
