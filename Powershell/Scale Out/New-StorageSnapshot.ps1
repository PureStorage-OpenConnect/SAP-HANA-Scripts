<#
.Notes
NAME: New-StorageSnapshot
AUTHOR: Andrew Sillifant
Website: https://www.purestorage.com/
Version: 0.2
CREATED: 2020/07/04
LASTEDIT: 2020/07/04

 .Synopsis
Provides and easy to use single command for the creating of application consistent storage snapshots between SAP HANA and Pure Storage Flash Array

.Description
Create an application consistent storage snapshot for an SAP HANA Scale Out System

.Parameter HostAddress
The IPv4 or V6 address of the SAP HANA host 

.Parameter InstanceNumber
The instance number of the SAP HANA deployment

.Parameter DatabaseName
The database name of the SAP HANA deployment 

.Parameter DatabaseUser
A database user with permissions to either SYSTEMDB or the ability to create storage snapshots and view the SAP HANA global.ini file

.Parameter DatabasePassword
The database password that matches to DatabaseUser

.Parameter DatabasePort
The Port of the SAP HANA database , in MDC environments 

.Parameter OperatingSystemUser
An operating system user with permissions to freeze and unfreeze the SAP HANA Data volume

.Parameter OperatingSystemPassword
The password for the user specified in OperatingSystemUser

.Parameter PureFlashArrayAddress
The Pure storage FlashArray which the SAP HANA deployment resides on

.Parameter PureFlashArrayUser
A user for the Pure storage FlashArray with permissions to create snapshots and view volumes

.Parameter PureFlashArrayPassword
The password for the user specified in PureFlashArrayUser

.Parameter DomainName
Only for Scale out scenarios where the search domain does not match the existing domain for the SAP HANA hosts

.Parameter CrashConsistentSnapshot
If this parameter is specified then the a snapshot of both the 
log and data volume will be created without preparing the database
If this is not wspecified the snapshot will be created as application consistent

.Example
New-StorageSnapshot -HostAddress <IP address of host> 
-InstanceNumber <Instance Number (00)> -DatabaseName <Database Name (HN1)> -DatabaseUser <DBUser> 
-OperatingSystemUser <OS-User> -PureFlashArrayAddress <Pure FlashArray IP or hostname>
 -PureFlashArrayUser <pure FA User> -DatabasePort <Port>
Create a snapshot without entering information for the password fields

.Example
New-StorageSnapshot -HostAddress <IP address of host> -InstanceNumber <Instance Number (00)>
 -DatabaseName <Database Name (HN1)> -DatabaseUser <DBUser> -DatabasePassword <DBPassword> 
-OperatingSystemUser <OS-User> -OperatingSystemPassword <OSPassword> -PureFlashArrayAddress <Pure FlashArray IP or hostname> 
-PureFlashArrayUser <pure FA User> -PureFlashArrayPassword <Pure FA Password> -DatabasePort <Port>
Create a snapshot with all of the password fields being shown as plaintext 

.Example
New-StorageSnapshot -HostAddress <IP address of host> 
-InstanceNumber <Instance Number (00)> -DatabaseName <Database Name (HN1)> -DatabaseUser <DBUser> 
-OperatingSystemUser <OS-User> -PureFlashArrayAddress <Pure FlashArray IP or hostname>
 -PureFlashArrayUser <pure FA User> -DatabasePort <Port> -CrashConsistent
Create a crash consistent snapshot without entering information for the password fields

#>

################################
#           Parameters         #
################################

