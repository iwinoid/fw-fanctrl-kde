PLASMOID_ID = com.github.iwinoid.fw-fanctrl-kde
SOURCE_DIR := $(CURDIR)
VERSION := $(shell python3 -c 'import json; print(json.load(open("metadata.json"))["KPlugin"]["Version"])' 2>/dev/null)
ARCHIVE = $(PLASMOID_ID)-$(VERSION).tar.xz
ARCHIVE_PATH = $(abspath ..)/$(ARCHIVE)

# Runtime files only. The release archive (and therefore `make install`, which
# installs from that archive) contains exactly these paths, so development
# files (docs, tests, image, Makefile, README, caches) can never leak into an
# installed plasmoid.
STAGE_DIR = tmp/package/$(PLASMOID_ID)
STAGE_TOP_FILES = metadata.json LICENSE
STAGE_DIRS = contents
STAGE_SCRIPTS = scripts/fw_helper.py

# XDG_DATA_HOME-aware install location (used by the uninstall fallback).
DATA_HOME = $(if $(XDG_DATA_HOME),$(XDG_DATA_HOME),$(HOME)/.local/share)
PLASMOID_DIR = $(DATA_HOME)/plasma/plasmoids/$(PLASMOID_ID)

# Set RESTART=y to restart the Plasma shell after install (default: n).
RESTART ?= n

ifeq ($(strip $(VERSION)),)
$(error "Version" is missing or empty in metadata.json)
endif

.PHONY: all install uninstall reinstall pack stage lint clean restart-plasma

all: install

# Build the release archive in the parent directory. The top-level directory
# is the plasmoid id, matching metadata.json (KPlugin.Id), not the repository
# checkout name.
pack: stage
	@echo "Packing $(PLASMOID_ID) $(VERSION)..."
	@tar -C tmp/package -cJf $(ARCHIVE_PATH) $(PLASMOID_ID)
	@rm -rf tmp/package
	@echo "✓ Packed to $(ARCHIVE_PATH)"

stage:
	@echo "Staging runtime files..."
	@rm -rf tmp/package
	@mkdir -p $(STAGE_DIR)/scripts
	@install -m 644 $(STAGE_TOP_FILES) $(STAGE_DIR)/
	@cp -a $(STAGE_DIRS) $(STAGE_DIR)/
	@install -m 755 $(STAGE_SCRIPTS) $(STAGE_DIR)/scripts/
	@find $(STAGE_DIR) \( -name '__pycache__' -o -name '*.pyc' -o -name '*~' \) \
		-print0 | xargs -0 -r rm -rf

# Install from the generated archive instead of the source tree: the archive is
# the runtime whitelist above, so a reinstall can never copy development files
# into the installation. `--upgrade` refreshes an existing installation;
# `--install` is only the first-install fallback. If both fail, print the real
# error and stop -- never silently fall back to copying the checkout.
install: pack
	@echo "Installing $(PLASMOID_ID) $(VERSION) from $(ARCHIVE)..."
	@if kpackagetool6 --type=Plasma/Applet --upgrade $(ARCHIVE_PATH) >tmp/install-error.log 2>&1; then \
		echo "✓ Upgraded the existing installation."; \
	elif kpackagetool6 --type=Plasma/Applet --install $(ARCHIVE_PATH) >>tmp/install-error.log 2>&1; then \
		echo "✓ Installed."; \
	else \
		echo "✗ kpackagetool6 could not install $(ARCHIVE):"; \
		cat tmp/install-error.log; \
		rm -f tmp/install-error.log; \
		exit 1; \
	fi
	@rm -f tmp/install-error.log
	@if [ "$(RESTART)" = "y" ]; then \
		$(MAKE) restart-plasma; \
	else \
		echo "  Plasma shell not restarted (RESTART=$(RESTART)). Run 'make restart-plasma' when ready."; \
	fi

# plasmashell is managed by the systemd user unit plasma-plasmashell.service;
# restart it through systemd so the new process stays supervised. Only if that
# fails, fall back to kquitapp6, and wait until the old process is really gone
# before starting a new one.
restart-plasma:
	@echo "Restarting Plasma shell..."
	@if systemctl --user restart plasma-plasmashell.service 2>/dev/null; then \
		echo "✓ plasma-plasmashell.service restarted."; \
	else \
		echo "systemd unit restart failed; falling back to kquitapp6..."; \
		kquitapp6 plasmashell 2>/dev/null || true; \
		for i in $$(seq 1 50); do \
			pgrep -u $$(id -u) -x plasmashell >/dev/null || break; \
			sleep 0.2; \
		done; \
		if pgrep -u $$(id -u) -x plasmashell >/dev/null; then \
			echo "✗ plasmashell did not exit; not starting another instance."; \
			exit 1; \
		fi; \
		systemctl --user start plasma-plasmashell.service 2>/dev/null || \
			(setsid plasmashell --no-respawn >/dev/null 2>&1 &); \
		echo "✓ Plasma shell restarted."; \
	fi

uninstall:
	@echo "Removing $(PLASMOID_ID)..."
	@kpackagetool6 --type=Plasma/Applet --remove $(PLASMOID_ID) 2>&1 || \
		rm -rf $(PLASMOID_DIR)
	@echo "✓ Plasmoid uninstalled."

reinstall:
	@$(MAKE) uninstall
	@$(MAKE) install

# Same strict qmllint pipeline as CI (see .github/check-qmllint.py).
lint:
	@python3 .github/check-qmllint.py

clean:
	@find . -path ./.git -prune -o \
		\( -name '*~' -o -name '*.pyc' -o -name '__pycache__' \) \
		-print0 | xargs -0 -r rm -rf 2>/dev/null || true
	@rm -rf tmp/package tmp/install-error.log
	@echo "✓ Cleaned up temp files."
