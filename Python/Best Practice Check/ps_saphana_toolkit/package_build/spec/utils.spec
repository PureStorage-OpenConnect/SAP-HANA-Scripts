###############################################################################
# Spec file for Utils
################################################################################
# Configured to be built by user student or other non-root user
################################################################################
#
Summary: Pure Storage SAP HANA Toolkit
Name: ps_saphana_toolkit
Version: 0.0.1
Release: 1
License: GPL
URL: https://www.purestorage.com/
Group: System
Packager: Andrew Sillifant
Requires: python3
BuildRoot: ~/rpmbuild/

# Build with the following syntax:
# rpmbuild --target noarch -bb utils.spec

%description
The Pure Storage SAP HANA toolkit containing important tools for storage interop

%prep
################################################################################
# Create the build tree and copy the files from the development directories    #
# into the build tree.                                                         #
################################################################################
echo "BUILDROOT = $RPM_BUILD_ROOT"
mkdir -p $RPM_BUILD_ROOT/opt/purestorage/saphana_toolkit/
mkdir -p $RPM_BUILD_ROOT/usr/local/share/utils/saphana_toolkit/
rm -rf /opt/build/ps_saphana_toolkit/package_build/code/*
#rm /opt/build/ps_saphana_toolkit/development/dist/ps_saphana_cfg_check
cd /opt/build/ps_saphana_toolkit/development
pyinstaller --onefile ps_saphana_cfg_check.py
cp /opt/build/ps_saphana_toolkit/development/dist/* /opt/build/ps_saphana_toolkit/package_build/code/


cp /opt/build/ps_saphana_toolkit/package_build/code/* $RPM_BUILD_ROOT/opt/purestorage/saphana_toolkit/
cp /opt/build/ps_saphana_toolkit/package_build/license/* $RPM_BUILD_ROOT/usr/local/share/utils/saphana_toolkit
cp /opt/build/ps_saphana_toolkit/package_build/spec/* $RPM_BUILD_ROOT/usr/local/share/utils/saphana_toolkit

exit

%files
%attr(0744, root, root) /opt/purestorage/saphana_toolkit/*
%attr(0644, root, root) /usr/local/share/utils/saphana_toolkit/*

%pre
mkdir -p /opt/purestorage/saphana_toolkit

%post
################################################################################
# Set up binaries and directories                                             #
################################################################################


ln -s /opt/purestorage/saphana_toolkit/ps_saphana_cfg_check /usr/local/bin/


%preun
rm /usr/local/bin/ps_saphana_cfg_check

%postun
rm -rf /opt/purestorage/saphana_toolkit

%clean
rm -rf $RPM_BUILD_ROOT/opt/purestorage/saphana_toolkit
rm -rf $RPM_BUILD_ROOT/usr/local/share/utils/saphana_toolkit

%changelog
* Wed Aug 29 2018 Your Name <Youremail@yourdomain.com>
  - The original package includes several useful scripts. it is
    primarily intended to be used to illustrate the process of
    building an RPM.
