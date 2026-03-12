import os
import threading

import AppKit
import objc

from transcriber import Transcriber, model_search_dirs, normalize_language, resolve_model_path


WINDOW_GLASS_ALPHA = 0.80
PANEL_GLASS_ALPHA = 0.56
BACKGROUND_GLASS_ALPHA = 0.92
INPUT_FILL_ALPHA = 0.26
INPUT_BORDER_ALPHA = 0.48
BUTTON_FILL_ALPHA = 0.30
BUTTON_BORDER_ALPHA = 0.60
INNER_PANEL_ALPHA = 0.28

SUPPORTED_AUDIO_EXTENSIONS = (
    ".m4a",
    ".wav",
    ".mp3",
    ".flac",
    ".ogg",
    ".opus",
    ".aac",
    ".mp4",
    ".m4b",
)
OPEN_PANEL_FILE_TYPES = [ext[1:] for ext in SUPPORTED_AUDIO_EXTENSIONS]


def window_style_mask():
    def pick(new_name, old_name):
        value = getattr(AppKit, new_name, None)
        if value is None:
            value = getattr(AppKit, old_name)
        return value

    titled = pick("NSWindowStyleMaskTitled", "NSTitledWindowMask")
    closable = pick("NSWindowStyleMaskClosable", "NSClosableWindowMask")
    mini = pick("NSWindowStyleMaskMiniaturizable", "NSMiniaturizableWindowMask")
    resizable = pick("NSWindowStyleMaskResizable", "NSResizableWindowMask")
    full_size = getattr(AppKit, "NSWindowStyleMaskFullSizeContentView", 0)
    return int(titled) | int(closable) | int(mini) | int(resizable) | int(full_size)


class LiquidRootView(AppKit.NSView):
    delegate = None
    isDragActive = False
    dropFrame = AppKit.NSZeroRect

    def draggingEntered_(self, sender):
        self.isDragActive = True
        self.setNeedsDisplay_(True)
        return AppKit.NSDragOperationCopy

    def draggingExited_(self, sender):
        self.isDragActive = False
        self.setNeedsDisplay_(True)

    def performDragOperation_(self, sender):
        self.isDragActive = False
        self.setNeedsDisplay_(True)

        pasteboard = sender.draggingPasteboard()
        if pasteboard.types().containsObject_(AppKit.NSPasteboardTypeFileURL):
            file_url = AppKit.NSURL.URLFromPasteboard_(pasteboard)
            if file_url:
                path = str(file_url.path())
                if path.lower().endswith(SUPPORTED_AUDIO_EXTENSIONS) and self.delegate:
                    self.delegate.handleDroppedFile_(path)
                    return True
        return False

    def drawRect_(self, rect):
        bounds = self.bounds()
        gradient = AppKit.NSGradient.alloc().initWithColors_([
            AppKit.NSColor.colorWithCalibratedRed_green_blue_alpha_(0.01, 0.04, 0.13, BACKGROUND_GLASS_ALPHA),
            AppKit.NSColor.colorWithCalibratedRed_green_blue_alpha_(0.03, 0.09, 0.24, BACKGROUND_GLASS_ALPHA),
            AppKit.NSColor.colorWithCalibratedRed_green_blue_alpha_(0.07, 0.18, 0.39, BACKGROUND_GLASS_ALPHA),
        ])
        gradient.drawInRect_angle_(bounds, 90.0)

        shine = AppKit.NSGradient.alloc().initWithColors_([
            AppKit.NSColor.colorWithCalibratedRed_green_blue_alpha_(0.88, 0.95, 1.0, 0.30),
            AppKit.NSColor.colorWithCalibratedRed_green_blue_alpha_(0.78, 0.90, 1.0, 0.00),
        ])
        shine.drawInRect_angle_(bounds, -90.0)

        orb_left = AppKit.NSMakeRect(
            -bounds.size.width * 0.24,
            bounds.size.height * 0.28,
            bounds.size.width * 0.82,
            bounds.size.width * 0.82,
        )
        orb_left_gradient = AppKit.NSGradient.alloc().initWithColors_([
            AppKit.NSColor.colorWithCalibratedRed_green_blue_alpha_(0.30, 0.66, 1.0, 0.18),
            AppKit.NSColor.colorWithCalibratedRed_green_blue_alpha_(0.30, 0.66, 1.0, 0.00),
        ])
        orb_left_gradient.drawInBezierPath_angle_(AppKit.NSBezierPath.bezierPathWithOvalInRect_(orb_left), 90.0)

        orb_right = AppKit.NSMakeRect(
            bounds.size.width * 0.56,
            bounds.size.height * 0.08,
            bounds.size.width * 0.70,
            bounds.size.width * 0.70,
        )
        orb_right_gradient = AppKit.NSGradient.alloc().initWithColors_([
            AppKit.NSColor.colorWithCalibratedRed_green_blue_alpha_(0.58, 0.81, 1.0, 0.14),
            AppKit.NSColor.colorWithCalibratedRed_green_blue_alpha_(0.58, 0.81, 1.0, 0.00),
        ])
        orb_right_gradient.drawInBezierPath_angle_(AppKit.NSBezierPath.bezierPathWithOvalInRect_(orb_right), -90.0)

        if not AppKit.NSEqualRects(self.dropFrame, AppKit.NSZeroRect):
            glow_color = AppKit.NSColor.colorWithCalibratedRed_green_blue_alpha_(0.20, 0.64, 1.0, 0.28)
            border_color = AppKit.NSColor.colorWithCalibratedRed_green_blue_alpha_(0.54, 0.76, 1.0, 0.82)
            if self.isDragActive:
                glow_color = AppKit.NSColor.colorWithCalibratedRed_green_blue_alpha_(0.26, 0.78, 1.0, 0.44)
                border_color = AppKit.NSColor.colorWithCalibratedRed_green_blue_alpha_(0.70, 0.88, 1.0, 0.96)

            glow_color.set()
            AppKit.NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(
                AppKit.NSInsetRect(self.dropFrame, -8.0, -8.0), 28.0, 28.0
            ).fill()

            border = AppKit.NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(
                self.dropFrame, 22.0, 22.0
            )
            border_color.set()
            border.setLineWidth_(2.0)
            border.stroke()


