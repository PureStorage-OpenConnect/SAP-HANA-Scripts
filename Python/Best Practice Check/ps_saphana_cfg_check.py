##################################################################################################
#                                                                                                #
#   Pure Storage Inc. (2024) SAP HANA operating system configuration check and applicator.       #
#            Works with Red Hat Enterprise Linux and SUSE Enterprise Linux.                      #       
#  Checks for and applies the recommended settings for persistent storage based on Pure Storage  # 
#                                   FlashArray block storage                                     #  
#                                                                                                #
##################################################################################################
import os
import json
import io
import time
import argparse

# Arguments are typically not needed but will be included for instances where a required 
# configuration is needed in a different deployment type such as mounting iSCSI volumes in a virtual machine
parser = argparse.ArgumentParser(description='Check and apply the best practices\
     for SAP HANA deployed on a number of platforms')
parser.add_argument('-n','--nohypervisor', help='Do not apply hypervisor specific settings.\
     Use this for in guest mounting', action="store_false", default=None)
args = parser.parse_args()
ignore_hypervisor_check = args.nohypervisor


# This is where the configuration files for the relevent operation systems will be found
# Files located here should be :
# rh8 = Red Hat Enterprise Linux version 8.x
# rh9 = Red Hat Enterprise Linux version 9.x
# sl15 = SUSE Eneterprise Linux version 15.x
cfg_file_path = "/opt/purestorage/saphana_toolkit/"

# This method helps to identify the relevant platform information and Operating System vendor and revision levels
# The "system-detect-virt" package is used to identify the platform type
# /etc/os-release is used to identify the vendor , major and minor operating system versions 
def get_platform_info():
    platform = "unknown"
    stream = os.popen("systemd-detect-virt")
    out = stream.read()
    parsedresponse = out.rstrip("\n")
    if(parsedresponse == "none"):
        platform = parsedresponse
    elif(parsedresponse == "vmware"):
        if(ignore_hypervisor_check is not None):
            print("This is a VMware virtual machine. No settings will be applied. Use saptune")
            platform = parsedresponse
        else:
            print("This is a VMware virtual machine but the hypervisor specific settings will be ignored")
            platform = "none"
    #This is a check for CBS based instances within Azure
    #elif(parsedresponse == "microsoft"):
    #        print("This is a Microsoft Azure virtual machine. Pure Storage specific settings will be applied.")
    #        platform = parsedresponse
    else:
        print("the system is a VM on an unsupported platform")
    stream = os.popen("cat /etc/os-release | grep CPE_NAME")
    out = stream.read()
    parsedresponse = out.rstrip("\"\n")
    parsedresponse = parsedresponse.lstrip("CPE_NAME=\"cpe:/o:")
    splitvendor = parsedresponse.split(":")
    if(splitvendor[1] == "sles-sap"):
        splitvendor[1] = "sles"
    system_configuration = {'platform':platform, \
        'vendor':splitvendor[0], 'distribution':splitvendor[1], 'major':splitvendor[2], 'minor':splitvendor[3]}
    return system_configuration

# This method matches the configuration returned in get_platfom_info() to a specific 
# configuration and returns the recommended settings to apply
def get_recommended_config(system_configuration):
    cfg_file = cfg_file_path + "configurations.json"
    with open(cfg_file) as config_file:
        config_list = json.load(config_file)
        for config_template in config_list:
            if(config_template.get("vendor") == system_configuration.get("vendor")):
                if(config_template.get("distribution") == system_configuration.get("distribution")):
                    if(config_template.get("major") == system_configuration.get("major")):
                        if(config_template.get("minor") == system_configuration.get("minor")):
                           system_settings = {'platform':system_configuration.get("platform"), \
                               'platform':system_configuration.get("platform"), "dm_blk_mq": config_template.get("dm_blk_mq"), \
                                   "scsi_blk_mq": config_template.get("scsi_blk_mq"), "scheduler": config_template.get("scheduler"), \
                                       "mpathconf": config_template.get("mpathconf") }
                           return system_settings
    
