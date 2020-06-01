<#
.Notes
NAME: Restore-StorageSnapshot
AUTHOR: Andrew Sillifant
Website: https://www.purestorage.com/
Version: 0.1
CREATED: 2020/30/05
LASTEDIT: 2020/30/05

 .Synopsis
Provides and easy to use mechanism to recover data snapshots for SAP HANA databases
The database must be running for this script to work
If the database is not available , use SAP HANA studio or SAP HANA cockpit

.Description
Recovers from an application consistent storage snapshot for an SAP HANA Scale Up System

.Parameter HostAddress
The IPv4 or V6 address of the SAP HANA host 

.Parameter InstanceNumber
The instance number of the SAP HANA deployment

.Parameter DatabaseName
The database name of the SAP HANA deployment 

.Parameter DatabaseUser
A database user with permissions to either SYSTEMDB or the ability to create storage snapshots 
and view the SAP HANA global.ini file

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

.Parameter SIDADMPassword
The password for the <SID>adm user

.Parameter OverwriteVolume
A switch parameter , which if specified recovers the database by overwriting the original volume


.Example
Restore-StorageSnapshot.ps1 -HostAddress <IP address of host> -InstanceNumber <Instance Number (00)>  
-DatabaseName <Database Name (HN1)> -DatabaseUser <DBUser>  -DatabasePassword <DBPassword>  
-DatabasePort <Port> -OperatingSystemUser <OS-User> -OperatingSystemPassword <OSPassword> 
-PureFlashArrayAddress <Pure FlashArray IP or hostname>  -PureFlashArrayUser <pure FA User> 
-PureFlashArrayPassword <Pure FA Password> -SIDADMPassword <sidadm password> 
Recovers from an application consistent snapshot by copying the snapshot to a new volume

.Example
Restore-StorageSnapshot.ps1 -HostAddress <IP address of host> -InstanceNumber <Instance Number (00)>  
-DatabaseName <Database Name (HN1)> -DatabaseUser <DBUser>  -DatabasePassword <DBPassword>  
-DatabasePort <Port> -OperatingSystemUser <OS-User> -OperatingSystemPassword <OSPassword> 
-PureFlashArrayAddress <Pure FlashArray IP or hostname>  -PureFlashArrayUser <pure FA User> 
-PureFlashArrayPassword <Pure FA Password> -SIDADMPassword <sidadm password> -OverwriteVolume
Recovers from an application consistent snapshot by overwriting the SAP HANA data volume

.Example
Restore-StorageSnapshot.ps1 -HostAddress <IP address of host> -InstanceNumber <Instance Number (00)>  
-DatabaseName <Database Name (HN1)> -DatabaseUser <DBUser> -DatabasePort <Port> 
-OperatingSystemUser <OS-User> -PureFlashArrayAddress <Pure FlashArray IP or hostname>  
-PureFlashArrayUser <pure FA User> 

Recovers from an application consistent snapshot by copying the snapshot to a new volume
No passwords need to be given in the command line , the user will be prompted for them

.Example
Restore-StorageSnapshot.ps1 -HostAddress <IP address of host> -InstanceNumber <Instance Number (00)>  
-DatabaseName <Database Name (HN1)> -DatabaseUser <DBUser> -DatabasePort <Port> 
-OperatingSystemUser <OS-User> -PureFlashArrayAddress <Pure FlashArray IP or hostname>  
-PureFlashArrayUser <pure FA User> 
Recovers from an application consistent snapshot by overwriting the SAP HANA data volume
No passwords need to be given in the command line , the user will be prompted for them

#>

################################
#           Parameters         #
################################