def style_glass_panel(panel, corner_radius):
    panel.setWantsLayer_(True)
    if panel.layer():
        panel.layer().setCornerRadius_(corner_radius)
        panel.layer().setMasksToBounds_(True)
        panel.layer().setBorderWidth_(1.2)
        panel.layer().setBackgroundColor_(
            AppKit.NSColor.colorWithCalibratedRed_green_blue_alpha_(0.06, 0.13, 0.27, PANEL_GLASS_ALPHA).CGColor()
        )
        panel.layer().setBorderColor_(
            AppKit.NSColor.colorWithCalibratedRed_green_blue_alpha_(0.90, 0.96, 1.0, 0.64).CGColor()
        )


def style_glass_control(control):
    control.setWantsLayer_(True)
    if control.layer():
        control.layer().setCornerRadius_(10.0)
        control.layer().setBorderWidth_(1.0)
        control.layer().setBackgroundColor_(
            AppKit.NSColor.colorWithCalibratedRed_green_blue_alpha_(0.08, 0.15, 0.30, INPUT_FILL_ALPHA).CGColor()
        )
        control.layer().setBorderColor_(
            AppKit.NSColor.colorWithCalibratedRed_green_blue_alpha_(0.84, 0.93, 1.0, INPUT_BORDER_ALPHA).CGColor()
        )
    focus_none = getattr(AppKit, "NSFocusRingTypeNone", None)
    if focus_none is not None and hasattr(control, "setFocusRingType_"):
        control.setFocusRingType_(focus_none)


def style_glass_button(button):
    button.setBordered_(False)
    button.setWantsLayer_(True)
    if button.layer():
        button.layer().setCornerRadius_(11.0)
        button.layer().setBorderWidth_(1.0)
        button.layer().setBackgroundColor_(
            AppKit.NSColor.colorWithCalibratedRed_green_blue_alpha_(0.10, 0.20, 0.36, BUTTON_FILL_ALPHA).CGColor()
        )
        button.layer().setBorderColor_(
            AppKit.NSColor.colorWithCalibratedRed_green_blue_alpha_(0.90, 0.96, 1.0, BUTTON_BORDER_ALPHA).CGColor()
        )


