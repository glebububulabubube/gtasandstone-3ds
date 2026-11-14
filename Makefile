#---------------------------------------------------------------------------------
# gtasandstone — собственный 3D-движок под Old 3DS (ctrulib + citro3d)
# По каноническому шаблону devkitPro (3ds_rules) + доп. цель .cia через makerom.
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
DATA		:=	assets
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

export VPATH	:=	$(CURDIR) \
			$(foreach dir,$(SOURCES),$(CURDIR)/$(dir)) \
			$(foreach dir,$(DATA),$(CURDIR)/$(dir))

export DEPSDIR	:=	$(CURDIR)/$(BUILD)

CFILES		:=	$(foreach dir,$(SOURCES),$(notdir $(wildcard $(dir)/*.c)))
CPPFILES	:=	$(foreach dir,$(SOURCES),$(notdir $(wildcard $(dir)/*.cpp)))
SFILES		:=	$(foreach dir,$(SOURCES),$(notdir $(wildcard $(dir)/*.s)))
PICAFILES	:=	$(foreach dir,$(SOURCES),$(notdir $(wildcard $(dir)/*.v.pica)))
SHLISTFILES	:=	$(foreach dir,$(SOURCES),$(notdir $(wildcard $(dir)/*.shlist)))
BINFILES	:=	$(foreach dir,$(DATA),$(notdir $(wildcard $(dir)/*.*)))

ifeq ($(strip $(CPPFILES)),)
	export LD	:=	$(CC)
else
	export LD	:=	$(CXX)
endif

export OFILES_SOURCES := $(CPPFILES:.cpp=.o) $(CFILES:.c=.o) $(SFILES:.s=.o)
export OFILES_BIN	:=	$(addsuffix .o,$(BINFILES)) \
			$(PICAFILES:.v.pica=.shbin.o) $(SHLISTFILES:.shlist=.shbin.o)
export OFILES := $(OFILES_BIN) $(OFILES_SOURCES)

export HFILES := $(PICAFILES:.v.pica=_shbin.h) $(SHLISTFILES:.shlist=_shbin.h) \
			$(addsuffix .h,$(subst .,_,$(BINFILES)))

export INCLUDE	:=	$(foreach dir,$(INCLUDES),-I$(CURDIR)/$(dir)) \
			$(foreach dir,$(LIBDIRS),-I$(dir)/include) \
			-I$(CURDIR)/$(BUILD)

export LIBPATHS	:=	$(foreach dir,$(LIBDIRS),-L$(dir)/lib)

export _3DSXDEPS := $(if $(NO_SMDH),,$(OUTPUT).smdh)

ifeq ($(strip $(NO_SMDH)),)
	export _3DSXFLAGS += --smdh=$(CURDIR)/$(TARGET).smdh
endif

.PHONY: all clean cia

#---------------------------------------------------------------------------------
# верхняя цель: собирает .3dsx (через вложенный make в build/).
# .cia опционален (нужен установленный makerom); в CI делаем отдельно.
#---------------------------------------------------------------------------------
all: $(BUILD) $(DEPSDIR)
	@$(MAKE) --no-print-directory -C $(BUILD) -f $(CURDIR)/Makefile

#---------------------------------------------------------------------------------
# .cia: makerom упаковывает .elf(+smdh) в installable cia.
#---------------------------------------------------------------------------------
cia: $(OUTPUT).elf $(OUTPUT).smdh
	@echo "building .cia"
	@mkdir -p $(CURDIR)/ciabuild
	@cp $(CURDIR)/$(TARGET).elf $(CURDIR)/ciabuild/gta.elf
	@cp $(CURDIR)/$(TARGET).smdh $(CURDIR)/ciabuild/gta.smdh
	@if command -v makerom >/dev/null 2>&1; then \
		makerom -f cia -o $(CURDIR)/$(TARGET).cia -i $(CURDIR)/ciabuild/gta.elf:$(CURDIR)/ciabuild/gta.smdh; \
	else \
		echo "makerom не найден — .cia пропускается (собран только .3dsx)"; \
	fi
	@rm -rf $(CURDIR)/ciabuild

$(BUILD):
	@mkdir -p $@

$(DEPSDIR):
	@mkdir -p $@

clean:
	@echo clean ...
	@rm -fr $(BUILD) $(TARGET).3dsx $(TARGET).elf $(TARGET).smdh $(TARGET).cia

#---------------------------------------------------------------------------------
else
#---------------------------------------------------------------------------------

# сборка .3dsx целиком делегирована вложенному make (нижняя секция).
$(OUTPUT).3dsx	:	$(OUTPUT).elf $(_3DSXDEPS)

$(OUTPUT).elf	:	$(OFILES)
	@echo "linking $(notdir $@)"
	$(LD) $(LDFLAGS) $(OFILES) $(LIBPATHS) $(LIBS) -o $@

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
