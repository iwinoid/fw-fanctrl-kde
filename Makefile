PLASMOID_ID = org.fw-fanctrl.plasmoid
SOURCE_DIR = $(CURDIR)
PKG_DIR = $(notdir $(SOURCE_DIR))

# Set RESTART=y to auto-restart Plasma after install/reinstall (default: y)
RESTART ?= y

.PHONY: all install uninstall reinstall pack clean restart-plasma

all: install

restart-plasma:
	@echo "Restarting Plasma shell..."
	@kquitapp6 plasmashell 2>/dev/null || true
	@sleep 1
	@plasmashell &>/dev/null &
	@sleep 2
	@echo "✓ Plasma shell restarted."

install:
	@echo "Installing $(PLASMOID_ID)..."
	@kpackagetool6 --type=Plasma/Applet --install "$(SOURCE_DIR)" 2>&1 || \
		( echo "Trying legacy install..." && \
		  mkdir -p $(HOME)/.local/share/plasma/plasmoids/$(PLASMOID_ID) && \
		  cp -r ./* $(HOME)/.local/share/plasma/plasmoids/$(PLASMOID_ID)/ )
	@chmod +x $(HOME)/.local/share/plasma/plasmoids/$(PLASMOID_ID)/scripts/fw_helper.py
	@echo "✓ $(PLASMOID_ID) installed!"
	@if [ "$(RESTART)" = "y" ]; then \
		$(MAKE) restart-plasma; \
	else \
		echo "  Run 'make restart-plasma' to restart Plasma shell."; \
	fi

uninstall:
	@echo "Removing $(PLASMOID_ID)..."
	@kpackagetool6 --type=Plasma/Applet --remove "$(PLASMOID_ID)" 2>&1 || \
		rm -rf $(HOME)/.local/share/plasma/plasmoids/$(PLASMOID_ID)
	@echo "✓ Plasmoid uninstalled."

reinstall:
	@$(MAKE) uninstall
	@$(MAKE) install

pack:
	@echo "Packing $(PLASMOID_ID) for distribution..."
	@cd .. && tar --exclude-vcs --exclude='.Rhistory' --exclude='__pycache__' --exclude='*.pyc' -czf $(PLASMOID_ID).tar.gz $(PKG_DIR)/
	@echo "✓ Packed to ../$(PLASMOID_ID).tar.gz"

clean:
	@find . \( -name '*~' -o -name '*.pyc' -o -name '__pycache__' \) -print0 | xargs -0 -r rm -rf 2>/dev/null || true
	@echo "✓ Cleaned up temp files."