def make_glass_panel(frame, corner_radius=22.0):
    panel = AppKit.NSVisualEffectView.alloc().initWithFrame_(frame)
    panel.setMaterial_(
        getattr(
            AppKit,
            "NSVisualEffectMaterialHUDWindow",
            getattr(AppKit, "NSVisualEffectMaterialUnderWindowBackground", getattr(AppKit, "NSVisualEffectMaterialSidebar", 7)),
        )
    )
    panel.setBlendingMode_(
        getattr(AppKit, "NSVisualEffectBlendingModeBehindWindow", getattr(AppKit, "NSVisualEffectBlendingModeWithinWindow", 0))
    )
    panel.setState_(getattr(AppKit, "NSVisualEffectStateActive", 1))
    style_glass_panel(panel, corner_radius)
    return panel


class AppDelegate(AppKit.NSObject):
    window = None
    rootView = None
    headerPanel = None
    transcriptPanel = None
    textView = None
    scrollView = None
    statusField = None
    modelPopup = None
    modelLabel = None
    languageLabel = None
    languageField = None
    titleField = None
    subtitleField = None
    hintField = None
    openButton = None
    copyButton = None
    saveButton = None
    transcriber = None

    selectedModelKey = "small"
    selectedLanguage = normalize_language(os.environ.get("STT80_LANGUAGE", "auto"))
    modelOptions = {
        "tiny": "ggml-tiny.bin",
        "base": "ggml-base.bin",
        "small": "ggml-small.bin",
        "medium-q5": "ggml-medium-q5_0.bin",
        "medium": "ggml-medium.bin",
    }

    def applicationDidFinishLaunching_(self, notification):
        frame = AppKit.NSMakeRect(0, 0, 980, 690)
        self.window = AppKit.NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
            frame,
            window_style_mask(),
            AppKit.NSBackingStoreBuffered,
            False,
        )
        self.window.setTitle_("STT80 Liquid Glass")
        self.window.center()
        self.window.setOpaque_(False)
        self.window.setBackgroundColor_(AppKit.NSColor.colorWithCalibratedRed_green_blue_alpha_(0.03, 0.06, 0.14, WINDOW_GLASS_ALPHA))
        self.window.setMinSize_(AppKit.NSMakeSize(900, 620))
        self.window.setDelegate_(self)
        if hasattr(self.window, "setTitlebarAppearsTransparent_"):
            self.window.setTitlebarAppearsTransparent_(True)
        if hasattr(self.window, "setTitleVisibility_"):
            hidden_title = getattr(AppKit, "NSWindowTitleHidden", None)
            if hidden_title is not None:
                self.window.setTitleVisibility_(hidden_title)
        if hasattr(self.window, "setToolbarStyle_"):
            compact = getattr(
                AppKit,
                "NSWindowToolbarStyleUnifiedCompact",
                getattr(AppKit, "NSWindowToolbarStyleUnified", None),
            )
            if compact is not None:
                self.window.setToolbarStyle_(compact)
        if hasattr(self.window, "setMovableByWindowBackground_"):
            self.window.setMovableByWindowBackground_(True)

        self.rootView = LiquidRootView.alloc().initWithFrame_(frame)
        self.rootView.delegate = self
        self.rootView.registerForDraggedTypes_([AppKit.NSPasteboardTypeFileURL])
        self.window.setContentView_(self.rootView)

        self._build_layout()
        self.window.makeKeyAndOrderFront_(None)
        AppKit.NSApplication.sharedApplication().activateIgnoringOtherApps_(True)

        threading.Thread(target=self.loadModel, daemon=True).start()

    def _build_layout(self):
        width = self.rootView.bounds().size.width
        height = self.rootView.bounds().size.height

        self.headerPanel = make_glass_panel(AppKit.NSMakeRect(22, height - 108, width - 44, 84), corner_radius=24.0)
        self.headerPanel.setAutoresizingMask_(AppKit.NSViewWidthSizable | AppKit.NSViewMinYMargin)
        self.rootView.addSubview_(self.headerPanel)

        self.transcriptPanel = make_glass_panel(AppKit.NSMakeRect(22, 22, width - 44, height - 144), corner_radius=26.0)
        self.transcriptPanel.setAutoresizingMask_(AppKit.NSViewWidthSizable | AppKit.NSViewHeightSizable)
        self.rootView.addSubview_(self.transcriptPanel)
        self.rootView.dropFrame = self.transcriptPanel.frame()

        self.titleField = AppKit.NSTextField.alloc().initWithFrame_(AppKit.NSMakeRect(22, 42, 430, 24))
        self.titleField.setEditable_(False)
        self.titleField.setBordered_(False)
        self.titleField.setDrawsBackground_(False)
        self.titleField.setFont_(AppKit.NSFont.fontWithName_size_("SF Pro Display Semibold", 19) or AppKit.NSFont.boldSystemFontOfSize_(19))
        self.titleField.setTextColor_(AppKit.NSColor.colorWithCalibratedRed_green_blue_alpha_(0.92, 0.96, 1.0, 1.0))
        self.titleField.setStringValue_("STT80 - Local Transcription")
        self.headerPanel.addSubview_(self.titleField)

        self.subtitleField = AppKit.NSTextField.alloc().initWithFrame_(AppKit.NSMakeRect(22, 20, 430, 18))
        self.subtitleField.setEditable_(False)
        self.subtitleField.setBordered_(False)
        self.subtitleField.setDrawsBackground_(False)
        self.subtitleField.setFont_(AppKit.NSFont.fontWithName_size_("SF Pro Text", 12) or AppKit.NSFont.systemFontOfSize_(12))
        self.subtitleField.setTextColor_(AppKit.NSColor.colorWithCalibratedRed_green_blue_alpha_(0.72, 0.82, 0.96, 1.0))
        self.subtitleField.setStringValue_("Transcribe local audio in any language (auto or code like en/es/it).")
        self.headerPanel.addSubview_(self.subtitleField)

        self.modelLabel = AppKit.NSTextField.alloc().initWithFrame_(AppKit.NSMakeRect(446, 47, 78, 16))
        self.modelLabel.setEditable_(False)
        self.modelLabel.setBordered_(False)
        self.modelLabel.setDrawsBackground_(False)
        self.modelLabel.setFont_(AppKit.NSFont.fontWithName_size_("SF Pro Text Semibold", 11) or AppKit.NSFont.systemFontOfSize_(11))
        self.modelLabel.setTextColor_(AppKit.NSColor.colorWithCalibratedRed_green_blue_alpha_(0.72, 0.82, 0.96, 1.0))
        self.modelLabel.setStringValue_("MODEL")
        self.headerPanel.addSubview_(self.modelLabel)

        self.modelPopup = AppKit.NSPopUpButton.alloc().initWithFrame_pullsDown_(AppKit.NSMakeRect(516, 40, 128, 26), False)
        self.modelPopup.addItemsWithTitles_(["tiny", "base", "small", "medium-q5", "medium"])
        self.modelPopup.selectItemWithTitle_(self.selectedModelKey)
        self.modelPopup.setTarget_(self)
        self.modelPopup.setAction_(b"modelSelectionChanged:")
        self.modelPopup.setAutoresizingMask_(AppKit.NSViewMinXMargin | AppKit.NSViewMinYMargin)
        self.modelPopup.setFont_(AppKit.NSFont.fontWithName_size_("SF Pro Text Medium", 12) or AppKit.NSFont.systemFontOfSize_(12))
        if hasattr(self.modelPopup, "setContentTintColor_"):
            self.modelPopup.setContentTintColor_(AppKit.NSColor.colorWithCalibratedRed_green_blue_alpha_(0.90, 0.95, 1.0, 1.0))
        style_glass_control(self.modelPopup)
        self.headerPanel.addSubview_(self.modelPopup)

        self.openButton = self._make_button(AppKit.NSMakeRect(650, 40, 90, 26), "Open...", b"openFile:")
        self.copyButton = self._make_button(AppKit.NSMakeRect(746, 40, 90, 26), "Copy", b"copyOutput:")
        self.saveButton = self._make_button(AppKit.NSMakeRect(842, 40, 90, 26), "Save TXT", b"saveOutput:")
        self.headerPanel.addSubview_(self.openButton)
        self.headerPanel.addSubview_(self.copyButton)
        self.headerPanel.addSubview_(self.saveButton)

        self.statusField = AppKit.NSTextField.alloc().initWithFrame_(AppKit.NSMakeRect(446, 16, 486, 16))
        self.statusField.setEditable_(False)
        self.statusField.setBordered_(False)
        self.statusField.setDrawsBackground_(False)
        self.statusField.setFont_(AppKit.NSFont.fontWithName_size_("SF Pro Text", 11) or AppKit.NSFont.systemFontOfSize_(11))
        self.statusField.setTextColor_(AppKit.NSColor.colorWithCalibratedRed_green_blue_alpha_(0.72, 0.82, 0.96, 1.0))
        self.statusField.setStringValue_("Booting engine...")
        self.statusField.setAutoresizingMask_(AppKit.NSViewMinXMargin | AppKit.NSViewMaxYMargin | AppKit.NSViewWidthSizable)
        self.headerPanel.addSubview_(self.statusField)

        self.languageLabel = AppKit.NSTextField.alloc().initWithFrame_(AppKit.NSMakeRect(0, 16, 68, 16))
        self.languageLabel.setEditable_(False)
        self.languageLabel.setBordered_(False)
        self.languageLabel.setDrawsBackground_(False)
        self.languageLabel.setFont_(AppKit.NSFont.fontWithName_size_("SF Pro Text Semibold", 11) or AppKit.NSFont.systemFontOfSize_(11))
        self.languageLabel.setTextColor_(AppKit.NSColor.colorWithCalibratedRed_green_blue_alpha_(0.72, 0.82, 0.96, 1.0))
        self.languageLabel.setStringValue_("LANG")
        self.headerPanel.addSubview_(self.languageLabel)

        self.languageField = AppKit.NSTextField.alloc().initWithFrame_(AppKit.NSMakeRect(0, 12, 104, 22))
        self.languageField.setStringValue_(self.selectedLanguage)
        self.languageField.setDrawsBackground_(False)
        self.languageField.setTextColor_(AppKit.NSColor.colorWithCalibratedRed_green_blue_alpha_(0.92, 0.96, 1.0, 1.0))
        self.languageField.setFont_(AppKit.NSFont.fontWithName_size_("SF Pro Text Medium", 12) or AppKit.NSFont.systemFontOfSize_(12))
        style_glass_control(self.languageField)
        if hasattr(self.languageField, "setPlaceholderString_"):
            self.languageField.setPlaceholderString_("auto")
        self.languageField.setTarget_(self)
        self.languageField.setAction_(b"languageChanged:")
        if hasattr(self.languageField, "setSendsActionOnEndEditing_"):
            self.languageField.setSendsActionOnEndEditing_(True)
        self.headerPanel.addSubview_(self.languageField)

        self.hintField = AppKit.NSTextField.alloc().initWithFrame_(AppKit.NSMakeRect(22, self.transcriptPanel.bounds().size.height - 34, self.transcriptPanel.bounds().size.width - 44, 16))
        self.hintField.setEditable_(False)
        self.hintField.setBordered_(False)
        self.hintField.setDrawsBackground_(False)
        self.hintField.setAutoresizingMask_(AppKit.NSViewWidthSizable | AppKit.NSViewMinYMargin)
        self.hintField.setFont_(AppKit.NSFont.fontWithName_size_("SF Pro Text Semibold", 12) or AppKit.NSFont.systemFontOfSize_(12))
        self.hintField.setTextColor_(AppKit.NSColor.colorWithCalibratedRed_green_blue_alpha_(0.76, 0.86, 0.98, 1.0))
        self.hintField.setStringValue_("Drop Zone: .m4a .wav .mp3 .flac .ogg .opus .aac .mp4 .m4b")
        self.transcriptPanel.addSubview_(self.hintField)

        self.scrollView = AppKit.NSScrollView.alloc().initWithFrame_(
            AppKit.NSMakeRect(22, 18, self.transcriptPanel.bounds().size.width - 44, self.transcriptPanel.bounds().size.height - 56)
        )
        self.scrollView.setAutoresizingMask_(AppKit.NSViewWidthSizable | AppKit.NSViewHeightSizable)
        self.scrollView.setHasVerticalScroller_(True)
        self.scrollView.setBorderType_(AppKit.NSNoBorder)
        self.scrollView.setDrawsBackground_(False)
        self.scrollView.setWantsLayer_(True)
        if self.scrollView.layer():
            self.scrollView.layer().setCornerRadius_(16.0)
            self.scrollView.layer().setBorderWidth_(1.0)
            self.scrollView.layer().setBackgroundColor_(
                AppKit.NSColor.colorWithCalibratedRed_green_blue_alpha_(0.09, 0.17, 0.30, INNER_PANEL_ALPHA).CGColor()
            )
            self.scrollView.layer().setBorderColor_(
                AppKit.NSColor.colorWithCalibratedRed_green_blue_alpha_(0.86, 0.94, 1.0, 0.40).CGColor()
            )

        size = self.scrollView.contentSize()
        self.textView = AppKit.NSTextView.alloc().initWithFrame_(AppKit.NSMakeRect(0, 0, size.width, size.height))
        self.textView.setEditable_(False)
        self.textView.setVerticallyResizable_(True)
        self.textView.setHorizontallyResizable_(False)
        self.textView.setAutoresizingMask_(AppKit.NSViewWidthSizable)
        self.textView.textContainer().setWidthTracksTextView_(True)
        self.textView.setBackgroundColor_(AppKit.NSColor.clearColor())
        self.textView.setTextColor_(AppKit.NSColor.colorWithCalibratedRed_green_blue_alpha_(0.92, 0.96, 1.0, 1.0))
        self.textView.setFont_(AppKit.NSFont.fontWithName_size_("SF Mono", 13) or AppKit.NSFont.userFixedPitchFontOfSize_(13))
        self.textView.setString_(
            "STT80 READY\n\n"
            "Recommended model: small (best speed/quality balance)\n\n"
            "1) Set language to 'auto' or a language code (en/es/it/fr/de/...)\n"
            "2) Wait for local transcription\n"
            "3) Get transcript + estimated 2-speaker turns"
        )

        self.scrollView.setDocumentView_(self.textView)
        self.transcriptPanel.addSubview_(self.scrollView)
        self._layout_header_controls()

    def _make_button(self, frame, title, action):
        button = AppKit.NSButton.alloc().initWithFrame_(frame)
        button.setTitle_(title)
        button.setBezelStyle_(getattr(AppKit, "NSBezelStyleRounded", getattr(AppKit, "NSRoundedBezelStyle", 1)))
        button.setFont_(AppKit.NSFont.fontWithName_size_("SF Pro Text Semibold", 12) or AppKit.NSFont.systemFontOfSize_(12))
        if hasattr(button, "setContentTintColor_"):
            button.setContentTintColor_(AppKit.NSColor.colorWithCalibratedRed_green_blue_alpha_(0.92, 0.96, 1.0, 1.0))
        style_glass_button(button)
        button.setTarget_(self)
        button.setAction_(action)
        button.setAutoresizingMask_(AppKit.NSViewMinXMargin | AppKit.NSViewMinYMargin)
        return button

    @objc.python_method
    def _layout_header_controls(self):
        if not self.headerPanel:
            return

        panel_width = self.headerPanel.bounds().size.width
        inset = 22.0
        button_width = 90.0
        spacing = 6.0

        save_x = panel_width - inset - button_width
        copy_x = save_x - spacing - button_width
        open_x = copy_x - spacing - button_width
        popup_x = open_x - 12.0 - 128.0
        label_x = popup_x - 68.0
        language_field_width = 104.0
        language_label_width = 54.0
        language_field_x = save_x - 2.0 - language_field_width
        language_label_x = language_field_x - 6.0 - language_label_width

        self.modelLabel.setFrame_(AppKit.NSMakeRect(label_x, 47, 60, 16))
        self.modelPopup.setFrame_(AppKit.NSMakeRect(popup_x, 40, 128, 26))
        self.openButton.setFrame_(AppKit.NSMakeRect(open_x, 40, button_width, 26))
        self.copyButton.setFrame_(AppKit.NSMakeRect(copy_x, 40, button_width, 26))
        self.saveButton.setFrame_(AppKit.NSMakeRect(save_x, 40, button_width, 26))
        self.languageLabel.setFrame_(AppKit.NSMakeRect(language_label_x, 16, language_label_width, 16))
        self.languageField.setFrame_(AppKit.NSMakeRect(language_field_x, 12, language_field_width, 22))

        status_width = max(140.0, language_label_x - 14.0 - label_x)
        self.statusField.setFrame_(AppKit.NSMakeRect(label_x, 16, status_width, 16))

    def windowDidResize_(self, notification):
        if self.rootView and self.transcriptPanel:
            self.rootView.dropFrame = self.transcriptPanel.frame()
            self.rootView.setNeedsDisplay_(True)
        self._layout_header_controls()

    @objc.python_method
    def loadModel(self):
        try:
            preferred_key = self.selectedModelKey

            model_file = self.modelOptions[preferred_key]
            model_path = resolve_model_path(model_file)

            if not model_path:
                fallback_order = ["small", "base", "tiny", "medium", "medium-q5"]
                fallback_key = None
                fallback_path = None
                for candidate in fallback_order:
                    candidate_file = self.modelOptions[candidate]
                    candidate_path = resolve_model_path(candidate_file)
                    if candidate_path:
                        fallback_key = candidate
                        fallback_path = candidate_path
                        break

                if fallback_key and fallback_path:
                    self.selectedModelKey = fallback_key
                    self.performSelectorOnMainThread_withObject_waitUntilDone_(
                        b"setModelPopupSelection:", fallback_key, False
                    )
                    self._update_status(f"Model '{preferred_key}' not found. Falling back to '{fallback_key}'.")
                    model_path = fallback_path
                else:
                    searched = "\n".join(f"- {path}" for path in model_search_dirs())
                    raise FileNotFoundError(
                        f"Missing model: {model_file}\n\nSearched in:\n{searched}"
                    )

            self.transcriber = Transcriber(model_path=model_path, language=self.selectedLanguage)
            self._update_status(
                f"Engine ready ({self.selectedModelKey}, {self.transcriber.backend_label}, lang: {self.transcriber.language_label})."
            )
        except Exception as exc:
            self.transcriber = None
            self._update_status(f"Engine error: {exc}")
            self._update_text(
                "Unable to start local Whisper backend.\n\n"
                f"Details: {exc}\n\n"
                "Quick checks:\n"
                "- pip install whisper-cpp-python\n"
                "- ffmpeg installed (brew install ffmpeg)\n"
                "- place ggml-<tiny|base|small|medium-q5|medium>.bin in project/models or ~/Library/Application Support/STT80/models\n"
                "- for medium-q5: build whisper-cli via ./setup_whisper_cli.sh"
            )

    def languageChanged_(self, sender):
        language = normalize_language(str(sender.stringValue()))
        self.selectedLanguage = language
        self.languageField.setStringValue_(language)

        if self.transcriber:
            self.transcriber.set_language(language)
            self._update_status(f"Language set to {self.transcriber.language_label}.")
        else:
            label = "auto-detect" if language == "auto" else language
            self._update_status(f"Language set to {label}. It will apply when engine is ready.")

    def modelSelectionChanged_(self, sender):
        selected_title = str(sender.titleOfSelectedItem())
        if selected_title not in self.modelOptions:
            return
        self.selectedModelKey = selected_title
        self.transcriber = None
        self._update_status(f"Switching model: {self.selectedModelKey}...")
        threading.Thread(target=self.loadModel, daemon=True).start()

    def copyOutput_(self, sender):
        text = str(self.textView.string() or "")
        pasteboard = AppKit.NSPasteboard.generalPasteboard()
        pasteboard.clearContents()
        pasteboard.setString_forType_(text, AppKit.NSPasteboardTypeString)
        self._update_status("Transcript copied to clipboard.")

    def openFile_(self, sender):
        panel = AppKit.NSOpenPanel.openPanel()
        panel.setTitle_("Select an audio file")
        panel.setCanChooseFiles_(True)
        panel.setCanChooseDirectories_(False)
        panel.setAllowsMultipleSelection_(False)
        if hasattr(panel, "setAllowedFileTypes_"):
            panel.setAllowedFileTypes_(OPEN_PANEL_FILE_TYPES)

        result = panel.runModal()
        ok_value = getattr(AppKit, "NSModalResponseOK", getattr(AppKit, "NSFileHandlingPanelOKButton", 1))
        if int(result) != int(ok_value):
            self._update_status("File open canceled.")
            return

        file_url = panel.URL()
        if not file_url:
            self._update_status("File open canceled.")
            return

        self.handleDroppedFile_(str(file_url.path()))

    def saveOutput_(self, sender):
        panel = AppKit.NSSavePanel.savePanel()
        panel.setTitle_("Save transcript")
        panel.setNameFieldStringValue_("transcript.txt")
        if hasattr(panel, "setAllowedFileTypes_"):
            panel.setAllowedFileTypes_(["txt"])

        result = panel.runModal()
        ok_value = getattr(AppKit, "NSModalResponseOK", getattr(AppKit, "NSFileHandlingPanelOKButton", 1))
        if int(result) != int(ok_value):
            self._update_status("Save canceled.")
            return

        output_url = panel.URL()
        if not output_url:
            self._update_status("Save canceled.")
            return

        output_path = str(output_url.path())
        try:
            with open(output_path, "w", encoding="utf-8") as file_handle:
                file_handle.write(str(self.textView.string() or ""))
            self._update_status(f"Transcript saved: {os.path.basename(output_path)}")
        except Exception as exc:
            self._update_status(f"Save error: {exc}")

    @objc.python_method
    def _update_status(self, text):
        self.performSelectorOnMainThread_withObject_waitUntilDone_(b"setStatusText:", text, False)

    @objc.python_method
    def _update_text(self, text):
        self.performSelectorOnMainThread_withObject_waitUntilDone_(b"setMainText:", text, False)

    def setStatusText_(self, text):
        self.statusField.setStringValue_(str(text))

    def setMainText_(self, text):
        self.textView.setString_(str(text))

    def setModelPopupSelection_(self, model_key):
        self.modelPopup.selectItemWithTitle_(str(model_key))

    def handleDroppedFile_(self, file_path):
        normalized_path = str(file_path or "")
        if not normalized_path.lower().endswith(SUPPORTED_AUDIO_EXTENSIONS):
            self._update_status("Unsupported file type. Use m4a/wav/mp3/flac/ogg/opus/aac/mp4/m4b.")
            return

        if not self.transcriber:
            self._update_status("Engine not ready yet.")
            return

        language = normalize_language(str(self.languageField.stringValue() or self.selectedLanguage))
        self.selectedLanguage = language
        self.languageField.setStringValue_(language)
        self.transcriber.set_language(language)

        file_name = os.path.basename(normalized_path)
        self._update_status(f"Transcribing: {file_name} (lang: {self.transcriber.language_label})")
        self._update_text(f"Local processing...\n\nFILE: {file_name}")
        threading.Thread(target=self._process_audio, args=(normalized_path,), daemon=True).start()

    @objc.python_method
    def _process_audio(self, file_path):
        result = self.transcriber.transcribe(file_path)
        self._update_text(result)
        self._update_status("Done. Drop another audio file.")

    def applicationShouldTerminateAfterLastWindowClosed_(self, sender):
        return True


if __name__ == "__main__":
    app = AppKit.NSApplication.sharedApplication()
    delegate = AppDelegate.alloc().init()
    app.setDelegate_(delegate)
    app.run()