Param(
    [parameter(Mandatory=$True)]
    [string]$HostAddress,
    [parameter(,Mandatory=$True)]
    [string]$InstanceNumber,
    [parameter(Mandatory=$True)]
    [string]$DatabaseName ,
    [parameter(Mandatory=$True)]
    [string]$DatabaseUser,
    [Parameter(Mandatory=$False)]
    $DatabasePassword,
    [Parameter(Mandatory=$True)]
    $DatabasePort,
    [parameter(Mandatory=$True)]
    [string]$OperatingSystemUser,
    [Parameter(Mandatory=$False)]
    $OperatingSystemPassword,
    [parameter(Mandatory=$True)]
    [string]$PureFlashArrayAddress,
    [parameter(Mandatory=$True)]
    [string]$PureFlashArrayUser,
    [Parameter(Mandatory=$False)]
    $PureFlashArrayPassword,
    [Parameter(Mandatory=$False)]
    $SIDADMPassword,
    [Parameter(Mandatory=$False)]
    [switch]$OverwriteVolume
)

################################
#       Default Values for     #
#       optional parameters    #
#       and prompt functions   #
################################

function AskSecureQ ([String]$Question, [String]$Foreground="Yellow", [String]$Background="Blue") {
    Write-Host $Question -ForegroundColor $Foreground -BackgroundColor $Background -NoNewLine
    Return (Read-Host -AsSecureString)
}

function AskInSecureQ ([String]$Question, [String]$Foreground="Yellow", [String]$Background="Blue") {
    Write-Host $Question -ForegroundColor $Foreground -BackgroundColor $Background -NoNewLine
    $plainTextEncrypted = Read-Host -AsSecureString
    $bstr = [System.Runtime.InteropServices.Marshal]::SecureStringToBSTR($plainTextEncrypted)
    $plaintext = [System.Runtime.InteropServices.Marshal]::PtrToStringAuto($bstr)
    return $plaintext
}