# The recommended configuration settings returned by get_recommended_config() are applied here 
# If recommended the bootloader options are altered to allow for a different IO scheduler
# If recommended the multipath configuration is applied
# If any changes are made to the bootloader then a reboot must take place

# for 1.0 we add support for CBS need to change the multipath parameter and the nvme_core.multipath parameter. The local boot disk also needs to be blacklisted. 
# multipath=on rootdelay=300 scsi_mod.use_blk_mq=1 USE_BY_UUID_DEVICE_NAMES=1 nvme_core.multipath=N

def apply_recommended_settings(settings):
    #First do the bootloader
    bootloader_rebuild = False
    #First step - check bootloader config 
    print("\n Checking kernel IO parameters \n")
    if(settings.get("scsi_blk_mq") == "true"):
        setting_applied_or_skipped = False
        while(setting_applied_or_skipped != True):
            confirm_scsi_mod = input("This will change the default IO Scheduler for SCSI devices, Confirm ? (y/n) -->: ")
            if(confirm_scsi_mod.lower() == "y"):
                reboot_needed = add_bootloader_cfg("scsi_mod.use_blk_mq=1")
                if(reboot_needed):
                    bootloader_rebuild = True
                    print("This system needs to be rebooted in order to load the blk_mq scheduler for SCSI devices")
                setting_applied_or_skipped = True
            elif(confirm_scsi_mod.lower() == "n"):
                print("Skipping IO scheduler change for SCSI devices")
                setting_applied_or_skipped = True
            else:
                print("Invalid response")
    if(settings.get("platform") == "none"):
        if(settings.get("dm_blk_mq") == "true"):
            setting_applied_or_skipped = False
            while(setting_applied_or_skipped != True):
                confirm_dm_mod = input("This will change the default IO Scheduler for DM devices, Confirm ? (y/n) -->: ")
                if(confirm_dm_mod.lower() == "y"):
                    reboot_needed = add_bootloader_cfg("dm_mod.use_blk_mq=y")
                    if(reboot_needed):
                        bootloader_rebuild = True
                        print("This system needs to be rebooted in order to load the blk_mq scheduler for DM devices")
                    setting_applied_or_skipped = True
                elif(confirm_dm_mod.lower() == "n"):
                    print("Skipping IO scheduler change for DM devices")
                    setting_applied_or_skipped = True
                else:
                    print("Invalid response")
    #If the platform is virtual then the global elevator needs to be set
    if(settings.get("platform") == "vmware"):
        setting_applied_or_skipped = False
        while(setting_applied_or_skipped != True):
            confirm_mod = input("This will change the default IO Scheduler system wide, Confirm ? (y/n) -->: ")
            if(confirm_mod.lower() == "y"):
                reboot_needed = add_bootloader_cfg("elevator=" + settings.get("scheduler"))
                if(reboot_needed):
                    bootloader_rebuild = True
                    print("This system needs to be rebooted in order to load the blk_mq scheduler system wide")
                setting_applied_or_skipped = True
            elif(confirm_mod.lower() == "n"):
                print("Skipping system wide IO Scheduler change")
                setting_applied_or_skipped = True
            else:
                print("Invalid response")
    
    # This could be a CBS instance connected to Microsoft Azure VM's or AWS EC2 VM's
    # Only Microsoft supported in 1.0
    if(settings.get("platform") == "microsoft"):
        setting_applied_or_skipped = False
        while(setting_applied_or_skipped != True):
            config_dmmpath_mod = input("This will change the device-mapper-multipathing from off to on, Confirm ? (y/n) -->: ")
            if(config_dmmpath_mod.lower() == "y"):
                reboot_needed = add_bootloader_cfg("multipath=on")
                if(reboot_needed):
                    bootloader_rebuild = True
                    print("This system needs to be rebooted in order to enable multipathing")
                setting_applied_or_skipped = True
            elif(config_dmmpath_mod.lower() == "n"):
                print("Skipping enabling multipathing module")
                setting_applied_or_skipped = True

    if(settings.get("platform") == "none"):
        #Second do multipath.conf
        print("\n Checking multipath and device rules configuration \n")
        add_multipath_cfg(settings.get("mpathconf"), "PURE", "FlashArray")
        #Finally set the udevadm values 
        set_udev_rules(settings)
        stream = os.popen("systemctl enable multipathd")
        stream = os.popen("systemctl start multipathd")
        stream = os.popen("systemctl restart multipathd")
        stream = os.popen("udevadm control --reload-rules && udevadm trigger")
        print("\n DONE! \n")
    elif (settings.get("platform") == "vmware"):
        print("\n  Skipping multipath and device rules configuration \n")


    #If any bootloader configurations have changed then the bootloadeer needs to be rebuilt
    if(bootloader_rebuild):
        print("\n Rebuilding bootloader \n")
        stream = os.popen("grub2-mkconfig -o /boot/grub2/grub.cfg")
        time.sleep(20)
        out = stream.read()
        print(out)
        reboot_prompt = input("The system needs to be rebooted , do you want to do this now ?, Confirm ? (y/n) -->: ")
        prompt_completed = False
        while(prompt_completed != True):
            if(reboot_prompt.lower() == "y"):
                reboot_timer = 15
                while(reboot_timer > 0):
                    print("The system will reboot in " + str(reboot_timer) + " seconds")
                    time.sleep(1)
                    reboot_timer = reboot_timer - 1
                prompt_completed = True
                stream = os.popen("reboot")
            elif(reboot_prompt.lower() == "n"):
                print("Best practice checks have been applied. Ensure this system is rebooted to apply bootloader changes")
                prompt_completed = True
            else:
                print("Invalid response")
            
