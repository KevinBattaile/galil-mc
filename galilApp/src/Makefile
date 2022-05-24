TOP=../..

include $(TOP)/configure/CONFIG

PROD_IOC = galil
DBD += galil.dbd

galil_DBD += base.dbd
galil_DBD += asyn.dbd motorSupport.dbd calcSupport.dbd devIocStats.dbd asSupport.dbd
galil_DBD += GalilSupport.dbd

galil_LIBS += asyn motor calc devIocStats autosave
galil_LIBS += GalilSupport

galil_SRCS += galil_registerRecordDeviceDriver.cpp
galil_SRCS += galilMain.cpp

galil_LIBS += $(EPICS_BASE_IOC_LIBS)


include $(TOP)/configure/RULES