function Check-Arguments()
{
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
    if ($SIDADMPassword -ne $null) 
    {
        $script:SIDADMPassword = ConvertTo-SecureString -String $SIDADMPassword `
        -AsPlainText -Force
    } 
    else 
    {
        $script:SIDADMPassword = AskSecureQ "Type in <sidadm> password"
    }
}

################################
#   Static non-public values   #
################################

$GetSAPAHANASystemType = "SELECT VALUE FROM M_INIFILE_CONTENTS WHERE FILE_NAME = 'global.ini' `
AND SECTION = 'multidb' AND KEY = 'mode'"
$GetSAPHANACatalog = "SELECT BACKUP_ID,UTC_START_TIME FROM SYS.M_BACKUP_CATALOG WHERE `
ENTRY_TYPE_NAME = 'data snapshot' ORDER BY SYS_END_TIME desc"
$GetSAPHANAInstanceID = "SELECT VALUE from SYS.M_SYSTEM_OVERVIEW WHERE NAME = 'Instance ID'"
$GetDataVolumeLocation = "SELECT VALUE FROM M_INIFILE_CONTENTS WHERE FILE_NAME = 'global.ini' `
AND SECTION = 'persistence' AND KEY = 'basepath_datavolumes'  AND VALUE NOT LIKE '$%'"
$hdbRecoverSystemDB = "RECOVER DATA USING SNAPSHOT  CLEAR LOG"
$hdbGetTenantsToRestore = "SELECT DATABASE_NAME FROM M_DATABASES WHERE ACTIVE_STATUS = 'NO'"
$multiDB = $false

  
function Check-ForPrerequisites()
{
    $hdbODBCCheck =  Get-OdbcDriver | Where-Object Name -EQ 'HDBODBC'
    if($hdbODBCCheck -eq $null)
    {
        Write-Host "`t`t ------------------------------------------------ " -ForegroundColor White
        Write-host "`t`t|       Please install the SAP HANA client       |" -ForegroundColor White
        Write-Host "`t`t ------------------------------------------------ " -ForegroundColor White
        return $false
    }
    else
    {
        if( $PSVersiontable.PSVersion.Major -lt 3) {
            Write-Host "`t`t ------------------------------------------------ " -ForegroundColor Red
            Write-host "`t`t|This script requires minimum of PowerShell v3.0 |" -ForegroundColor Red
            Write-Host "`t`t ------------------------------------------------ " -ForegroundColor Red
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
        Write-Host "`t`t ------------------------------------------------ " -ForegroundColor White
        Write-host "`t`t|              Installing POSH-SSH               |" -ForegroundColor White
        Write-Host "`t`t ------------------------------------------------ " -ForegroundColor White
        Install-Module -Name Posh-SSH   
    }
    else
    {
        Write-Host "`t`t ------------------------------------------------ " -ForegroundColor White
        Write-host "`t`t|           POSH-SSH already installed           |" -ForegroundColor White
        Write-Host "`t`t ------------------------------------------------ " -ForegroundColor White

    }
    Import-Module Posh-SSH
}
  
function Check-ForPureStorageSDK()
{
    Set-PSRepository -Name PSGallery -InstallationPolicy Trusted
    $pureSTorageSDKCheck = Get-Module -Name PureStoragePowerShellSDK
    if($pureSTorageSDKCheck -eq $null)
    {
        Write-Host "`t`t ------------------------------------------------ " -ForegroundColor White
        Write-host "`t`t|     Installing Pure Storage Powershell SDK     |" -ForegroundColor White
        Write-Host "`t`t ------------------------------------------------ " -ForegroundColor White
        Install-Module PureStoragePowerShellSDK
    }
    else
    {
        Write-Host "`t`t ------------------------------------------------ " -ForegroundColor White
        Write-host "`t`t|  Pure Storage Powershell SDK already installed |" -ForegroundColor White
        Write-Host "`t`t ------------------------------------------------ " -ForegroundColor White
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
    $Cred = New-Object -TypeName System.Management.Automation.PSCredential -ArgumentList $OSUser, $OSPassword
          
    $sessionval = New-SSHSession -ComputerName $HostAddress -Credential $Cred -AcceptKey:$True -ConnectionTimeout 600
    $session = Get-SSHSession -SessionId $sessionval.SessionId
    $stream = $session.Session.CreateShellStream("dumb", 0, 0, 0, 0, 1000)
    Start-Sleep -Seconds 1
    do{$output = $stream.read()}while($stream.DataAvailable)
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

function Check-StorageSnapshot()
{
     Param(
        $FlashArrayAddress, 
        $User, 
        $Password,
        $BackupID
    )

    $Array = New-PfaArray -EndPoint $FlashArrayAddress -username $User -Password $Password -IgnoreCertificateError
    $Volumes = Get-PfaVolumes -Array $Array 
    $VolSnap = $null
    foreach($vol in $Volumes)
    {
        $VolumeSnaps = Get-PfaVolumeSnapshots -Array $Array -VolumeName $vol.name
        foreach($snap in $VolumeSnaps)
        {
            if(($snap.name).Contains($BackupID))
            {
                $VolSnap = $snap
            }
        }        
    }
    return $VolSnap
}

function Stop-SAPHANAInstance()
{
    Param(
        $HostAddress,
        $DataVolumeMountPoint,
        $OSUser,
        $OSPassword
    )

    $Cred = New-Object -TypeName System.Management.Automation.PSCredential -ArgumentList $OSUser, $OSPassword
    $sessionval = New-SSHSession -ComputerName $HostAddress -Credential $Cred -AcceptKey:$True -ConnectionTimeout 600
    $session = Get-SSHSession -SessionId $sessionval.SessionId
    $stream = $session.Session.CreateShellStream("dumb", 0, 0, 0, 0, 1000)
    Start-Sleep -Seconds 1
    do{$output = $stream.read()}while($stream.DataAvailable)
    $shutdownInstanceString = "/usr/sap/hostctrl/exe/sapcontrol -nr " + $InstanceNumber + " -function Stop"
    $checkInstanceStatusString = "/usr/sap/hostctrl/exe/sapcontrol -nr " + $InstanceNumber + " -function GetProcessList"
    $Stream.WriteLine($shutdownInstanceString)
    Start-Sleep -Milliseconds 100
    do{$output = $stream.read()}while($stream.DataAvailable)

    $running = $true
    while($running)
    {
        $stream.WriteLine($checkInstanceStatusString)
        do{
            start-sleep -Milliseconds 50
            $response = $stream.Read()
        }
        while($stream.DataAvailable)
        if($response.Contains("hdbdaemon, HDB Daemon, GRAY, Stopped"))
        {
            $running = $false
        }
    }
    $unmountDataVolumeString = "umount " + $DataVolumeMountPoint
    $stream.WriteLine($unmountDataVolumeString)
    Start-Sleep -Milliseconds 100
    $output =  Remove-SSHSession -SessionId $sessionval.SessionId
    
}

function Restore-OverwiteVolume()
{
    Param(
        $FlashArrayAddress, 
        $User, 
        $Password,
        $Snapshot,
        $HostAddress,
        $DataVolumeMountPoint,
        $OSUser,
        $OSPassword,
        $CurrentVolumeSerialNumber
    )

    $Array = New-PfaArray -EndPoint $FlashArrayAddress -username $User -Password $Password -IgnoreCertificateError

    #Need to overwrite the current volume attached to the HANA instance 
    $Volumes = Get-PfaVolumes -Array $Array 
  
    foreach($vol in $Volumes)
    {
        if($CurrentVolumeSerialNumber.Contains($vol.serial.tolower()))
        {
            $volumeoverwite = New-PfaVolume -Array $Array -VolumeName $vol.name -Source $Snapshot.name -Overwrite
        }
    }
    

    $Cred = New-Object -TypeName System.Management.Automation.PSCredential -ArgumentList $OSUser, $OSPassword
    $sessionval = New-SSHSession -ComputerName $HostAddress -Credential $Cred -AcceptKey:$True -ConnectionTimeout 600
    $session = Get-SSHSession -SessionId $sessionval.SessionId
    $stream = $session.Session.CreateShellStream("dumb", 0, 0, 0, 0, 1000)
    Start-Sleep -Seconds 1
    do{$output = $stream.read()}while($stream.DataAvailable)
   
    #Operating system add new device map
    Start-Sleep -Seconds 5
    $rescanStorageStringAdd = "rescan-scsi-bus.sh -a" 
    $stream.writeline($rescanStorageStringAdd)
    do{$output += start-sleep -Milliseconds 250;$stream.read();start-sleep -Milliseconds 250;}while($stream.DataAvailable)
    Start-Sleep -Seconds 10
    $deviceMountString = "mount /dev/mapper/3624a9370" + $volumeoverwite.serial.ToLower() + " " + $DataVolumeMountPoint
    $stream.writeline($deviceMountString)
    Start-Sleep -Seconds 30
    $output =  Remove-SSHSession -SessionId $sessionval.SessionID
    $ReturnedSerialNumber = Get-VolumeSerialNumber -HostAddress $HostAddress -DataVolumeMountPoint $DataVolumeMountPoint -OSUser $OSUser -OSPassword $OSPassword
    if($ReturnedSerialNumber.Contains($volumeoverwite.serial.ToLower()))
    {
        return $True
    }
    else
    {
        return $False
    }

}

function Restore-CopySnapToVolume()
{
    Param(
        $FlashArrayAddress, 
        $User, 
        $Password,
        $Snapshot,
        $HostAddress,
        $DataVolumeMountPoint,
        $OSUser,
        $OSPassword,
        $BackupID, 
        $SerialNumber
    )

    $Array = New-PfaArray -EndPoint $FlashArrayAddress -username $User -Password $Password -IgnoreCertificateError
    $newVolFromCopy = New-PfaVolume -Array $Array -VolumeName ($snapshot.source + "-" + $BackupID) -Source $snapshot.name 
    $Hosts = Get-PfaHosts -Array $Array
    foreach ($hostobj in $hosts)
    {
        $hostvolumes = Get-PfaHostVolumeConnections -Array $Array -Name $hostobj.name
        foreach($hostvol in $hostvolumes)
        {
            if($hostvol.vol -ne "pure-protocol-endpoint")
            {
                $vol = Get-PfaVolume -Array $Array -Name $hostvol.vol 
                if($SerialNumber.Contains($vol.serial.tolower()))
                {
                    #disconnect existing data volume
                    $disconnectHost = Remove-PfaHostVolumeConnection -Array $Array -HostName $hostobj.name -VolumeName $hostvol.vol
                    #Operating system remove device maps
                    $Cred = New-Object -TypeName System.Management.Automation.PSCredential -ArgumentList $OSUser, $OSPassword
                    $sessionval = New-SSHSession -ComputerName $HostAddress -Credential $Cred -AcceptKey:$True -ConnectionTimeout 600
                    $session = Get-SSHSession -SessionId $sessionval.SessionId
                    $stream = $session.Session.CreateShellStream("dumb", 0, 0, 0, 0, 1000)
                    Start-Sleep -Seconds 1
                    do{$output += start-sleep -Milliseconds 250;$stream.read();start-sleep -Milliseconds 250;}while($stream.DataAvailable)
                    $rescanStorageStringRemove = "rescan-scsi-bus.sh -r" 
                    $stream.writeline($rescanStorageStringRemove)
                    do{$output += start-sleep -Milliseconds 250;$stream.read();start-sleep -Milliseconds 250;}while($stream.DataAvailable)
                    #connect copy data volume 
                    $connectHost = New-PfaHostVolumeConnection -Array $Array -VolumeName $newVolFromCopy.name -HostName $hostobj.name
                    #Operating system add new device map
                    $rescanStorageStringAdd = "rescan-scsi-bus.sh -a" 
                    $stream.writeline($rescanStorageStringAdd)
                    do{$output += start-sleep -Milliseconds 250;$stream.read();start-sleep -Milliseconds 250;}while($stream.DataAvailable)
                    Start-Sleep -Seconds 10
                    $deviceMountString = "mount /dev/mapper/3624a9370" + $newVolFromCopy.serial.ToLower() + " " + $DataVolumeMountPoint
                    $stream.writeline($deviceMountString)
                    Start-Sleep -Seconds 30
                    $output =  Remove-SSHSession -SessionId $sessionval.SessionID
                    $ReturnedSerialNumber = Get-VolumeSerialNumber -HostAddress $HostAddress -DataVolumeMountPoint $DataVolumeMountPoint -OSUser $OSUser -OSPassword $OSPassword
                    if($ReturnedSerialNumber.Contains($newVolFromCopy.serial.ToLower()))
                    {
                        return $True
                    }
                    else
                    {
                        return $False
                    }
                }
            }
        }
    }
}

function Restore-SystemDB()
{
    Param(
    $HostAddress,
    $SID)

    $sdiadmuser = $SID.VALUE.ToLower() + "adm"
    $Cred = New-Object -TypeName System.Management.Automation.PSCredential -ArgumentList $sdiadmuser, $script:SIDADMPassword
    $sessionval = New-SSHSession -ComputerName $HostAddress -Credential $Cred -AcceptKey:$True -ConnectionTimeout 600
    $session = Get-SSHSession -SessionId $sessionval.SessionId
    $stream = $session.Session.CreateShellStream("dumb", 0, 0, 0, 0, 1000)
    Start-Sleep -Seconds 5
    do{$output = $stream.read()}while($stream.DataAvailable)
    $recoverSystemDBString = "/usr/sap/" + $SID.VALUE + "/HDB" + $InstanceNumber + "/HDBSettings.sh /usr/sap/" + $SID.VALUE + `
    "/HDB" + $InstanceNumber + "/exe/python_support/recoverSys.py --command=""RECOVER DATA  USING SNAPSHOT  CLEAR LOG"""
    $stream.WriteLine($recoverSystemDBString)
    Start-Sleep -Seconds 1
    do{$output = $stream.read();Start-Sleep -Milliseconds 500}while($stream.DataAvailable)
    $output =  Remove-SSHSession -SessionId $sessionval.SessionID
}

function Check-RunningInstance()
{
    Param(
        $HostAddress,
        $OSUser,
        $OSPassword
    )

    $Cred = New-Object -TypeName System.Management.Automation.PSCredential -ArgumentList $OSUser, $OSPassword
    $sessionval = New-SSHSession -ComputerName $HostAddress -Credential $Cred -AcceptKey:$True -ConnectionTimeout 600
    $session = Get-SSHSession -SessionId $sessionval.SessionId
    $stream = $session.Session.CreateShellStream("dumb", 0, 0, 0, 0, 1000)
    Start-Sleep -Seconds 1
    do{$output = $stream.read()}while($stream.DataAvailable)
    $checkInstanceStatusString = "/usr/sap/hostctrl/exe/sapcontrol -nr " + $InstanceNumber + " -function GetProcessList"

    $running = $false
    while(!$running)
    {
        
        do{
            $stream.WriteLine($checkInstanceStatusString)
            start-sleep -Seconds 1
            $response = $stream.Read()
        }
        while($stream.DataAvailable)
        if($response.Contains("hdbdaemon, HDB Daemon, GREEN, Running"))
        {
            $running = $True
        }
    }
    $output =  Remove-SSHSession -SessionId $sessionval.SessionId
}


##Check for necessary prerequisites
if(Check-ForPrerequisites)
{
    Check-Arguments
    $hdbConnectionString = "Driver={HDBODBC};ServerNode=" + $HostAddress + ":3" + $InstanceNumber `
    + $DatabasePort + ";UID=" + $DatabaseUser + ";PWD=" + $script:DatabasePassword +";"
    ##Check the SAP HANA system type for multiDB or single tenant DB
    $SystemType = Check-SAPHANASystemType
    if($SystemType.VALUE -eq 'multidb')
    {
        $hdbConnectionString = "Driver={HDBODBC};ServerNode=" + $HostAddress + ":3" + `
        $InstanceNumber + "13;UID=" + $DatabaseUser + ";PWD=" + $script:DatabasePassword +";"
        $multiDB = $true
    }
    
   
    $instanceID =  Get-ODBCData -hanaConnectionString $hdbConnectionString -hdbsql $GetSAPHANAInstanceID
    $ShortMountPath = ((Get-ODBCData -hanaConnectionString $hdbConnectionString -hdbsql `
    $GetDataVolumeLocation).VALUE).Replace("/" + $instanceID.VALUE,"")
    $SerialNumber =  Get-VolumeSerialNumber -HostAddress $HostAddress -OSUser $OperatingSystemUser `
    -OSPassword $script:OperatingSystemPassword -DataVolumeMountPoint $ShortMountPath

    $catalog = Get-ODBCData -hanaConnectionString $hdbConnectionString -hdbsql $GetSAPHANACatalog

    $CatalogItems = @()
    for($i = 0; $i -lt $catalog.Count;$i++)
    {
        $CatalogObj = New-Object -TypeName psobject
        $CatalogObj | Add-Member -MemberType NoteProperty -Name CatalogID -Value ($i + 1)
        $CatalogObj | Add-Member -MemberType NoteProperty -Name BackupID -Value $catalog[$i].BACKUP_ID
        $CatalogObj | Add-Member -MemberType NoteProperty -Name Date -Value $catalog[$i].UTC_START_TIME
        $CatalogItems += $CatalogObj
    }

    $RestoreMenu = $true
    $MenuControlValue = 10
    $startValue = 0
    $OneTimeList = $MenuControlValue
    $ValidOptionsCatalog = 1..$CatalogItems.Count
    $ValidOPtionsNavigation = "n","p","q"
    $ValidOptionsRecovery = "y","n"
    while($RestoreMenu)
    {
        Clear-Host
        Write-Host "`n`t`t  ------------------------------------------ "
	    Write-Host "`t`t | SAP HANA Backup Catalog : Data Snapshots |"
        Write-Host "`t`t |      Select a Catalog ID to restore      |"
        Write-Host "`t`t  ------------------------------------------ "  
        Write-Host "`t  ------------  `t `t    ---------- `t`t  ------"
        Write-Host "`t | Catalog ID | `t `t   | BackupID |`t`t | Date |"
        Write-Host "`t  ------------  `t `t    ---------- `t`t  ------"

    
        for($i = $startValue; $i -lt $OneTimeList;$i++)
        {
            Write-Host "`t " $CatalogItems[$i].CatalogID " `t`t`t`t " $CatalogItems[$i].BackupID " `t " $CatalogItems[$i].Date 
        }

        $xMenuInput = Read-Host "`nInput Catalog ID or option `n""n"" for next page `n""p"" for previous page `n""q"" to quit `n-->"
        if ($xMenuInput -as [int])
        {
            if($ValidOptionsCatalog.Contains([int]$xMenuInput))
            {
                $recoverypoint = $CatalogItems[$xMenuInput -1]
                #Validate storage snap exists 
                
                $snapshot = Check-StorageSnapshot -FlashArrayAddress $PureFlashArrayAddress -User $PureFlashArrayUser -Password $script:PureFlashArrayPassword `
                -BackupID $recoverypoint.BackupID 
                if($snapshot -ne $null)
                {
                    Write-Host "`t`t ------------------------------------------------ " -ForegroundColor White
                    Write-host "`t`t|   Volume Snapshot is  present on the Array     |" -ForegroundColor White
                    Write-Host "`t`t ------------------------------------------------ " -ForegroundColor White
                    Start-Sleep -Seconds 2
                    Write-Host "`t`t ------------------------------------------------ " -ForegroundColor Red
                    Write-Host "`t`t|          This is a disruptive process!!!       | " -ForegroundColor Red
                    Write-host "`t`t| Do you want to proceed with the recovery ? y/n | " -ForegroundColor Red
                    Write-Host "`t`t ------------------------------------------------ " -ForegroundColor Red
                    $confirmedRecovery = $false
                    while(!$confirmedRecovery)
                    {
                        $x2MenuInput = Read-Host "`n-->"
                        if($ValidOptionsRecovery.Contains($x2MenuInput))
                        {
                            if($x2MenuInput -eq "y")
                            {
                                #Shutdown database and unmount data volume
                                Write-Host "`t`t ------------------------------------------------ " -ForegroundColor White
                                Write-host "`t`t|        Shutting down SAP HANA Instance         |" -ForegroundColor White
                                Write-Host "`t`t ------------------------------------------------ " -ForegroundColor White
                                Stop-SAPHANAInstance -HostAddress $HostAddress -OSUser $OperatingSystemUser `
                                -OSPassword $Script:OperatingSystemPassword -DataVolumeMountPoint $ShortMountPath 
                                #Restore or copy the snap to data volume.
                                $restoredVolume = $null
                                if($OverwriteVolume)
                                {
                                    #just overwite the volume with snap / restore to parent
                                    Write-Host "`t`t ------------------------------------------------ " -ForegroundColor White
                                    Write-host "`t`t|           Overwriting existing volume          |" -ForegroundColor White
                                    Write-host "`t`t|        Updating operating system storage       |" -ForegroundColor White
                                    Write-Host "`t`t ------------------------------------------------ " -ForegroundColor White
                                    $sucess = Restore-OverwiteVolume -FlashArrayAddress $PureFlashArrayAddress -User $PureFlashArrayUser `
                                    -Password $script:PureFlashArrayPassword -Snapshot $snapshot -HostAddress $HostAddress `
                                    -DataVolumeMountPoint $ShortMountPath `
                                    -OSUser $OperatingSystemUser -OSPassword $Script:OperatingSystemPassword -CurrentVolumeSerialNumber $SerialNumber
                                }
                                else
                                {
                                    #restore to a new volume , connect that volume to the host 
                                    Write-Host "`t`t ------------------------------------------------ " -ForegroundColor White
                                    Write-host "`t`t|           Copying volume from snapshot         |" -ForegroundColor White
                                    Write-host "`t`t|        Updating operating system storage       |" -ForegroundColor White
                                    Write-Host "`t`t ------------------------------------------------ " -ForegroundColor White
                                    $sucess = Restore-CopySnapToVolume -FlashArrayAddress $PureFlashArrayAddress -User $PureFlashArrayUser `
                                    -Password $script:PureFlashArrayPassword -Snapshot $snapshot -HostAddress $HostAddress `
                                    -DataVolumeMountPoint $ShortMountPath `
                                    -OSUser $OperatingSystemUser -OSPassword $Script:OperatingSystemPassword -BackupID $recoverypoint.BackupID `
                                    -SerialNumber $SerialNumber

                                }

                                if($sucess -ne $False)
                                {
                                    ###Restore SystemDB
                                    Write-Host "`t`t ------------------------------------------------ " -ForegroundColor White
                                    Write-host "`t`t|               Restoring SystemDB               |" -ForegroundColor White
                                    Write-Host "`t`t ------------------------------------------------ " -ForegroundColor White
                                    Restore-SystemDB -HostAddress $HostAddress -SID $instanceID

                                    Write-Host "`t`t ------------------------------------------------ " -ForegroundColor White
                                    Write-host "`t`t|               Starting Instance                |" -ForegroundColor White
                                    Write-Host "`t`t ------------------------------------------------ " -ForegroundColor White
                                    Check-RunningInstance -HostAddress $HostAddress -OSUser $OperatingSystemUser -OSPassword $script:OperatingSystemPassword
                                    ##Restore Tenants
                                     
                                    $Databases = Get-ODBCData -hanaConnectionString $hdbConnectionString -hdbsql $hdbGetTenantsToRestore
                                    foreach($database in $Databases)
                                    {
                                        Write-Host "`t`t ------------------------------------------------ " -ForegroundColor White
                                        Write-host "`t`t|           Restoring Tenant" $database.DATABASE_NAME "                |" -ForegroundColor White
                                        Write-Host "`t`t ------------------------------------------------ " -ForegroundColor White
                                        $hdbRestoreString = "RECOVER DATA FOR " + $database.DATABASE_NAME + "  USING SNAPSHOT  CLEAR LOG"
                                        Get-ODBCData -hanaConnectionString $hdbConnectionString -hdbsql $hdbRestoreString
                                        $RestoreMenu = $False
                                        $confirmedRecovery = $True
                                        Write-Host "`t`t ------------------------------------------------ " -ForegroundColor White
                                        Write-host "`t`t|                System Restored                 |" -ForegroundColor White
                                        Write-host "`t`t|         Remember to update /etc/fstab          |" -ForegroundColor White
                                        Write-Host "`t`t ------------------------------------------------ " -ForegroundColor White
                                    }
                                }
                                else
                                {
                                        Write-Host "`t`t ------------------------------------------------ " -ForegroundColor White
                                        Write-host "`t`t|                An Error has occured            |" -ForegroundColor White
                                        Write-host "`t`t|             Continue manual recovery           |" -ForegroundColor White
                                        Write-Host "`t`t ------------------------------------------------ " -ForegroundColor White
                                }
                            }
                            elseif($xMenuInput -eq "n")
                            {
                                Write-host "Returning to Catalog Selection"
                                Start-Sleep -Seconds 2
                            }
                        }
                        else
                        {
                            $x2MenuInput = Read-Host "`nInvlid Input , Try Again -->"
                        }
                    }
                    
                }
                else
                {
                    Write-Host "`t`t --------------------------------------------- " -ForegroundColor Red
                    Write-host "`t`t| Volume Snapshot is not present on the Array |" -ForegroundColor Red
                    Write-Host "`t`t --------------------------------------------- " -ForegroundColor Red
                    Start-Sleep -Seconds 5
                }
            }
        }
        elseif($ValidOPtionsNavigation.Contains($xMenuInput))
        {
            if($xMenuInput -eq "n")
            {
                $startValue = $startValue + $MenuControlValue
                $OneTimeList+= $MenuControlValue
                if(($startValue + $MenuControlValue) -gt $CatalogItems.Count)
                {
                    $startValue = 0
                    $OneTimeList = $MenuControlValue
                }
            }
            if($xMenuInput -eq "p")
            {
                $startValue = $startValue - $MenuControlValue
                $OneTimeList-= $MenuControlValue
                if($startValue -lt 0)
                {
                    $startValue = 0
                    $OneTimeList = $MenuControlValue
                }
            }
            if($xMenuInput -eq "q")
            {
                $RestoreMenu = $False
            }
            
        }
        else
        {
            Write-Host "Invalid Input"
            start-sleep -Seconds 3
        }
    }



}


