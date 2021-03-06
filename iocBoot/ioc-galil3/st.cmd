#!../galil-mc/bin/linux-x86_64/galil

< envPaths
< /epics/common/xf19id2-ioc1-netsetup.cmd

epicsEnvSet("PORT", "Galil")
#epicsEnvSet("GALIL_DEBUG_FILE", "/tmp/galil3_debug.txt")

dbLoadDatabase("$(TOP)/dbd/galil.dbd",0,0)
galil_registerRecordDeviceDriver(pdbbase)

# GalilCreateController command parameters are:
#
# 1. const char *portName 	- The name of the asyn port that will be created for this controller
# 2. const char *address 	- The address of the controller
# 3. double updatePeriod	- The time in ms between datarecords 2ms min, 200ms max.  Async if controller + bus supports it, otherwise is polled/synchronous.
#                       	- Recommend 50ms or less for ethernet
#                       	- Specify negative updatePeriod < 0 to force synchronous tcp poll period.  Otherwise will try async udp mode first

GalilCreateController("$(PORT)", "xf19id2-galil3.nsls2.bnl.local", 10)

# GalilCreateAxis command parameters are:
#
# 1. char *portName Asyn port for controller
# 2. char  axis A-H,
# 3. int   limits_as_home (0 off 1 on),
# 4. char  *Motor interlock digital port number 1 to 8 eg. "1,2,4".  1st 8 bits are supported
# 5. int   Interlock switch type 0 normally open, all other values is normally closed interlock switch type

# Beam Stop V
GalilCreateAxis("$(PORT)", "A", 1, "", 1)
# Beam Stop H
GalilCreateAxis("$(PORT)", "B", 1, "", 1)
# Beam Stop Z
GalilCreateAxis("$(PORT)", "C", 1, "", 1)
# Slit Beam Def Bottom
GalilCreateAxis("$(PORT)", "D", 1, "", 1)
# Slit Beam Def Top
GalilCreateAxis("$(PORT)", "E", 1, "", 1)
# Slit Beam Def Inboard
GalilCreateAxis("$(PORT)", "F", 1, "", 1)
# Slit Beam Def Outboard
GalilCreateAxis("$(PORT)", "G", 1, "", 1)


# GalilStartController command parameters are:
#
# 1. char *portName Asyn port for controller
# 2. char *code file(s) to deliver to the controller we are starting. "" = use generated code (recommended)
#             Specify a single file or to use templates use: headerfile;bodyfile1!bodyfile2!bodyfileN;footerfile
# 3. int   Burn program to EEPROM conditions
#             0 = transfer code if differs from eeprom, dont burn code to eeprom, then finally execute code thread 0
#             1 = transfer code if differs from eeprom, burn code to eeprom, then finally execute code thread 0
#             It is asssumed thread 0 starts all other required threads
# 4. int   Thread mask.  Check these threads are running after controller code start.  Bit 0 = thread 0 and so on
#             if thread mask < 0 nothing is checked
#             if thread mask = 0 and GalilCreateAxis appears > 0 then threads 0 to number of GalilCreateAxis is checked (good when using the generated code)

GalilStartController("$(PORT)", "$(TOP)/galil-config/19id-galil3.dmc", 0, 0)

dbLoadRecords("$(TOP)/db/galil3.db","PORT=$(PORT)")
dbLoadRecords("$(IOCSTATS)/db/iocAdminSoft.db", "IOC=XF:19IDC-ES{Galil:3}")



# Autosave configuration (pre-init)
save_restoreSet_Debug(0)

# status-PV prefix, so save_restore can find its status PV's.
save_restoreSet_status_prefix("XF:19IDC-ES{Galil:3}")

# Ok to save/restore save sets with missing values (no CA connection to PV)?
save_restoreSet_IncompleteSetsOk(1)
# Save dated backup files?
save_restoreSet_DatedBackupFiles(1)
# Number of sequenced backup files to write
save_restoreSet_NumSeqFiles(1)
# Time interval between sequenced backups
save_restoreSet_SeqPeriodInSeconds(300)
# specify where save files should be
set_savefile_path("$(TOP)", "as")

# specify what save files should be restored.  Note these files must be
# in the directory specified in set_savefile_path(), or, if that function
# has not been called, from the directory current when iocInit is invoked
# example: set_pass0_restoreFile("autosave_geiger.sav")

# specify directories in which to to search for included request files
# set_requestfile_path(${TOP}, "autosaveReqs")
set_requestfile_path("$(GALIL)/GalilSup/Db", "")
set_requestfile_path("$(MOTOR)/db", "")
set_requestfile_path("$(TOP)/iocBoot/$(IOC)", "")

dbLoadRecords("$(AUTOSAVE)/db/save_restoreStatus.db","P=XF:19IDC-ES{Galil:3}")

save_restoreSet_CAReconnect(1)

# restore settings in pass 0 so encoder ratio is set correctly for position restore in device support init
set_pass0_restoreFile("galil_settings.sav")
# restore positions in pass 0 so motors don't move
set_pass0_restoreFile("galil_positions.sav")

iocInit()

# Save motor positions every 5 seconds
create_monitor_set("galil_positions.req", 5, "")
# Save motor settings every 30 seconds
create_monitor_set("galil_settings.req", 30, "")

dbpf XF:19IDC-ES{Galil:3}ECATFLT_STATUS.SCAN "Passive"