Param(
    [parameter(Mandatory=$false)]
    [string[]]$HostAddresses,
    [parameter(Mandatory=$false)]
    [string]$DomainName,
    [parameter(,Mandatory=$false)]
    [string]$InstanceNumber,
    [parameter(Mandatory=$false)]
    [string]$DatabaseName,
    [parameter(Mandatory=$false)]
    [string]$DatabaseUser,
    [Parameter(Mandatory=$False)]
    $DatabasePassword ,
    [Parameter(Mandatory=$False)]
    $DatabasePort,
    [parameter(Mandatory=$false)]
    [string]$OperatingSystemUser,
    [Parameter(Mandatory=$False)]
    $OperatingSystemPassword,
    [parameter(Mandatory=$false)]
    [string]$PureFlashArrayAddress,
    [parameter(Mandatory=$false)]
    [string]$PureFlashArrayUser,
    [Parameter(Mandatory=$False)]
    $PureFlashArrayPassword,
    [Parameter(Mandatory=$False)]
    [switch]$CrashConsistentSnapshot
)


function AskSecureQ ([String]$Question, [String]$Foreground="Yellow", [String]$Background="Blue") {
    Write-Host $Question -ForegroundColor $Foreground -BackgroundColor $Background -NoNewLine
    Return (Read-Host -AsSecureString)
}

function AskInSecureQ ([String]$Question, [String]$Foreground="Yellow", [String]$Background="Blue") {
    Write-Host $Question -ForegroundColor $Foreground -BackgroundColor $Background -NoNewLine
    Return (Read-Host)
}

function Check-Arguments()
{
    if ($InstanceNumber -eq "" -and $InstanceNumber -eq [String]::Empty) 
    {
        $InstanceNumber = "00"
    }
    if ($DatabasePort -eq "" -and $DatabasePort -eq [String]::Empty) 
    {
        $InstanceNumber = "15"
    }
    if ($DatabasePassword -ne $null) 
    {
        $script:DatabasePassword = $DatabasePassword 
    } 
    else 
    {
        $script:DatabasePassword = AskInSecureQ "Type in Database password "
    }
    if ($OperatingSystemPassword -ne $null)
    {
        $script:OperatingSystemPassword =  ConvertTo-SecureString -String $OperatingSystemPassword `
        -AsPlainText -Force
    } 
    else 
    {
        $script:OperatingSystemPassword = AskSecureQ "Type in Operating System password"
    }
    if ($PureFlashArrayPassword -ne $null) 
    {
        $script:PureFlashArrayPassword = ConvertTo-SecureString -String $PureFlashArrayPassword `
        -AsPlainText -Force
    } 
    else 
    {
        $script:PureFlashArrayPassword = AskSecureQ "Type in FlashArray password"
    }
}

################################
#   Static non-public values   #
################################