# This method will apply the recommended udev configuration rules
# Any existing udev config rules for 99-pure-storage.rules will be removed first 
def set_udev_rules(config):
    udev_rules_file = "/etc/udev/rules.d/99-pure-storage.rules"
    if os.path.exists(udev_rules_file):
        os.remove(udev_rules_file)
    udev_config = list()
    udev_config.append("# Recommended settings for Pure Storage FlashArray.")
    udev_config.append("\n")
    udev_config.append("# Reduce CPU overhead due to entropy collection")
    udev_config.append("\n")
    udev_config.append("ACTION==\"add|change\", KERNEL==\"sd*[!0-9]\", SUBSYSTEM==\"block\", ENV{ID_VENDOR}==\"PURE\", ATTR{queue/add_random}=\"0\"")
    udev_config.append("\n")
    udev_config.append("ACTION==\"add|change\", KERNEL==\"dm-[0-9]*\", SUBSYSTEM==\"block\", ENV{DM_NAME}==\"3624a937*\", ATTR{queue/add_random}=\"0\"")
    udev_config.append("\n")
    udev_config.append("# Spread CPU load by redirecting completions to originating CPU")
    udev_config.append("\n")
    udev_config.append("ACTION==\"add|change\", KERNEL==\"sd*[!0-9]\", SUBSYSTEM==\"block\", ENV{ID_VENDOR}==\"PURE\", ATTR{queue/rq_affinity}=\"2\"")
    udev_config.append("\n")
    udev_config.append("ACTION==\"add|change\", KERNEL==\"dm-[0-9]*\", SUBSYSTEM==\"block\", ENV{DM_NAME}==\"3624a937*\", ATTR{queue/rq_affinity}=\"2\"")
    udev_config.append("\n")
    udev_config.append("# Set the HBA timeout to 60 seconds")
    udev_config.append("\n")
    udev_config.append("ACTION==\"add|change\", KERNEL==\"sd*[!0-9]\", SUBSYSTEM==\"block\", ENV{ID_VENDOR}==\"PURE\", ATTR{device/timeout}=\"60\"")
    udev_config.append("\n")
    udev_config.append("# Set HANA storage to be 512KB rather than 4MB max size")
    udev_config.append("\n")
    udev_config.append("ACTION==\"add|change\", KERNEL==\"sd*[!0-9]\", SUBSYSTEM==\"block\", ENV{ID_VENDOR}==\"PURE\", ATTR{queue/max_sectors_kb}=\"512\"")
    udev_config.append("\n")
    udev_config.append("ACTION==\"add|change\", KERNEL==\"dm-[0-9]*\", SUBSYSTEM==\"block\", ENV{DM_NAME}==\"3624a937*\", ATTR{queue/max_sectors_kb}=\"512\"")
    udev_config.append("\n")
    udev_config.append("# Set DM devices number of requests to 1024 for read performance")
    udev_config.append("\n")
    udev_config.append("ACTION==\"add|change\", KERNEL==\"dm-[0-9]*\", SUBSYSTEM==\"block\", ENV{DM_NAME}==\"3624a937*\", ATTR{queue/nr_requests}=\"1024\"")
    udev_config.append("\n")
    with open(udev_rules_file, 'w') as file:
            file.writelines(udev_config)

