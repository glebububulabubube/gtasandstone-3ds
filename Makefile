#---------------------------------------------------------------------------------
# gtasandstone — собственный 3D-движок под Old 3DS (ctrulib + citro3d)
# Стандартный шаблон devkitPro: 3ds_rules сам компилит .v.pica -> _shbin.h,
# собирает .3dsx и .smdh. Здесь дополнительно делаем .cia через makerom.
#---------------------------------------------------------------------------------
.SUFFIXES:

ifeq ($(strip $(DEVKITARM)),)
$(error "Please set DEVKITARM in your environment. export DEVKITARM=<path to>devkitARM")
endif

TOPDIR ?= $(CURDIR)
include $(DEVKITARM)/3ds_rules

#---------------------------------------------------------------------------------
TARGET		:=	gtasandstone
BUILD		:=	build
SOURCES		:=	source
DATA		:=
GRAPHICS	:=
INCLUDES	:=	include

APP_TITLE		:=	GTA Sandstone
APP_DESCRIPTION	:=	Own 3D engine: walk/jump/run
APP_AUTHOR		:=	Gleb

#---------------------------------------------------------------------------------
ARCH	:=	-march=armv6k -mtune=mpcore -mfloat-abi=hard -mtp=soft

CFLAGS	:=	-g -Wall -Wextra -O2 -mword-relocations -ffunction-sections \
			$(ARCH) $(INCLUDE) -D__3DS__

CXXFLAGS	:=	$(CFLAGS) -fno-rtti -fno-exceptions -std=gnu++11

ASFLAGS	:=	-g $(ARCH)
LDFLAGS	=	-specs=3dsx.specs -g $(ARCH) -Wl,-Map,$(notdir $*.map)

LIBS	:=	-lcitro3d -lctru -lm

LIBDIRS	:=	$(CTRULIB) $(CT3K)

#---------------------------------------------------------------------------------
ifneq ($(BUILD),$(notdir $(CURDIR)))
#---------------------------------------------------------------------------------

export OUTPUT	:=	$(CURDIR)/$(TARGET)
export TOPDIR	:=	$(CURDIR)

export VPATH	:=	$(foreach dir,$(SOURCES),$(CURDIR)/$(dir)) \
			$(foreach dir,$(DATA),$(CURDIR)/$(dir)) \
			$(foreach dir,$(GRAPHICS),$(CURDIR)/$(dir))

export DEPSDIR	:=	$(CURDIR)/$(BUILD)

CFILES		:=	$(foreach dir,$(SOURCES),$(notdir $(wildcard $(dir)/*.c)))
CPPFILES	:=	$(foreach dir,$(SOURCES),$(notdir $(wildcard $(dir)/*.cpp)))
SFILES		:=	$(foreach dir,$(SOURCES),$(notdir $(wildcard $(dir)/*.s)))
PICAFILES	:=	$(foreach dir,$(SOURCES),$(notdir $(wildcard $(dir)/*.v.pica)))
SHLISTFILES	:=	$(foreach dir,$(SOURCES),$(notdir $(wildcard $(dir)/*.shlist)))
GFXFILES	:=	$(foreach dir,$(GRAPHICS),$(notdir $(wildcard $(dir)/*.t3s)))
BINFILES	:=	$(foreach dir,$(DATA),$(notdir $(wildcard $(dir)/*.*)))

ifeq ($(strip $(CPPFILES)),)
	export LD	:=	$(CC)
else
	export LD	:=	$(CXX)
endif

export OFILES_SOURCES := $(CPPFILES:.cpp=.o) $(CFILES:.c=.o) $(SFILES:.s=.o)
export OFILES_BIN	:=	$(addsuffix .o,$(BINFILES)) \
			$(PICAFILES:.v.pica=.shbin.o) $(SHLISTFILES:.shlist=.shbin.o) \
			$(addsuffix .o,$(T3XFILES))
export OFILES := $(OFILES_BIN) $(OFILES_SOURCES)

export HFILES := $(PICAFILES:.v.pica=_shbin.h) $(SHLISTFILES:.shlist=_shbin.h) \
			$(addsuffix .h,$(subst .,_,$(BINFILES))) $(GFXFILES:.t3s=.h)

export INCLUDE	:=	$(foreach dir,$(INCLUDES),-I$(CURDIR)/$(dir)) \
			$(foreach dir,$(LIBDIRS),-I$(dir)/include) \
			-I$(CURDIR)/$(BUILD)

export LIBPATHS	:=	$(foreach dir,$(LIBDIRS),-L$(dir)/lib)

export _3DSXDEPS := $(if $(NO_SMDH),,$(OUTPUT).smdh)

ifeq ($(strip $(NO_SMDH)),)
	export _3DSXFLAGS += --smdh=$(CURDIR)/$(TARGET).smdh
endif

.PHONY: all clean

all: $(BUILD) $(DEPSDIR)
	@$(MAKE) --no-print-directory -C $(BUILD) -f $(CURDIR)/Makefile
	@$(MAKE) --no-print-directory -C $(CURDIR) cia

$(BUILD):
	@mkdir -p $@

$(DEPSDIR):
	@mkdir -p $@

# .cia: упаковываем из готового .elf + .smdh через makerom
cia: $(OUTPUT).elf $(OUTPUT).smdh
	@echo "\033[32mbuilding .cia\033[0m"
	@mkdir -p $(CURDIR)/ciabuild
	@cp $(OUTPUT).elf $(CURDIR)/ciabuild/gta.elf
	@cp $(OUTPUT).smdh $(CURDIR)/ciabuild/gta.smdh
	@makerom -f cia -o $(CURDIR)/$(TARGET).cia -i $(CURDIR)/ciabuild/gta.elf:$(CURDIR)/ciabuild/gta.smdh
	@rm -rf $(CURDIR)/ciabuild

clean:
	@echo clean ...
	@rm -fr $(BUILD) $(TARGET).3dsx $(TARGET).elf $(TARGET).smdh $(TARGET).cia

#---------------------------------------------------------------------------------
else
#---------------------------------------------------------------------------------

.DEFAULT_GOAL := all

$(OUTPUT).3dsx	:	$(OUTPUT).elf $(_3DSXDEPS)
$(OUTPUT).elf	:	$(OFILES)
$(OFILES_SOURCES) : $(HFILES)

%.bin.o	%_bin.h :	%.bin
	$(bin2o)

%.shbin.o %_shbin.h : %.shbin
	$(SILENTMSG) $(notdir $<)
	$(bin2o)

-include $(DEPSDIR)/*.d

#---------------------------------------------------------------------------------
endif
#---------------------------------------------------------------------------------