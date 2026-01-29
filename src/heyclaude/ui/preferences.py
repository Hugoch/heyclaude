"""Preferences window using PyObjC."""

import logging
import threading

import objc
from AppKit import (
    NSAlert,
    NSAlertFirstButtonReturn,
    NSApp,
    NSBackingStoreBuffered,
    NSBezelStyleRounded,
    NSButton,
    NSComboBox,
    NSFont,
    NSLayoutAttributeBottom,
    NSLayoutAttributeCenterY,
    NSLayoutAttributeLeading,
    NSLayoutAttributeTop,
    NSLayoutAttributeTrailing,
    NSLayoutAttributeWidth,
    NSLayoutConstraint,
    NSLayoutRelationEqual,
    NSMakeRect,
    NSObject,
    NSOffState,
    NSOnState,
    NSPopUpButton,
    NSSecureTextField,
    NSSlider,
    NSStackView,
    NSSwitchButton,
    NSTabView,
    NSTabViewItem,
    NSTextField,
    NSTextFieldCell,
    NSUserInterfaceLayoutOrientationVertical,
    NSView,
    NSWindow,
    NSWindowStyleMaskClosable,
    NSWindowStyleMaskMiniaturizable,
    NSWindowStyleMaskTitled,
)
from Foundation import NSMakeRect

from ..config import get_config
from ..telegram_bot import test_telegram_connection_sync

logger = logging.getLogger(__name__)