# With this method the multipath configuration file is parsed to find any existing Pure Storage SCSI block device configuration first
# ONLY the Pure Storage pieces are updated
# if no configuration file exists , a new one is created 
def add_multipath_cfg(config, vendor, product):
    multipath_config = "/etc/multipath.conf"
    mpath_config_file = cfg_file_path + config
    with open(mpath_config_file) as file:
            mpath_template = file.readlines()
    try :
        with open(multipath_config, 'r') as file:
            mpath_conf = file.readlines()
        linewatcher = 0
        new_mpath_conf = list()

        while(linewatcher < len(mpath_conf)):
            if("device {\n" in mpath_conf[linewatcher]):
                device_reader = list()
                line_device_track = linewatcher
                line_device_end = linewatcher
                vendor_found = False
                product_found = False
                device_end = False
                while(device_end != True):
                    if("}" not in mpath_conf[line_device_track]):
                        device_reader.append(mpath_conf[line_device_track])
                        if ("vendor" in mpath_conf[line_device_track]):
                            if(vendor in mpath_conf[line_device_track]):
                                vendor_found = True
                        if ("product" in mpath_conf[line_device_track]):
                            if(product in mpath_conf[line_device_track]):
                                product_found = True
                        line_device_track = line_device_track + 1
                    else:
                        device_reader.append(mpath_conf[line_device_track])
                        line_device_end = line_device_track
                        device_end = True
                if(vendor_found and product_found):
                    for new_line in mpath_template:
                        new_mpath_conf.append(new_line)
                    new_mpath_conf.append("\n")
                else:
                    for prop in device_reader:
                        new_mpath_conf.append(prop)
                linewatcher = line_device_end
            else:
                new_mpath_conf.append(mpath_conf[linewatcher])
            linewatcher = linewatcher + 1
        with open(multipath_config, 'w') as file:
            file.writelines(new_mpath_conf)
    except Exception:
        #the file does not exist , create a new one
        mpathconflist = list()
        mpath_conf_start = "devices {\n"
        mpathconflist.append(mpath_conf_start)
        for line in mpath_template:
            mpathconflist.append(line)
        mpath_conf_end = "\n}"
        mpathconflist.append(mpath_conf_end)
        with open(multipath_config, 'w') as file:
            file.writelines(mpathconflist)
            
# This method rebuilds the bootloader , if it is required
def add_bootloader_cfg(config):
    bootloader_changed = False
    grub_config = "/etc/default/grub"
    with open(grub_config, 'r') as file:
        grubconf = file.readlines()
    linewatcher = 0
    for line in grubconf:
        if(line.startswith('GRUB_CMDLINE_LINUX_DEFAULT')):
            parameters = line.rstrip("\"\n")
            parameters = parameters.lstrip("GRUB_CMDLINE_LINUX_DEFAULT=\"")
            parameterlist = parameters.split(" ")
            parameter_exists = False
            for param in parameterlist:
                if param == config:
                    parameter_exists = True
            if parameter_exists == False:
                new_parameters = line.rstrip("\"\n")
                new_parameters = new_parameters + " " + config + "\"\n"
                grubconf[linewatcher] = new_parameters
                bootloader_changed = True
        linewatcher = linewatcher + 1
    with open(grub_config, 'w') as file:
        file.writelines(grubconf)
    return bootloader_changed

system_info = get_platform_info()
settings = get_recommended_config(system_info)
apply_recommended_settings(settings)
