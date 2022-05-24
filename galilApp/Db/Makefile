TOP=../..
include $(TOP)/configure/CONFIG

# Build all substitutions file in this folder
DB += $(notdir $(patsubst %.substitutions,%.db,$(wildcard $(TOP)/galilApp/Db/*.substitutions)))

include $(TOP)/configure/RULES