class PreferencesWindowController(NSObject):
    """Controller for the preferences window."""

    window = objc.ivar()
    config = objc.ivar()
    on_config_changed = objc.ivar()

    def initWithConfig_(self, config):
        self = objc.super(PreferencesWindowController, self).init()
        if self is None:
            return None

        self.config = config
        self.on_config_changed = None
        self._create_window()
        return self

    def _create_window(self):
        """Create the preferences window."""
        style = (
            NSWindowStyleMaskTitled
            | NSWindowStyleMaskClosable
            | NSWindowStyleMaskMiniaturizable
        )

        self.window = NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
            NSMakeRect(0, 0, 500, 400),
            style,
            NSBackingStoreBuffered,
            False,
        )
        self.window.setTitle_("HeyClaude Preferences")
        self.window.center()

        tab_view = NSTabView.alloc().initWithFrame_(NSMakeRect(20, 20, 460, 360))

        general_tab = self._create_general_tab()
        tab_view.addTabViewItem_(general_tab)

        macos_tab = self._create_macos_tab()
        tab_view.addTabViewItem_(macos_tab)

        telegram_tab = self._create_telegram_tab()
        tab_view.addTabViewItem_(telegram_tab)

        advanced_tab = self._create_advanced_tab()
        tab_view.addTabViewItem_(advanced_tab)

        self.window.contentView().addSubview_(tab_view)

    def _create_label(self, text: str, frame) -> NSTextField:
        """Create a label text field."""
        label = NSTextField.alloc().initWithFrame_(frame)
        label.setStringValue_(text)
        label.setBezeled_(False)
        label.setDrawsBackground_(False)
        label.setEditable_(False)
        label.setSelectable_(False)
        return label

    def _create_general_tab(self) -> NSTabViewItem:
        """Create the General tab."""
        tab = NSTabViewItem.alloc().initWithIdentifier_("general")
        tab.setLabel_("General")

        view = NSView.alloc().initWithFrame_(NSMakeRect(0, 0, 440, 300))

        y = 250

        launch_label = self._create_label("Launch at Login:", NSMakeRect(20, y, 150, 20))
        view.addSubview_(launch_label)

        self.launch_checkbox = NSButton.alloc().initWithFrame_(NSMakeRect(180, y, 200, 20))
        self.launch_checkbox.setButtonType_(NSSwitchButton)
        self.launch_checkbox.setTitle_("")
        self.launch_checkbox.setState_(
            NSOnState if self.config.launch_at_login else NSOffState
        )
        self.launch_checkbox.setTarget_(self)
        self.launch_checkbox.setAction_(objc.selector(self.launchAtLoginChanged_, signature=b"v@:@"))
        view.addSubview_(self.launch_checkbox)

        y -= 40

        port_label = self._create_label("Server Port:", NSMakeRect(20, y, 150, 20))
        view.addSubview_(port_label)

        self.port_field = NSTextField.alloc().initWithFrame_(NSMakeRect(180, y, 100, 24))
        self.port_field.setStringValue_(str(self.config.server_port))
        view.addSubview_(self.port_field)

        y -= 60

        hook_label = self._create_label("Hook Status:", NSMakeRect(20, y, 150, 20))
        view.addSubview_(hook_label)

        self.hook_status = self._create_label("Not installed", NSMakeRect(180, y, 150, 20))
        view.addSubview_(self.hook_status)

        install_btn = NSButton.alloc().initWithFrame_(NSMakeRect(180, y - 30, 120, 30))
        install_btn.setTitle_("Install Hook")
        install_btn.setBezelStyle_(NSBezelStyleRounded)
        install_btn.setTarget_(self)
        install_btn.setAction_(objc.selector(self.installHook_, signature=b"v@:@"))
        view.addSubview_(install_btn)

        self._update_hook_status()

        tab.setView_(view)
        return tab

    def _create_macos_tab(self) -> NSTabViewItem:
        """Create the macOS Notifications tab."""
        tab = NSTabViewItem.alloc().initWithIdentifier_("macos")
        tab.setLabel_("macOS")

        view = NSView.alloc().initWithFrame_(NSMakeRect(0, 0, 440, 300))

        y = 250

        enabled_label = self._create_label("Enable Notifications:", NSMakeRect(20, y, 150, 20))
        view.addSubview_(enabled_label)

        self.macos_enabled = NSButton.alloc().initWithFrame_(NSMakeRect(180, y, 200, 20))
        self.macos_enabled.setButtonType_(NSSwitchButton)
        self.macos_enabled.setTitle_("")
        self.macos_enabled.setState_(
            NSOnState if self.config.macos_enabled else NSOffState
        )
        self.macos_enabled.setTarget_(self)
        self.macos_enabled.setAction_(objc.selector(self.macosEnabledChanged_, signature=b"v@:@"))
        view.addSubview_(self.macos_enabled)

        y -= 40

        sound_label = self._create_label("Sound:", NSMakeRect(20, y, 150, 20))
        view.addSubview_(sound_label)

        self.sound_popup = NSPopUpButton.alloc().initWithFrame_pullsDown_(
            NSMakeRect(180, y, 150, 26), False
        )
        sounds = ["Ping", "Basso", "Blow", "Bottle", "Frog", "Funk", "Glass", "Hero", "Pop", "Submarine"]
        for sound in sounds:
            self.sound_popup.addItemWithTitle_(sound)
        self.sound_popup.selectItemWithTitle_(self.config.macos_sound)
        self.sound_popup.setTarget_(self)
        self.sound_popup.setAction_(objc.selector(self.soundChanged_, signature=b"v@:@"))
        view.addSubview_(self.sound_popup)

        y -= 40

        terminal_label = self._create_label("Terminal App:", NSMakeRect(20, y, 150, 20))
        view.addSubview_(terminal_label)

        self.terminal_popup = NSPopUpButton.alloc().initWithFrame_pullsDown_(
            NSMakeRect(180, y, 150, 26), False
        )
        terminals = ["iTerm", "Terminal", "Warp", "Alacritty", "Kitty", "auto"]
        for term in terminals:
            self.terminal_popup.addItemWithTitle_(term)
        self.terminal_popup.selectItemWithTitle_(self.config.terminal_app)
        self.terminal_popup.setTarget_(self)
        self.terminal_popup.setAction_(objc.selector(self.terminalChanged_, signature=b"v@:@"))
        view.addSubview_(self.terminal_popup)

        tab.setView_(view)
        return tab

    def _create_telegram_tab(self) -> NSTabViewItem:
        """Create the Telegram tab."""
        tab = NSTabViewItem.alloc().initWithIdentifier_("telegram")
        tab.setLabel_("Telegram")

        view = NSView.alloc().initWithFrame_(NSMakeRect(0, 0, 440, 300))

        y = 250

        enabled_label = self._create_label("Enable Telegram:", NSMakeRect(20, y, 150, 20))
        view.addSubview_(enabled_label)

        self.telegram_enabled = NSButton.alloc().initWithFrame_(NSMakeRect(180, y, 200, 20))
        self.telegram_enabled.setButtonType_(NSSwitchButton)
        self.telegram_enabled.setTitle_("")
        self.telegram_enabled.setState_(
            NSOnState if self.config.telegram_enabled else NSOffState
        )
        self.telegram_enabled.setTarget_(self)
        self.telegram_enabled.setAction_(objc.selector(self.telegramEnabledChanged_, signature=b"v@:@"))
        view.addSubview_(self.telegram_enabled)

        y -= 40

        token_label = self._create_label("Bot Token:", NSMakeRect(20, y, 150, 20))
        view.addSubview_(token_label)

        self.token_field = NSSecureTextField.alloc().initWithFrame_(NSMakeRect(180, y, 230, 24))
        self.token_field.setStringValue_(self.config.telegram_bot_token)
        view.addSubview_(self.token_field)

        y -= 40

        chat_label = self._create_label("Chat ID:", NSMakeRect(20, y, 150, 20))
        view.addSubview_(chat_label)

        self.chat_field = NSTextField.alloc().initWithFrame_(NSMakeRect(180, y, 150, 24))
        self.chat_field.setStringValue_(self.config.telegram_chat_id)
        view.addSubview_(self.chat_field)

        y -= 40

        test_btn = NSButton.alloc().initWithFrame_(NSMakeRect(180, y, 150, 30))
        test_btn.setTitle_("Test Connection")
        test_btn.setBezelStyle_(NSBezelStyleRounded)
        test_btn.setTarget_(self)
        test_btn.setAction_(objc.selector(self.testTelegram_, signature=b"v@:@"))
        view.addSubview_(test_btn)

        y -= 50

        context_label = self._create_label("Include Context:", NSMakeRect(20, y, 150, 20))
        view.addSubview_(context_label)

        self.context_checkbox = NSButton.alloc().initWithFrame_(NSMakeRect(180, y, 200, 20))
        self.context_checkbox.setButtonType_(NSSwitchButton)
        self.context_checkbox.setTitle_("")
        self.context_checkbox.setState_(
            NSOnState if self.config.telegram_include_context else NSOffState
        )
        self.context_checkbox.setTarget_(self)
        self.context_checkbox.setAction_(objc.selector(self.contextChanged_, signature=b"v@:@"))
        view.addSubview_(self.context_checkbox)

        y -= 40

        lines_label = self._create_label("Context Lines:", NSMakeRect(20, y, 150, 20))
        view.addSubview_(lines_label)

        self.lines_slider = NSSlider.alloc().initWithFrame_(NSMakeRect(180, y, 150, 24))
        self.lines_slider.setMinValue_(5)
        self.lines_slider.setMaxValue_(50)
        self.lines_slider.setIntValue_(self.config.telegram_context_lines)
        self.lines_slider.setTarget_(self)
        self.lines_slider.setAction_(objc.selector(self.linesChanged_, signature=b"v@:@"))
        view.addSubview_(self.lines_slider)

        self.lines_value = self._create_label(
            str(self.config.telegram_context_lines), NSMakeRect(340, y, 40, 20)
        )
        view.addSubview_(self.lines_value)

        tab.setView_(view)
        return tab

    def _create_advanced_tab(self) -> NSTabViewItem:
        """Create the Advanced tab."""
        tab = NSTabViewItem.alloc().initWithIdentifier_("advanced")
        tab.setLabel_("Advanced")

        view = NSView.alloc().initWithFrame_(NSMakeRect(0, 0, 440, 300))

        y = 250

        all_notif_label = self._create_label("All Notifications:", NSMakeRect(20, y, 150, 20))
        view.addSubview_(all_notif_label)

        self.all_notif_checkbox = NSButton.alloc().initWithFrame_(NSMakeRect(180, y, 20, 20))
        self.all_notif_checkbox.setButtonType_(NSSwitchButton)
        self.all_notif_checkbox.setTitle_("")
        self.all_notif_checkbox.setState_(
            NSOnState if self.config.all_notifications else NSOffState
        )
        self.all_notif_checkbox.setTarget_(self)
        self.all_notif_checkbox.setAction_(objc.selector(self.allNotificationsChanged_, signature=b"v@:@"))
        view.addSubview_(self.all_notif_checkbox)

        hint_label = self._create_label("Instant, not just idle", NSMakeRect(210, y, 200, 20))
        hint_label.setTextColor_(NSTextField.alloc().init().textColor().colorWithAlphaComponent_(0.6))
        view.addSubview_(hint_label)

        y -= 30

        reinstall_note = self._create_label("(Reinstall hook after changing)", NSMakeRect(180, y, 250, 16))
        reinstall_note.setTextColor_(NSTextField.alloc().init().textColor().colorWithAlphaComponent_(0.4))
        from AppKit import NSFont
        reinstall_note.setFont_(NSFont.systemFontOfSize_(11))
        view.addSubview_(reinstall_note)

        y -= 50

        debug_label = self._create_label("Debug Logging:", NSMakeRect(20, y, 150, 20))
        view.addSubview_(debug_label)

        self.debug_checkbox = NSButton.alloc().initWithFrame_(NSMakeRect(180, y, 200, 20))
        self.debug_checkbox.setButtonType_(NSSwitchButton)
        self.debug_checkbox.setTitle_("")
        self.debug_checkbox.setState_(NSOnState if self.config.debug else NSOffState)
        self.debug_checkbox.setTarget_(self)
        self.debug_checkbox.setAction_(objc.selector(self.debugChanged_, signature=b"v@:@"))
        view.addSubview_(self.debug_checkbox)

        y -= 40

        logs_btn = NSButton.alloc().initWithFrame_(NSMakeRect(180, y, 100, 30))
        logs_btn.setTitle_("View Logs")
        logs_btn.setBezelStyle_(NSBezelStyleRounded)
        logs_btn.setTarget_(self)
        logs_btn.setAction_(objc.selector(self.viewLogs_, signature=b"v@:@"))
        view.addSubview_(logs_btn)

        tab.setView_(view)
        return tab

    def _update_hook_status(self):
        """Update the hook installation status display."""
        from ..hooks import is_hook_installed

        if is_hook_installed():
            self.hook_status.setStringValue_("Installed")
        else:
            self.hook_status.setStringValue_("Not installed")

    @objc.typedSelector(b"v@:@")
    def launchAtLoginChanged_(self, sender):
        self.config.set("launch_at_login", sender.state() == NSOnState)
        self._notify_changed()

    @objc.typedSelector(b"v@:@")
    def macosEnabledChanged_(self, sender):
        self.config.set("notifications.macos.enabled", sender.state() == NSOnState)
        self._notify_changed()

    @objc.typedSelector(b"v@:@")
    def soundChanged_(self, sender):
        self.config.set("notifications.macos.sound", sender.titleOfSelectedItem())
        self._notify_changed()

    @objc.typedSelector(b"v@:@")
    def terminalChanged_(self, sender):
        self.config.set("notifications.macos.terminal_app", sender.titleOfSelectedItem())
        self._notify_changed()

    @objc.typedSelector(b"v@:@")
    def telegramEnabledChanged_(self, sender):
        self.config.set("notifications.telegram.enabled", sender.state() == NSOnState)
        self._notify_changed()

    @objc.typedSelector(b"v@:@")
    def testTelegram_(self, sender):
        token = self.token_field.stringValue()
        chat_id = self.chat_field.stringValue()

        if not token or not chat_id:
            self._show_alert("Error", "Please enter both Bot Token and Chat ID")
            return

        self.config.set("notifications.telegram.bot_token", token)
        self.config.set("notifications.telegram.chat_id", chat_id)

        def test():
            success, message = test_telegram_connection_sync(token, chat_id)

            def show_result():
                if success:
                    self._show_alert("Success", f"Telegram connection working!\n{message}")
                else:
                    self._show_alert("Error", f"Connection failed:\n{message}")

            from AppKit import NSApp

            NSApp.performSelectorOnMainThread_withObject_waitUntilDone_(
                objc.selector(lambda: show_result(), signature=b"v@:"),
                None,
                False,
            )

        threading.Thread(target=test, daemon=True).start()

    @objc.typedSelector(b"v@:@")
    def contextChanged_(self, sender):
        self.config.set(
            "notifications.telegram.include_context", sender.state() == NSOnState
        )
        self._notify_changed()

    @objc.typedSelector(b"v@:@")
    def linesChanged_(self, sender):
        value = int(sender.intValue())
        self.lines_value.setStringValue_(str(value))
        self.config.set("notifications.telegram.context_lines", value)
        self._notify_changed()

    @objc.typedSelector(b"v@:@")
    def allNotificationsChanged_(self, sender):
        self.config.set("filters.all_notifications", sender.state() == NSOnState)
        self._notify_changed()

    @objc.typedSelector(b"v@:@")
    def debugChanged_(self, sender):
        self.config.set("debug", sender.state() == NSOnState)
        self._notify_changed()

    @objc.typedSelector(b"v@:@")
    def viewLogs_(self, sender):
        import subprocess

        from ..config import get_log_path

        log_path = get_log_path()
        if log_path.exists():
            subprocess.run(["open", "-a", "Console", str(log_path)])
        else:
            self._show_alert("No Logs", "Log file does not exist yet.")

    @objc.typedSelector(b"v@:@")
    def installHook_(self, sender):
        from ..hooks import install_hook

        success, message = install_hook(all_notifications=self.config.all_notifications)
        if success:
            self._show_alert("Success", message)
            self._update_hook_status()
        else:
            self._show_alert("Error", message)

    def _show_alert(self, title: str, message: str):
        """Show an alert dialog."""
        alert = NSAlert.alloc().init()
        alert.setMessageText_(title)
        alert.setInformativeText_(message)
        alert.addButtonWithTitle_("OK")
        alert.runModal()

    def _notify_changed(self):
        """Notify that config has changed."""
        if self.on_config_changed:
            self.on_config_changed()

    def showWindow_(self, sender):
        """Show the preferences window."""
        from AppKit import (
            NSApplicationActivationPolicyRegular,
            NSMenu,
            NSMenuItem,
        )

        # Temporarily become a regular app to show the window
        NSApp.setActivationPolicy_(NSApplicationActivationPolicyRegular)

        # Create Edit menu for copy/paste support
        menubar = NSMenu.alloc().init()
        app_menu_item = NSMenuItem.alloc().init()
        menubar.addItem_(app_menu_item)

        edit_menu_item = NSMenuItem.alloc().init()
        menubar.addItem_(edit_menu_item)

        edit_menu = NSMenu.alloc().initWithTitle_("Edit")

        cut_item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_("Cut", "cut:", "x")
        copy_item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_("Copy", "copy:", "c")
        paste_item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_("Paste", "paste:", "v")
        select_all_item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_("Select All", "selectAll:", "a")

        edit_menu.addItem_(cut_item)
        edit_menu.addItem_(copy_item)
        edit_menu.addItem_(paste_item)
        edit_menu.addItem_(NSMenuItem.separatorItem())
        edit_menu.addItem_(select_all_item)

        edit_menu_item.setSubmenu_(edit_menu)
        NSApp.setMainMenu_(menubar)

        NSApp.activateIgnoringOtherApps_(True)
        self.window.makeKeyAndOrderFront_(sender)


_prefs_controller = None


def show_preferences(config, on_changed=None):
    """Show the preferences window."""
    global _prefs_controller
    if _prefs_controller is None:
        _prefs_controller = PreferencesWindowController.alloc().initWithConfig_(config)
        _prefs_controller.on_config_changed = on_changed
    _prefs_controller.showWindow_(None)