$SnapshotTime = "{0:yyyy-MM-dd HH:mm:ss}" -f (get-date)
$GetSAPAHANASystemType = "SELECT VALUE FROM M_INIFILE_CONTENTS WHERE FILE_NAME = 'global.ini' `
AND SECTION = 'multidb' AND KEY = 'mode'"
$GetHostsAndStorageData = "SELECT HOST, STORAGE_ID, PATH, KEY, VALUE FROM SYS.M_ATTACHED_STORAGES `
WHERE KEY = 'WWID' AND PATH LIKE (SELECT CONCAT(VALUE,'%') FROM M_INIFILE_CONTENTS WHERE FILE_NAME`
 = 'global.ini' AND SECTION = 'persistence' AND KEY = 'basepath_datavolumes' AND VALUE NOT LIKE '$%')"
$GetHostsAndStorageLog = "SELECT HOST, STORAGE_ID, PATH, KEY, VALUE FROM SYS.M_ATTACHED_STORAGES `
WHERE KEY = 'WWID' AND PATH LIKE (SELECT CONCAT(VALUE,'%') FROM M_INIFILE_CONTENTS WHERE FILE_NAME`
 = 'global.ini' AND SECTION = 'persistence' AND KEY = 'basepath_logvolumes' AND VALUE NOT LIKE '$%')"
$CreateHDBStorageSnapshot = "BACKUP DATA FOR FULL SYSTEM CREATE SNAPSHOT COMMENT 'SNAPSHOT-" `
+ $SnapshotTime +"';"
$RetrieveHDBSnapshotID = "SELECT BACKUP_ID, COMMENT FROM M_BACKUP_CATALOG WHERE ENTRY_TYPE_NAME `
= 'data snapshot' AND STATE_NAME = 'prepared' AND COMMENT = 'SNAPSHOT-" + $SnapshotTime +"';"
$RetrieveSystemDBLocation = "SELECT HOST FROM SYS.M_SERVICES WHERE DETAIL = 'master' AND SERVICE_NAME `
= 'nameserver'"
$hdbConnectionString = "Driver={HDBODBC};ServerNode="
foreach($shhost in $HostAddresses)
{
    $hdbConnectionString = $hdbConnectionString + $shhost + ":3" + $InstanceNumber + $DatabasePort + ","
}
$hdbConnectionString = $hdbConnectionString -replace ".{1}$"
$hdbConnectionString = $hdbConnectionString + ";UID=" + $DatabaseUser + ";PWD=" + $DatabasePassword +";"
$multiDB = $false

function Check-ForPrerequisites()
{
    $hdbODBCCheck =  Get-OdbcDriver | Where-Object Name -EQ 'HDBODBC'
    if($hdbODBCCheck -eq $null)
    {
        Write-Host "Please install the SAP HANA client for microsoft windows"
        return $false
    }
    else
    {
        if( $PSVersiontable.PSVersion.Major -lt 3) {
            Write-Error  "This script requires minimum of PowerShell v3.0" 
            return $false
        }
        else
        {
            ##Check for required libraries for SSH and Pure Storage SDK
            Check-ForPOSH-SSH
            Check-ForPureStorageSDK
            return $true
        }
    }
}
  
function Check-ForPOSH-SSH()
{
    Set-PSRepository -Name PSGallery -InstallationPolicy Trusted
    $poshSSHCHeck = Get-Module -Name Posh-SSH
    if($poshSSHCHeck -eq $null)
    {
        Write-Host "Installing POSH-SSH"
        Install-Module -Name Posh-SSH   
    }
    else
    {
        Write-Host "POSH-SSH already installed"
    }
    Import-Module Posh-SSH
}
  
function Check-ForPureStorageSDK()
{
    Set-PSRepository -Name PSGallery -InstallationPolicy Trusted
    $pureSTorageSDKCheck = Get-Module -Name PureStoragePowerShellSDK
    if($pureSTorageSDKCheck -eq $null)
    {
        Write-Host "Installing Pure Storage Powershell toolkit"
        Install-Module PureStoragePowerShellSDK
    }
    else
    {
        Write-Host "Pure Storage Powershell toolkit already installed"
    }
    Import-Module PureStoragePowerShellSDK
}
  
function Get-ODBCData() 
{
    Param($hanaConnectionString,
    $hdbsql)
  
    $Conn = New-Object System.Data.Odbc.OdbcConnection($hanaCOnnectionString)
    $Conn.open()
    $readcmd = New-Object System.Data.Odbc.OdbcCommand($hdbsql,$Conn)
    $readcmd.CommandTimeout = '300'
    $da = New-Object System.Data.Odbc.OdbcDataAdapter($readcmd)
    $dt = New-Object System.Data.DataTable
    [void]$da.fill($dt)
    $Conn.close()
    return $dt
}
  
function Check-SAPHANASystemType()
{
    $systemtype = Get-ODBCData -hanaConnectionString $hdbConnectionString -hdbsql $GetSAPAHANASystemType
    return $systemtype
}
  
function Get-VolumeSerialNumber()
{
    Param(
        $HostAddress,
        $DataVolumeMountPoint,
        $OSUser,
        $OSPassword
    )
    $Cred = New-Object –TypeName System.Management.Automation.PSCredential –ArgumentList $OSUser, $OSPassword
          
    $sessionval = New-SSHSession -ComputerName $HostAddress -Credential $Cred -AcceptKey:$True -ConnectionTimeout 600
    $session = Get-SSHSession -SessionId $sessionval.SessionId
    $stream = $session.Session.CreateShellStream("dumb", 0, 0, 0, 0, 1000)
    Start-Sleep -Seconds 1
    $output = $stream.Read()
    $stream.WriteLine("df -h | grep " + $DataVolumeMountPoint)
    $output = $stream.Readline()
    $dfToParse = $stream.ReadLine()
    $ParsedVolumeDevLocation = [regex]::Match($dfToParse, '(\S+)').Groups[1].Value
    $udevADMQuery = "udevadm info --query=all --name=" + $ParsedVolumeDevLocation + " | grep DM_SERIAL"
    $stream.WriteLine($udevADMQuery)
    $output = $stream.ReadLine()
    $queryResponse = $stream.ReadLine()
    $volSerialNumber = ($queryResponse.split('='))[1]
    $output =  Remove-SSHSession -SessionId $sessionval.SessionId
    return $volSerialNumber
}
  
function Get-HostAttachedVolume()
{
    Param(
        $HostAddress,
        $SapHANAStorageInfo,
        $OSUser,
        $OSPassword
    )
  
    $Cred = New-Object –TypeName System.Management.Automation.PSCredential –ArgumentList $OSUser, $OSPassword
    $sessionval = New-SSHSession -ComputerName $HostAddress -Credential $Cred -AcceptKey:$True -ConnectionTimeout 600
    $session = Get-SSHSession -SessionId $sessionval.SessionId
    $stream = $session.Session.CreateShellStream("dumb", 0, 0, 0, 0, 1000)
    Start-Sleep -Seconds 1
    $output = $stream.Read()
    $stream.WriteLine("date")
    $output = $stream.ReadLine()
    $output = $stream.ReadLine()
    Start-Sleep -Milliseconds 500
    $promptLength = $stream.Length
    $found = $false
    $returnObject
    while(!$found)
    {
        foreach($si in $SapHANAStorageInfo)
        {
            $stream.WriteLine("df -h | grep " + $si.PATH)
            Start-Sleep -Milliseconds 500
            $output = $stream.Readline()
            while($stream.Length -gt $promptLength)
            {
                $dfToParse = $stream.ReadLine()
                $si | Add-Member -NotePropertyName HOST_IP -NotePropertyValue $HostAddress
                $returnObject = $si
                $found = $True
            }
        }
        $found = $true
    }
  
    $output =  Remove-SSHSession -SessionId $sessionval.SessionId
    return $returnObject
}
  
function Create-PureStorageVolumeSnapshot()
{
    Param(
        $FlashArrayAddress, 
        $User, 
        $Password,
        $SerialNumber, 
        $SnapshotSuffix
    )
  
    $Array = New-PfaArray -EndPoint $FlashArrayAddress -username $User -Password $Password -IgnoreCertificateError
    $Volumes = Get-PfaVolumes -Array $Array 
  
    foreach($vol in $Volumes)
    {
        if($serialNumber.Contains($vol.serial.tolower()))
        {
            Write-Host "Volume located, creating snapshot"
            $VolumeSnapshot = New-PfaVolumeSnapshots -Array $Array -Sources $vol.name -Suffix $SnapshotSuffix
            if(!($VolumeSnapshot.name -eq $null))
            {
                Write-host "Snapshot name : " $VolumeSnapshot.name 
                return $VolumeSnapshot.serial
            }
            else
            {
                return $null
            }
        }
    }
}

function Create-PureStoragePGSnapshot()
{
    Param(
        $FlashArrayAddress, 
        $User, 
        $Password,
        $PGName
    )
  
    $Array = New-PfaArray -EndPoint $FlashArrayAddress -username $User -Password $Password -IgnoreCertificateError
    New-PfaProtectionGroupSnapshot -Array $Array -Protectiongroupname $PGName
}

function Check-PureStoragePG()
{
    Param(
        $FlashArrayAddress, 
        $User, 
        $Password,
        $PersistenceInfo,
        $PGName
    )
    
    $Array = New-PfaArray -EndPoint $FlashArrayAddress -username $User -Password $Password -IgnoreCertificateError
    
    ##For scale out , need to ensure that the volumes are exported using a host group
    
    $HostGroups = Get-PfaHostGroups -Array $Array
    $PersistenceInfoWithVolNames = @()

    $ProtectionGroups = Get-PfaProtectionGroup -Array $Array -Name $PGName -ErrorAction SilentlyContinue
    if($ProtectionGroups -eq $null)
    {
        $Output = New-PfaProtectionGroup -Array $Array -Name $PGName
    }

    $Volumes = Get-PfaVolumes -Array $Array

    
    foreach($device in $PersistenceInfo)
    {
        foreach($vol in $Volumes)
        {
            if($device.SerialNumber.Contains($vol.serial.tolower()))
            {
               $PFAPG = Get-PfaVolumeProtectionGroups -Array $Array -VolumeName $vol.name 
               [int]$PGcount = 0
               if($PFSAPG -ne "")
               {
                    
                    foreach($pg in $PFAPG)
                    {
                        if($pg.name -eq $PGName)
                        {
                            $PGcount++
                        }
                    }    
                }
                $device | Add-Member -MemberType NoteProperty -Name VolumeName -Value $vol.name 
                if(!$PGcount -gt 0)
                {
                    $Output = Add-PfaVolumesToProtectionGroup -Array $Array -Name $PGName -VolumesToAdd $device.VolumeName
                }
                $PersistenceInfoWithVolNames += $device       
            }
        }
    }

    return $PersistenceInfoWithVolNames
}
  
function Create-SAPHANADatabaseSnapshot()
{
    Get-ODBCData -hanaConnectionString $hdbConnectionString -hdbsql $CreateHDBStorageSnapshot
    $hdbSnapshot = Get-ODBCData -hanaConnectionString $hdbConnectionString -hdbsql $RetrieveHDBSnapshotID
    return $hdbSnapshot
}
  
function FreezeFileSystem()
{
    param(
        $HostAddress, 
        $OSUser,
        $OSPassword,
        $FilesystemMount
    )
    $Cred = New-Object –TypeName System.Management.Automation.PSCredential –ArgumentList $OSUser, $OSPassword
          
    $sessionval = New-SSHSession -ComputerName $HostAddress -Credential $Cred -AcceptKey:$True -ConnectionTimeout 600
    $session = Get-SSHSession -SessionId $sessionval.SessionId
    $stream = $session.Session.CreateShellStream("dumb", 0, 0, 0, 0, 1000)
    Start-Sleep -Seconds 1
    $output = $stream.Read()
    $stream.WriteLine(" /sbin/fsfreeze -f " + $FilesystemMount)
    Start-Sleep -Milliseconds 250
    $output =  Remove-SSHSession -SessionId $sessionval.SessionId
}
  
function UnFreezeFileSystem()
{
    param(
        $HostAddress, 
        $OSUser,
        $OSPassword,
        $FilesystemMount
    )
    $Cred = New-Object –TypeName System.Management.Automation.PSCredential –ArgumentList $OSUser, $OSPassword
          
    $sessionval = New-SSHSession -ComputerName $HostAddress -Credential $Cred -AcceptKey:$True -ConnectionTimeout 600
    $session = Get-SSHSession -SessionId $sessionval.SessionId
    $stream = $session.Session.CreateShellStream("dumb", 0, 0, 0, 0, 1000)
    Start-Sleep -Seconds 1
    $output = $stream.Read()
    $stream.WriteLine(" /sbin/fsfreeze -u " + $FilesystemMount)
    Start-Sleep -Milliseconds 250
    $output =  Remove-SSHSession -SessionId $sessionval.SessionId
}
  
function Abandon-SAPHANADatabaseSnapshot()
{
    Param(
        $BackupID, 
        $EBID
    )
    $AbandonHDBSnapshot = "BACKUP DATA FOR FULL SYSTEM CLOSE SNAPSHOT BACKUP_ID " + $BackupID `
+ " UNSUCCESSFUL '" + $EBID + "';"
    Get-ODBCData -hanaConnectionString $hdbConnectionString -hdbsql $AbandonHDBSnapshot
}
  
function Confirm-SAPHANADatabaseSnapshot()
{
    Param(
        $BackupID,
        $EBID
    )
    $ConfirmHDBSnapshot = "BACKUP DATA FOR FULL SYSTEM CLOSE SNAPSHOT BACKUP_ID " + $BackupID `
+ " SUCCESSFUL '" + $EBID + "';"
    Get-ODBCData -hanaConnectionString $hdbConnectionString -hdbsql $ConfirmHDBSnapshot
}


##Check for necessary Prerequisites
if(Check-ForPrerequisites)
{
    Check-Arguments
    ##Check the SAP HANA system type for multiDB or single tenant DB
    $SystemType = Check-SAPHANASystemType
    if($SystemType.VALUE -eq 'multidb')
    {
        $systemDBLocation = Get-ODBCData -hanaConnectionString $hdbConnectionString -hdbsql $RetrieveSystemDBLocation
        if(!($DomainName -eq $null))
        {
            $hdbConnectionString = "Driver={HDBODBC};ServerNode=" + $systemDBLocation.HOST + "." + $DomainName + ":3" + $InstanceNumber + "13;UID=" + $DatabaseUser + ";PWD=" + $DatabasePassword +";"
        }
        else
        {
            $hdbConnectionString = "Driver={HDBODBC};ServerNode=" + $systemDBLocation.HOST + ":3" + $InstanceNumber + "13;UID=" + $DatabaseUser + ";PWD=" + $DatabasePassword +";"
        }
        $multiDB = $true
    }

    if(!$CrashConsistentSnapshot)
    {
        ##Get the volumes and mount path
        $HostsAndAttachedStorage = Get-ODBCData -hanaConnectionString $hdbConnectionString -hdbsql $GetHostsAndStorageData
        

        $HostStorageInfo = @()
        foreach($shhost in $HostAddresses)
        {
            $HostStorageInfo += Get-HostAttachedVolume -HostAddress $shhost -SapHANAStorageInfo $HostsAndAttachedStorage -OSUser $OperatingSystemUser -OSPassword $OperatingSystemPassword
        }

        $IsolatedHostsAndStorage = @()
        foreach($shhost in $HostStorageInfo)
        {
            if(!($shhost -eq $null))
            {
                $IsolatedHostsAndStorage += $shhost
            }
        }


        ##Prepare HANA Storage Snapshot
        Write-Host "Preparing SAP HANA Snapshot"
        $HANASnapshot = Create-SAPHANADatabaseSnapshot 
        Start-Sleep -Seconds 5

        ##Freeze the filesystems
        Write-Host "Freezing filesystems"
        foreach($shhost in $IsolatedHostsAndStorage)
        {
            FreezeFileSystem -HostAddress $shhost.HOST_IP -OSUser $OperatingSystemUser -OSPassword $OperatingSystemPassword -FilesystemMount $shhost.PATH
        }

        ##Create Pure Volume Snapshots
        Write-Host "Creating block volume snapshot"
        $snapshotSerial = @()
        foreach($shhost in $IsolatedHostsAndStorage)
        {
            
            $SnapshotSuffix = "SAPHANA-" + $HANASnapshot.BACKUP_ID.ToString() + "-Host-" + $shhost.HOST + "-Path-" + $shhost.PATH.Replace($ShortMountPath + "/", "")
            $snapshotSerial += Create-PureStorageVolumeSnapshot -FlashArrayAddress $PureFlashArrayAddress -User $PureFlashArrayUser -Password $PureFlashArrayPassword -SerialNumber $shhost.VALUE -SnapshotSuffix $SnapshotSuffix
        
        }
       
        ##Unfreeze the filesystems
        Write-Host "Unfreezing filesystems"
        foreach($shhost in $IsolatedHostsAndStorage)
        {
            UnFreezeFileSystem -HostAddress $shhost.HOST_IP -OSUser $OperatingSystemUser -OSPassword $OperatingSystemPassword -FilesystemMount $shhost.PATH
        }
        $countserials = 0
        $EBID = ""
        foreach($serial in $snapshotSerial)
        {
            if($serial -eq $null)
            {
                $countserials -= 1
            }
            else
            {
                $EBID = $EBID + $serial + ","
                $countserials += 1
            }  
        }


        if($countserials -eq $IsolatedHostsAndStorage.Count)
        {
            Write-Host "Confirming Snapshot"
            $EBID = $EBID -replace ".{1}$"
            Confirm-SAPHANADatabaseSnapshot -BackupID $HANASnapshot.BACKUP_ID.ToString() -EBID "ScaleOut"
        }
        else
        {
            Write-Host "Abandoning Snapshot"
            Abandon-SAPHANADatabaseSnapshot -BackupID $HANASnapshot.BACKUP_ID.ToString() -EBID "ScaleOut"
        }
    }
    else
    {
        $dataDevices = (Get-ODBCData -hanaConnectionString $hdbConnectionString -hdbsql $GetHostsAndStorageData)
        $logDevices = (Get-ODBCData -hanaConnectionString $hdbConnectionString -hdbsql $GetHostsAndStorageLog)
        

        $HostStorageInfo = @()
        foreach($shhost in $HostAddresses)
        {
            $deviceInfo = Get-HostAttachedVolume -HostAddress $shhost -SapHANAStorageInfo $dataDevices -OSUser $OperatingSystemUser -OSPassword $OperatingSystemPassword
            $HostStorageInfo += $deviceInfo[1]
            $deviceInfo = Get-HostAttachedVolume -HostAddress $shhost -SapHANAStorageInfo $logDevices -OSUser $OperatingSystemUser -OSPassword $OperatingSystemPassword
            $HostStorageInfo += $deviceInfo[1]
        }
        
        $Persistence = @()
        foreach($d in $HostStorageInfo)
        {
            if($d -ne $null)
            {
                $persistenceObj = New-Object -TypeName PSObject


                $SerialNumber =  Get-VolumeSerialNumber -HostAddress $d.HOST_IP -OSUser $OperatingSystemUser `
                -OSPassword $OperatingSystemPassword -DataVolumeMountPoint $d.VALUE
                $persistenceObj | Add-Member -MemberType NoteProperty -Name MountPoint -Value $d.PATH
                $persistenceObj | Add-Member -MemberType NoteProperty -Name Host -Value $d.HOST
                $persistenceObj | Add-Member -MemberType NoteProperty -Name Host_IP -Value $d.HOST_IP
                $persistenceObj | Add-Member -MemberType NoteProperty -Name SerialNumber -Value $SerialNumber
                $Persistence += $persistenceObj 
            }
        }
        
        #Check if the log and data volumes are already apart of a protection group in a host group

        $PGName = "SAPHANA-" +$DatabaseName + "-CrashConsistent"

        $Persistence = Check-PureStoragePG -FlashArrayAddress $PureFlashArrayAddress -User $PureFlashArrayUser -Password $PureFlashArrayPassword -PersistenceInfo $Persistence -PGName $PGName


        ##Freeze the filesystem
        foreach($p in $Persistence)
        {
            Write-Host "Freezing filesystem for " $p.MountPoint
            FreezeFileSystem -HostAddress $p.Host_IP -OSUser $OperatingSystemUser -OSPassword `
            $OperatingSystemPassword -FilesystemMount $p.MountPoint
        }

        Write-Host "Creating Crash Consistent Snapshot"
        $PGSnap = Create-PureStoragePGSnapshot -FlashArrayAddress $PureFlashArrayAddress -User $PureFlashArrayUser -Password $PureFlashArrayPassword -PGName $PGName
        Write-Host $PGSnap.name " created for SAP HANA Database " $DatabaseName
        foreach($p in $Persistence)
        {
            Write-Host "Unfreezing filesystem for " $p.MountPoint
            UnFreezeFileSystem -HostAddress $p.Host_IP -OSUser $OperatingSystemUser -OSPassword `
            $OperatingSystemPassword -FilesystemMount $p.MountPoint
        }
    }
}
  
