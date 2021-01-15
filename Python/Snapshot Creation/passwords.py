##################################################################################################
#                                                                                                #
#             Pure Storage Inc. (2021) SAP HANA Snapshot password helper classes                 # 
#                                                                                                #
##################################################################################################

import getpass

class DB_Password:

    DEFAULT_DB_Password = 'Prompt if not specified'
    def __init__(self, value):
        if value == self.DEFAULT_DB_Password:
            value = getpass.getpass('Database Password: ')
        self.value = value

    def __str__(self):
        return self.value

class OS_Password:

    DEFAULT_OS_Password = 'Prompt if not specified'
    def __init__(self, value):
        if value == self.DEFAULT_OS_Password:
            value = getpass.getpass('Operating System Password: ')
        self.value = value

    def __str__(self):
        return self.value

class SID_Password:

    DEFAULT_DB_SID_Password = 'Prompt if not specified'
    def __init__(self, value):
        if value == self.DEFAULT_DB_SID_Password:
            value = getpass.getpass('Database <sid>adm user Password: ')
        self.value = value

    def __str__(self):
        return self.value

class vCenter_Password:

    DEFAULT_vCenter_Password = 'Prompt if not specified'
    def __init__(self, value):
        if value == self.DEFAULT_vCenter_Password:
            value = getpass.getpass('vCenter Password (Leave blank if not required): ')
        self.value = value

    def __str__(self):
        return self.value

class FlashArray_Password:

    DEFAULT_FlashArray_Password = 'Prompt if not specified'
    def __init__(self, value):
        if value == self.DEFAULT_FlashArray_Password:
            value = getpass.getpass('FlashArray Password: ')
        self.value = value

    def __str__(self):
        return self.value