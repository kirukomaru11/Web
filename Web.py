from os import environ

environ["XDG_DATA_HOME"] = (environ.get("XDG_DATA_HOME", False) or (environ.get("HOME", f"/home/{environ.get('USER', 'user')}") + "/.local/share")) + "/Web"

try:
    from Utils import *
except ModuleNotFoundError:
    try:
        from .Utils import *
    except ModuleNotFoundError:
        print("No Utils")
        exit()

from gi.repository import WebKit

print("WebKit version:", ".".join((str(i) for i in (WebKit.get_major_version(), WebKit.get_minor_version(), WebKit.get_micro_version()))))

from gi.repository.Soup import tld_get_base_domain

from re import compile as Regex

class Window(Window):
    __gtype_name__ = "Window"

    drop_target_gtypes = (Gdk.FileList, Gio.File, Gtk.Label)
    prev_button = GObject.Property(type=Gtk.Button)
    next_button = GObject.Property(type=Gtk.Button)
    search = GObject.Property(type=Gtk.Widget)
    stack = GObject.Property(type=Gtk.Stack)
    wide = GObject.Property(type=Adw.ToolbarView)
    narrow = GObject.Property(type=Adw.ToolbarView)
    context_tab = GObject.Property(type=Adw.TabPage)
    context = GObject.Property(type=Gtk.Widget)
    bar = GObject.Property(type=Gtk.ProgressBar)
    find = GObject.Property(type=Gtk.Widget)
    downloads = GObject.Property(type=Gtk.Widget)

    def __init__(self, _id=None, tabs=None):
        tabs = tabs or []
        if not hasattr(self.__class__, "menu"):
            a = {}
            if exists(TRANSMISSION):
                a["Open Transmission"] = "open-transmission"
            a.update({"uBlock Filters": "ublock-filters", "Extra Settings": "extra-settings", "WebKit Features": "webkit-features", "Site Data Exceptions": "site-data-exceptions"})
            self.__class__.menu = Menu({"!a": Menu({"Open URIs": "open-uris"}), "!b": Menu({"Fullscreen": "win.fullscreen", "Find Bar": "win.find-bar", "Second View": "win.second-view", "New Window": "new-window", "View Open Tabs": "overview", "Reopen Closed Tab": "reopen-tab"}), "!c": Menu(a), "!d": App.default.default_menu})
        super().__init__()
        self.stack = Gtk.Stack()
        self.search = Search()
        self.wide, self.narrow = [Adw.ToolbarView(content=Adw.LayoutSlot.new("content")) for _ in range(2)]
        if not _id: App.default.data.set_default(table="Windows", conditions="ID = ?", conds=(self.get_id(),), names=("ID", ), values=(self.get_id(),))
        elif self.get_id() != _id: App.default.data.update(table="Windows", column="ID", value=self.get_id(), conditions="ID = ?", conds=(_id,))
        self.next_button = Button(sensitive=False, icon_name="go-next", tooltip_text="Next", callback=Tab.nav_history)
        self.prev_button = Button(sensitive=False, icon_name="go-previous", tooltip_text="Back", callback=Tab.nav_history)
        multi = Adw.MultiLayoutView()
        bookmarks_view, view = tuple(Adw.TabView(menu_model=Tab.context_menu, focusable=True) for _ in range(2))
        for i in (view, bookmarks_view): self.stack.add_child(i)
        overlay = Gtk.Overlay(child=self.stack)
        self.bar = Gtk.ProgressBar()
        self.bar.add_css_class("osd")
        self.bar.connect("notify::fraction", self.__class__.bar_visible)
        overlay.add_overlay(Gtk.Revealer(transition_duration=300, can_target=False, can_focus=False, focusable=False, transition_type=Gtk.RevealerTransitionType.CROSSFADE, child=self.bar))
        self.find = ViewFind()
        overlay.add_overlay(Gtk.Revealer(transition_duration=300, halign=Gtk.Align.CENTER, child=self.find))
        self.bar.get_parent().bind_property("valign", self.find.get_parent(), "valign", DEFAULT_BIND)
        self.find.get_parent().bind_property("valign", self.find.get_parent(), "transition-type", DEFAULT_BIND, self.__class__.find_reveal_bind)
        ExtraSettings.instance.load_bar.bind_property("active", self.bar.get_parent(), "visible", DEFAULT_BIND)
        self.add_action(Gio.SimpleAction.new_stateful("find-bar", None,  get_variant(False)))
        self.lookup_action("find-bar").bind_property("state", self.find.get_parent(), "reveal-child", SYNC_BIND, unpack_bind, variant_bind)
        multi.bind_property("layout-name", self.bar.get_parent(), "valign", DEFAULT_BIND, self.__class__.multi_bar_bind)
        self.downloads = Downloads()
        for i, w in (("downloads", self.downloads), ("content", overlay), ("search", self.search), ("start", Gtk.Box()), ("menu", Button(t=Gtk.MenuButton, menu_model=self.__class__.menu, tooltip_text="Menu", icon_name="open-menu"))): multi.set_child(i, w)
        for i in (self.prev_button, self.next_button): multi.get_child("start").append(i)
        wide_header = Adw.HeaderBar(title_widget=Adw.Clamp(hexpand=True, child=Adw.LayoutSlot.new("search"), maximum_size=650))
        narrow_header = Adw.HeaderBar(show_title=False, show_end_title_buttons=False)
        self.wide.add_top_bar(wide_header)
        for i in (Adw.LayoutSlot.new("search"), narrow_header): self.narrow.add_bottom_bar(i)
        for i in ("Default Width", "Default Height"): App.default.data.persist_action(self, i, 1, "Windows", i, "ID = ?", (self.get_id(),)).bind_property("state", self, i.lower().replace(" ", "-"), SYNC_BIND, unpack_bind, variant_bind)
        App.default.data.persist_action(self, "Maximized", False, "Windows", "Maximized", "ID = ?", (self.get_id(),)).bind_property("state", self, "maximized", SYNC_BIND, unpack_bind, variant_bind)
        App.default.data.persist_action(self, "Second View", True, "Windows", "Second View", "ID = ?", (self.get_id(),))
        for i, n in ((self.wide, "wide"), (self.narrow, "narrow")):
            ToolbarFullscreen(i)
            multi.add_layout(Adw.Layout(content=i, name=n))
        App.default.data.persist_action(self, "Fullscreen", False, "Windows", "Fullscreen", "ID = ?", (self.get_id(),)).connect("notify::state", self.change_fullscreen)
        for i in (wide_header, narrow_header):
            i.pack_start(Adw.LayoutSlot.new("start"))
            i.pack_end(Adw.LayoutSlot.new("menu"))
            i.pack_end(Adw.LayoutSlot.new("downloads"))
        wide_header.pack_start(Button(icon_name="tab-new", tooltip_text="New Tab", action_name="app.new-tab"))
        for i in App.default.data.read(table="Tabs", conditions="Window = ?", conds=(self.get_id(),), return_dict=True, force_tuple=True): Tab.create(view=bookmarks_view if i["TabView"] == 2 else view, uri=i["URI"])
        for i in tabs: Tab.create(webview=i[0], view=self.stack.get_first_child() if i[1] == 0 else self.stack.get_last_child(), uri=i[2])
        if not self.stack.get_first_child().get_selected_page(): Tab.create(view=self.stack.get_first_child())
        for i in self.stack:
            i.bar = Adw.TabBar(autohide=i != bookmarks_view, view=i)
            if i == bookmarks_view:
                i.bar.get_first_child().bind_property("reveal-child", self.stack.get_first_child().bar, "autohide", INVERT_BIND)
                self.lookup_action("second-view").bind_property("state", i.bar.get_first_child(), "reveal-child", SYNC_BIND, unpack_bind, variant_bind)
            self.wide.add_top_bar(i.bar)
            i.overview = Adw.TabOverview(child=multi if i == view else view.overview, enable_new_tab=True, view=i, secondary_menu=Window.menu)
            i.overview.connect("create-tab", self.__class__.overview_create_tab)
            tb = Adw.TabButton(view=i)
            if i == bookmarks_view:  self.lookup_action("second-view").bind_property("state", tb, "visible", SYNC_BIND, unpack_bind, variant_bind)
            tb.connect("clicked", self.__class__.tab_button_clicked)
            narrow_header.pack_start(tb)
            i.connect("notify::selected-page", Tab.changed)
            i.connect("notify::n-pages", Tab.idle_save_all)
            i.connect("page-reordered", Tab.idle_save_all)
            i.connect("setup-menu", Tab.setup_menu)
            i.connect("create-window", self.__class__.create)
            i.connect("close-page", Tab.operation)
        b = Adw.Breakpoint.new(Adw.BreakpointCondition.new_length(Adw.BreakpointConditionLengthType.MAX_WIDTH, 700, Adw.LengthUnit.PX))
        for i in ("apply", "unapply"): b.connect(i, self.update_css_size)
        b.add_setter(multi, "layout-name", "narrow")
        self.add_breakpoint(b)
        self.stack.connect("notify::visible-child", self.__class__.child_changed)
        self.__class__.child_changed(self.stack, None)
        bookmarks_view.bar.get_first_child().connect("notify::reveal-child", self.__class__.reveal_bookmarks_bar)
        self.set_content(self.stack.get_last_child().overview)
        Task.invoke(bookmarks_view.bar.get_first_child().set_reveal_child, self.lookup_action("second-view").get_state().unpack())
        Task.invoke(self.__class__.reveal_bookmarks_bar, bookmarks_view.bar.get_first_child())
        self.change_fullscreen()
        self.present()

    def update_css_size(self, b):
        if not self.get_current_breakpoint(): self.add_css_class("small")
        else: self.remove_css_class("small")

    @staticmethod
    def on_scroll(e, x, y):
        t = e.get_widget().get_root().stack.get_visible_child().get_selected_page()
        if Gdk.ModifierType.CONTROL_MASK in e.get_current_event_state() and t and t.get_child().webview and t.get_child().webview.get_mapped():
            z = t.get_child().webview.get_zoom_level() + (-y * 0.1)
            ExtraSettings.instance.zoom.set_value(z)
            t.get_child().webview.set_zoom_level(z)
            return True

    @staticmethod
    def find_reveal_bind(b, v): return Gtk.RevealerTransitionType.SLIDE_DOWN if v == Gtk.Align.START else Gtk.RevealerTransitionType.SLIDE_UP

    @staticmethod
    def bar_visible(b, p=None): GLib.timeout_add(200, b.get_parent().set_reveal_child, not b.get_fraction() == 1.0)

    @staticmethod
    def multi_bar_bind(b, v): return Gtk.Align.END if v == "narrow" else Gtk.Align.START

    @staticmethod
    def on_key_pressed(e, v, kc, s):
        self = e.get_widget()
        if self.search.searches.model.get_selected_item() and (v == Gdk.KEY_Escape or v == Gdk.KEY_BackSpace and not self.search.text.get_text()):
            self.search.searches.set_selected("")
            return True
        if v == Gdk.KEY_Escape:
            if self.search.autocomplete.get_mapped(): return
            if self.search.searches and self.search.searches.get_mapped():
                self.search.searches.popdown()
                return True
            if self.search.text.get_mapped():
                self.search.toggle()
                return True
            if "toolbar-fullscreen" in self.get_css_classes() and self.search.get_ancestor(Gtk.Revealer).get_reveal_child():
                self.search.get_ancestor(Gtk.Revealer).set_reveal_child(False)
                return True
        t = self.stack.get_visible_child().get_selected_page()
        if t and t.get_child().webview and (v == Gdk.KEY_F5 or Gdk.ModifierType.CONTROL_MASK in s and v == Gdk.KEY_r):
            t.get_child().webview.get_context().set_preferred_languages(t.get_child().webview.get_context().preferred_languages)
            t.get_child().webview.reload_bypass_cache()
            return True
        if isinstance(self.get_focus(), Gtk.Editable) or isinstance(self.get_focus(), Gtk.TextView) or isinstance(self.get_focus(), WebKit.WebView): return
        if Gdk.ModifierType.CONTROL_MASK in s and v == Gdk.KEY_v:
            c = self.get_display().get_clipboard()
            if c.get_formats().contain_gtype(Gdk.FileList):
                c.read_value_async(Gdk.FileList, GLib.PRIORITY_LOW, None, self.__class__.clipboard_read_value)
                return True
            elif "gchararray" in c.get_formats().to_string():
                c.read_text_async(None, self.__class__.clipboard_read_text)
                return True
        if not Gdk.ModifierType.CONTROL_MASK in s and not isinstance(self.get_focus(), Gtk.Text) and Gdk.keyval_to_unicode(v) != 0 and len(Gdk.keyval_name(v)) == 1 :
            if not self.search.text.get_mapped(): self.search.toggle()
            self.search.text.grab_focus()

    @staticmethod
    def on_map(w): Tab.changed(w.stack.get_visible_child())

    @staticmethod
    def reveal_bookmarks_bar(a, p=None): GLib.timeout_add(200, a.get_ancestor(Adw.TabBar).get_template_child(Adw.TabBar, "scrolled_window").get_hadjustment().set_value, 0)

    @staticmethod
    def tab_button_clicked(b):
        if not b.get_view().get_n_pages(): Tab.create(view=b.get_view())
        b.get_view().get_parent().set_visible_child(b.get_view())
        b.get_view().overview.set_open(not b.get_view().overview.get_open())

    @staticmethod
    def overview_create_tab(*_): return Tab.create().tab

    @staticmethod
    def on_click(e, *args):
        self = e.get_widget().get_root()
        b = e.get_current_button()
        if isinstance(e, Gtk.GestureClick):
            n, x, y, signal = args
        else:
            x, y, signal = args
        if b == 8:
            if signal == "released": Task.invoke(self.prev_button.emit, "clicked")
            return
        elif b == 9:
            if signal == "released": Task.invoke(self.next_button.emit, "clicked")
            return
        if self.search.autocomplete.get_mapped():
            if signal == "released": self.search.autocomplete.popdown()
            return
        w = self.pick(x, y, Gtk.PickFlags.DEFAULT)
        if self.search.searches.get_mapped():
            w = self.get_widget_at_popover(self.search.searches, x, y)
            if not (w and w.get_ancestor(Search)): self.search.searches.popdown()
            return
        if (isinstance(e, Gtk.GestureClick) and b == 3 or isinstance(e, Gtk.GestureLongPress) and b == 1) and w and w.get_ancestor(Search):
            if isinstance(e, Gtk.GestureClick) and Gdk.ModifierType.SHIFT_MASK in e.get_current_event_state(): return
            self.show_popover_at_widget(self.search.searches, self.search, x, y)
            e.set_state(Gtk.EventSequenceState.CLAIMED)
            Task.invoke(e.reset)
        if signal == "released" and w and w.get_ancestor(Adw.TabBar): return self.stack.set_visible_child(w.get_ancestor(Adw.TabBar).get_view())

    @staticmethod
    def create(*_): return Window().stack.get_visible_child()

    @staticmethod
    def child_changed(s, p):
        for i in s:
            if i == s.get_visible_child(): i.bar.add_css_class("visible")
            else: i.bar.remove_css_class("visible")
        if s.get_root(): Tab.changed(s.get_visible_child())

    @staticmethod
    def clipboard_read_value(cl, r):
        v = cl.read_value_finish(r)
        open_files([v] if isinstance(v, Gio.File) else v)

    @staticmethod
    def clipboard_read_text(cl, r): open_files(cl.read_text_finish(r).split("\n"))

    @staticmethod
    def on_drop_target_drop(e, v, x, y):
        self = e.get_widget().get_root()
        if hasattr(self, "highlight") and self.highlight:
            self.highlight.remove_css_class("highlight")
            a, b = Searches.list.default.get_model()[v.get_label()], Searches.list.default.get_model()[self.highlight.get_label()]
            if a == b: return False
            a.id, b.id = b.id, a.id
            s = Searches.list.default.get_sorter()
            Searches.list.default.set_sorter(None)
            Searches.list.default.set_sorter(s)
            self.highlight = None
            return True
        else:
            open_files([v] if isinstance(v, Gio.File) else v)
            return True

    @staticmethod
    def on_drop_target_motion(e, x, y):
        self = e.get_widget().get_root()
        if getattr(self, "highlight", False): self.highlight.remove_css_class("highlight")
        self.highlight = self.get_widget_at_popover(self.search.searches, x, y)
        if self.highlight and not self.highlight.get_ancestor(Gtk.Button):
            self.highlight.add_css_class("highlight")
            return Gdk.DragAction.MOVE
        self.highlight = None
        return Gdk.DragAction.COPY

    @staticmethod
    def on_drag_source_prepare(e, x, y):
        self = e.get_widget().get_root()
        w = self.get_widget_at_popover(self.search.searches, x, y)
        if w and not w.get_ancestor(Gtk.Button):
            e.v = w
            e.set_actions(Gdk.DragAction.MOVE)
            return Gdk.ContentProvider.new_for_value(w)

    @staticmethod
    def on_drag_source_drag_begin(e, d):
        self = e.get_widget().get_root()
        if e.v: Gtk.DragIcon.get_for_drag(d).set_child(Gtk.Label(margin_top=10, margin_start=10, label=e.v.get_label(), css_classes=("title-4",), ellipsize=Pango.EllipsizeMode.END))

    @staticmethod
    def on_drag_source_drag_end(e, d, de):
        self = e.get_widget().get_root()
        e.set_content(None)
        e.set_actions(Gdk.DragAction.NONE)
        if hasattr(self, "highlight") and self.highlight: self.highlight.remove_css_class("highlight")

class Tab(Adw.Bin):
    __gtype_name__ = "Tab"

    @GObject.Property(type=str, flags=GObject.ParamFlags.READWRITE)
    def uri(self): return getattr(self, "_uri", "")

    @uri.setter
    def uri(self, value):
        if self.uri == "Transmission": return
        if value and "youtube.com" in value and "&pp=" in value:
            value = value.split("&pp=", 1)
            value = value[0] + (value[1].split("&", 1)[-1] if "&" in value[1] else "")
        self._uri = value or ""

    closed = []
    requests = {}
    history = {}

    muted = GObject.Property(type=bool, default=False)
    ephemeral = GObject.Property(type=bool, default=False)
    tab = GObject.Property(type=Adw.TabPage)
    webview = GObject.Property(type=WebKit.WebView)

    context_menu = Menu({"!a": Menu({"New Tab": "new-tab", "New Window": "new-window", "Reopen Closed Tab": "reopen-tab"}), "!b": Menu()})

    def __init__(self, view=False, webview=False, uri=False):
        super().__init__(css_name=self.__gtype_name__.lower())
        v = view or Window.current.stack.get_visible_child()
        view = view or Window.current.stack.get_first_child()
        current_tab = v.get_selected_page().get_child() if v.get_selected_page() else False
        if uri == False:
            uri = current_tab.uri if current_tab else ""
        self.uri = uri
        self.tab = view.add_page(self, current_tab.tab if current_tab else None) if view.get_mapped() else view.append(self)
        if current_tab and current_tab.webview and current_tab.webview.get_network_session() != NetworkSession():
            webview = current_tab.webview
            self.ephemeral = True
        if webview: self.setup_view(webview)
        elif current_tab and current_tab.uri == uri: self.tab.set_title(current_tab.tab.get_title())
        else: self.tab.set_title(uri)
        if not self.tab.get_title(): self.tab.set_title("Untitled")
        self.connect("notify::ephemeral", self.__class__.ephemeral_changed)
        if not self.get_child(): self.set_child(Adw.Spinner())

    @staticmethod
    def ephemeral_changed(self, p=None):
        self.unload()
        self.setup_view()

    def unload(self, force=False):
        self.set_child(None)
        if self.uri == "Transmission": close_transmission()
        if self.webview:
            self.webview.tab = None
            self.webview.stop_loading()
            self.webview.load_uri("")
            if hasattr(self, "webview_binds"):
                for i in self.webview_binds: i.unbind()
            self.webview.run_dispose()
            if force or not [i.webview for i in self.__class__.get_all() if i.webview and i.webview.related_view == self.webview]: self.webview.terminate_web_process()
            self.webview = None
            self.tab.set_loading(False)

    @staticmethod
    def convert_title(b, v):
        u = b.get_property("target").get_child().uri
        t = v if v else u if u else "Untitled"
        if u: History.set(u, t)
        return t

    @staticmethod
    def create(*_, view=False, webview=None, uri=False): return Tab(view=view if isinstance(view, Adw.TabView) else False, webview=False, uri=uri)

    @staticmethod
    def setup_menu(v, t):
        if not t: return
        v.get_root().set_property("context-tab", t)
        while v.get_menu_model().get_n_items() != 1: v.get_menu_model().remove(v.get_menu_model().get_n_items() - 1)
        v.get_menu_model().append_section(None, Menu({"Set User Agent": "context-set-user-agent", "Set Preferred Languages": "context-set-preferred-languages", "Set Time Zone Override": "context-set-time-zone-override"}))
        v.get_menu_model().append_section(None, Menu({"Copy URL": "context-copy-tab", "Unmute" if t.get_child().muted else "Mute": "context-mute-tab", "Switch Session to Normal" if t.get_child().ephemeral else "Switch Session to Ephemeral": "context-tab-switch-session", "Move to Other Bar": "context-move-tab", "Unload": "context-tab-unload", "Close": "context-close-tab"}))

    @staticmethod
    def nav_history(b):
        webview = b.get_root().stack.get_visible_child().get_selected_page().get_child().webview
        if not webview or not b.get_sensitive(): return
        if "Back" in b.get_tooltip_text(): webview.go_back()
        else: webview.go_forward()

    def sync(self):
        if not self.get_mapped(): return
        w = self.get_root()
        if not w or w.stack.get_visible_child().get_selected_page() != self.tab: return
        if not self.webview: return
        if self.webview.get_uri():
            self.uri = WebKit.uri_for_display(self.webview.get_uri())
        if hasattr(w.bar, "bind"): w.bar.bind.unbind()
        if w.bar.get_parent().get_visible():
            w.bar.bind = self.webview.bind_property("estimated-load-progress", w.bar, "fraction", DEFAULT_BIND)
        if w.find.get_mapped():
            w.find.entry.set_text(self.webview.get_find_controller().get_search_text() or "")
            w.find.entry.set_position(-1)
        w.search.search = ""
        w.search.set_text(self.uri)
        w.prev_button.set_sensitive(self.webview.can_go_back())
        w.next_button.set_sensitive(self.webview.can_go_forward())
        if not self.uri or self.uri == "about:blank": self.set_child(Adw.StatusPage(title="Start Browsing", icon_name="applications-internet-symbolic", description="This is an empty page"))
        elif self.get_child() != self.webview: self.set_child(self.webview)

    def setup_view(self, webview=None, **kwargs):
        for i, v in {"user_content_manager": UserContentManager(), "web_context": WebContext.default, "settings": WebKitFeatures.settings.default, "network_session": NetworkSession(ephemeral=self.ephemeral)}.items(): kwargs.setdefault(i, v)
        kwargs["web_context"].set_preferred_languages(kwargs["web_context"].preferred_languages)
        self.webview = WebKit.WebView(related_view=webview) if webview else WebKit.WebView(**kwargs)
        self.webview.tab = self
        self.webview.related_view = webview
        self.webview.set_zoom_level(ExtraSettings.instance.zoom.get_value())
        self.webview.set_background_color(ExtraSettings.instance.background_color.get_rgba())
        self.webview.connect("permission-request", self.__class__.permission_request)
        self.webview.connect("load-changed", self.__class__.load_changed)
        self.webview.connect("load-failed", self.__class__.load_failed)
        self.webview.connect("decide-policy", self.__class__.decide_policy)
        self.webview.connect("context-menu", self.__class__.view_context_menu)
        self.webview.connect("create", self.__class__.webview_create)
        self.webview_binds = (self.bind_property("muted", self.webview, "is-muted", DEFAULT_BIND), self.webview.bind_property("title", self.tab, "title", DEFAULT_BIND, self.__class__.convert_title), self.webview.bind_property("is-loading", self.tab, "loading", DEFAULT_BIND))
        if self.uri == "Transmission":
            if not hasattr(App, self.uri):
                App.Transmission = GLib.spawn_async([TRANSMISSION, "-f"], envp=[f"{i}={App.default.data_folder.get_path()}" for i in ("HOME", "XDG_DATA_HOME", "XDG_CONFIG_HOME", "XDG_STATE_HOME", "XDG_CACHE_HOME")], flags=GLib.SpawnFlags.DEFAULT | GLib.SpawnFlags.CHILD_INHERITS_STDERR | GLib.SpawnFlags.CHILD_INHERITS_STDOUT)[0]
            u = "http://127.0.0.1:9091/"
        else:
            u = self.uri
        Task.invoke(self.webview.load_uri, u)
        if self.uri == "Transmission":
            self.loaded_sig = self.tab.connect("notify::loading", self.__class__.do_load_transmission)

    @staticmethod
    def do_load_transmission(tab, prop):
        tab = tab.get_child()
        tab.tab.disconnect(tab.loaded_sig)
        del tab.loaded_sig
        a = getattr(App, "to_open", [])
        App.to_open = []
        GLib.spawn_command_line_sync(TRANSMISSION.replace("daemon", "remote") + f" -w '{App.default.data_folder.get_path()}'")
        open_files(a)

    @staticmethod
    def load_failed(v, e, u, er):
        if e == WebKit.LoadEvent.STARTED and "Frame load interrupted" in str(er): v.download_uri(u)

    @staticmethod
    def view_context_menu(v, c, te):
        n = -1
        for i in list(c.get_items()):
            n += 1
            if not i.get_title(): continue
            t = i.get_title().replace("_", "")
            if t.endswith(("Highlight", "Open Link", "Emoji", "Unicode Control Character")):
                n -= 1
                c.remove(i)
            elif any(i in t for i in ("New Window", "Toggle Media", "Copy Link Location", "Download", "Image", "Video")):
                c.remove(i)
                new = t.replace("Toggle Media ", "").replace(" Playback", "").replace("Switch Video to Fullscreen", "Fullscreen").replace(" Linked", "").replace(" Link", "").replace(" File", "").replace("Location", "URL").replace("Address", "URL").replace("Download", "Save").replace("Window", "Tab").replace(" in New Tab", "").replace(" Video", "").replace(" Image", "").replace(" As", "")
                if "ed" in new: print(t, new)
                c.insert(WebKit.ContextMenuItem.new_from_stock_action_with_label(i.get_stock_action(), new), n)
            elif t == "Inspect Element":
                c.remove(i)
                c.insert(WebKit.ContextMenuItem.new_from_gaction(App.default.lookup_action("inspector"), "Web Inspector"), n)
        if c.get_n_items() == 2:
            i = c.get_items()[0]
            if i.is_separator(): c.remove(i)
        n = -1
        l = list(c.get_items())
        for i in l:
            n += 1
            if i.is_separator() and len(l) > n and l[n + 1].is_separator():
                n -= 1
                c.remove(i)
        u = te.get_image_uri() or te.get_media_uri() or te.get_link_uri()
        if u == "javascript:void(0)":
            u = te.get_link_label()
        if u: Tab.add_searches(u, c)
        else: v.evaluate_javascript("window.getSelection().toString()", -1, None, None, None, Tab.stupid_selection_finish)

    @staticmethod
    def add_searches(q, c):
        if isinstance(c, WebKit.ContextMenu): c.insert(WebKit.ContextMenuItem.new_with_submenu("Search With", WebKit.ContextMenu.new_with_items([WebKit.ContextMenuItem.new_from_gaction(App.default.lookup_action("context-search"), i.name, get_variant(i.url.replace("%QUERY%", q))) for i in Searches.list.default.get_model()])), 0)
        else: c.get_last_child().get_menu_model().prepend_submenu("Search With", Menu(dict((i.name, "app.context-search::" + i.url.replace("%QUERY%", q)) for i in Searches.list.default.get_model())))

    @staticmethod
    def stupid_selection_finish(v, r):
        q = v.evaluate_javascript_finish(r).to_string()
        if q: Tab.add_searches(q, v)

    @staticmethod
    def changed(view, *_):
        if not view.get_mapped(): return
        w = view.get_root()
        if not w: return
        if not view.get_selected_page(): return
        self = view.get_selected_page().get_child()
        first_setup = not self.webview and self.tab
        if first_setup: self.setup_view()
        if not first_setup and isinstance(self.get_child(), Adw.Spinner): Task.invoke(self.webview.load_uri, self.uri)
        else: Task.invoke(self.sync)

    @staticmethod
    def operation(a, b=False, t=False):
        view = a if isinstance(a, Adw.TabView) else App.default.get_active_window().stack.get_visible_child()
        if not t:
            t = b if isinstance(b, Adw.TabPage) else view.get_root().context_tab if "context" in a.get_name() else view.get_selected_page()
            t = t.get_child()
        if not t: return
        view = t.get_ancestor(Adw.TabView)
        if isinstance(a, Adw.TabView) or isinstance(a, Gio.SimpleAction) and "close-tab" in a.get_name():
            view.close_page(t.tab) if isinstance(a, Gio.SimpleAction) else None
            Tab.closed.append(t.uri)

            App.default.lookup_action("reopen-tab").set_enabled(bool(Tab.closed))
            Task.invoke(t.unload)
        if "set-preferred-languages" in a.get_name():
            group = Adw.PreferencesGroup()
            r = TagRow(tags=t.webview.get_context().preferred_languages if t.webview and hasattr(t.webview.get_context(), "preferred_languages") else getattr(WebContext.default, "preferred_languages", None))
            group.add(r)
            p = Prompt(heading="Preferred Languages", callback=Tab.do_preferred_languages, extra_child=group)
            p.tab = t
            p.present(t.get_root())
        if "set-user-agent" in a.get_name():
            p = EntryPrompt(heading="User Agent", callback=Tab.do_user_agent)
            if t.webview: p.set_text(t.webview.get_settings().get_user_agent())
            p.tab = t
            p.present(t.get_root())
        if "set-time-zone-override" in a.get_name():
            p = EntryPrompt(heading="Time Zone", callback=Tab.do_time_zone)
            if t.webview: p.set_text(t.webview.get_context().get_property("time-zone-override"))
            p.tab = t
            p.present(t.get_root())
        if "move-tab" in a.get_name():
            nv = view.get_next_sibling() if view.get_next_sibling() != None else view.get_prev_sibling()
            view.transfer_page(t.tab, nv, nv.get_n_pages())
        if "mute" in a.get_name():
            t.muted = not t.muted
        if "switch-session" in a.get_name():
            t.ephemeral = not t.ephemeral
        if "copy" in a.get_name(): Gdk.Display.get_default().get_clipboard().set(t.uri)
        if "unload" in a.get_name(): t.unload()
        if "inspector" in a.get_name():
            t.webview.get_inspector().attach()
            t.webview.get_inspector().detach()
            t.webview.get_inspector().show()

    @staticmethod
    def do_user_agent(d):
        t = d.tab
        if not t.webview: t.setup_view()
        s = WebKit.Settings()
        for i in ExtraSettings.settings.list_properties():
            if any(it in i.flags for it in (GObject.ParamFlags.DEPRECATED, GObject.ParamFlags.CONSTRUCT_ONLY)): continue
            if i.name == "user-agent": s.set_property(i.name, d.get_text() or None)
            else: ExtraSettings.settings.bind_property(i.name, s, i.name, DEFAULT_BIND)
        t.webview.set_settings(s)

    @staticmethod
    def do_preferred_languages(d):
        t = d.tab
        if t.webview:
            c = WebContext(time_zone_override=t.webview.get_context().get_time_zone_override())
        else:
            c = WebContext()
        t.unload()
        c.preferred_languages = d.get_extra_child().get_row(0).tags
        t.setup_view(web_context=c)
        del d.tab

    @staticmethod
    def do_time_zone(d):
        t = d.tab
        c = WebContext(time_zone_override=d.get_text())
        if t.webview:
            c.preferred_languages = t.webview.get_context().preferred_languages
        t.unload()
        t.setup_view(web_context=c)
        del d.tab

    @staticmethod
    def context_search(a, b):
        t = Tab.create(uri=b.unpack())
        t.get_ancestor(Adw.TabView).set_selected_page(t.tab)

    @staticmethod
    def idle_save_all(*_): Task.invoke(Tab.get_all, save=True)

    @staticmethod
    def get_all(save=False):
        tabs = []
        for w in App.default.get_windows():
            if not isinstance(w, Window) or save and not w.get_mapped(): continue
            for __id, v in enumerate(w.stack):
                for ___id, i in enumerate(v.get_pages()):
                    if save:
                        i.get_child().data = (w.get_id(), __id, ___id)
                    tabs.append(i.get_child())
        if save and Window.current and Window.current.get_mapped():
            for i in tabs:
                if i.data[1] == 0 and i.data[2] == 0: App.default.data.delete(table="Tabs", conditions="Window = ?", conds=(i.data[0],))
                App.default.data.new(table="Tabs", values=(i.data[0], i.data[1] + 1, i.data[2] + 1, i.uri))
        return tabs

    @staticmethod
    def webview_create(v, d):
        if d.get_navigation_type() == WebKit.NavigationType.OTHER and not d.get_request().get_uri() == "about:blank": Tab.create(uri=d.get_request().get_uri())

    @staticmethod
    def decide_policy(v, d, t):
        u = d.get_navigation_action().get_request().get_uri() if isinstance(d, WebKit.NavigationPolicyDecision) else d.get_request().get_uri()
        if u == "about:blank":
            d.ignore()
            return True
        if u.startswith("blob:"):
            d.download()
            return True
        if isinstance(d, WebKit.NavigationPolicyDecision):
            if u.startswith("mpv://"):
                GLib.spawn_command_line_async(f"mpv {u.split('mpv://', 1)[-1]}")
                d.ignore()
                return True
            if not u.startswith(("file://", "about:", "https://", "http://")):
                GLib.spawn_command_line_async(f"xdg-open {u}")
                d.ignore()
                return True
        if t == WebKit.PolicyDecisionType.NEW_WINDOW_ACTION or isinstance(d, WebKit.NavigationPolicyDecision) and d.get_navigation_action().get_mouse_button() == 2:
            Tab.create(uri=u)
            d.ignore()
            return True

    @staticmethod
    def load_changed(v, event=None):
        self = v.tab
        if not self: return
        Task.invoke(self.sync)

    @staticmethod
    def permission_request(v, request):
        u = v.get_uri().split("://", 1)[-1].split("/", 1)[0]
        Tab.requests.setdefault(u, {})
        n = " ".join(CAMEL_CASE_SPLIT.findall(str(request).split("WebKit.",1)[-1].split("PermissionRequest", 1)[0]))
        if n in Tab.requests[u]:
            if Tab.requests[u][n].allowed: request.allow()
            else: request.deny()
        else:
            p = Prompt(heading="Permission Request", body=f"{u} is asking for {n} permission", callback=Tab.handle_request, responses=("deny", "allow"), confirm_callback=False)
            Tab.requests[u][n] = request
            p.request = request
            p.present(v.get_root())
        return True

    @staticmethod
    def handle_request(d, r):
        d.request.allowed = r == "allow"
        if d.request.allowed: d.request.allow()
        else: d.request.deny()
        d.request = None

class History(ListObject):
    __gtype_name__ = "History"
    title = GObject.Property(type=str)
    uri = GObject.Property(type=str)

    @staticmethod
    def title_bind(b, v):
        self = b.get_property("source")
        if not self: return ""
        if self.uri.startswith("file://"):
            t = GLib.markup_escape_text(uri_decode(self.uri))
        else:
            t = GLib.markup_escape_text(self.uri.split("://", 1)[-1].rstrip("/"))
        if self.title and not self.uri == self.title: return (f"<b>{self.title}</b> • " + t).strip()
        else: return t

    @staticmethod
    def init_list():
        if not hasattr(History, "list"):
            History.list = List(History, unique="uri", static=True)

    @staticmethod
    def set(u, t):
        History.init_list()
        ex = History.list[u]
        if ex:
            ex.title = t
        else: History.list.append({"uri": u, "title": t})

class SearchObject(ListObject):
    __gtype_name__ = "SearchObject"
    id = GObject.Property(type=int, nick="ID", default=0)

    @GObject.Property(type=str)
    def name(self): return getattr(self, "_name", "")

    @name.setter
    def name(self, value):
        old_name = self.name
        self._name = value
        if old_name:
            App.default.data.update(table="Searches", column="Name", value=self.name, conditions="Name = ?", conds=(old_name,))
            Task.invoke(Searches.list.default.get_model().do_dict)

    url = GObject.Property(type=str)
    shortcut = GObject.Property(type=str)
    color = GObject.Property(type=RGBA)

    def color_from(self, v): return RGBA(v)

    @staticmethod
    def changed(self, p):
        if getattr(self, "changing", False): return
        if not self in Searches.list.default.get_model(): return
        name = p.get_name().replace("-", "_")
        v = getattr(self, name, None)
        p = p.get_nick() or name.title().replace("_", " ")
        if isinstance(v, Gdk.RGBA):
            v = v.to_string()
        App.default.data.update(table="Searches", column=p, value=v, conditions="Name = ?", conds=(self.name,))

    @staticmethod
    def setup(f, l): l.set_child(Gtk.Label(xalign=0))

    @staticmethod
    def bind(f, l):
        if not l.get_child(): return
        l.get_child().bindings = [l.get_property("item").bind_property("name", l.get_child(), "label", DEFAULT_BIND)]

    @staticmethod
    def unbind(f, l):
        for i in getattr(l.get_child(), "bindings", []): i.unbind()
        if hasattr(l.get_child(), "bindings"): del l.get_child().bindings

    @staticmethod
    def teardown(f, l): l.set_child(None)

    def new(*_):
        name = unique_name("New Search", Searches.list.default.get_model())
        App.default.data.new(table="Searches", values=(name,), names=("Name",))
        Searches.list.default.get_model().add(App.default.data.read(table="Searches", conds=(name,), conditions="Name = ?", return_dict=True))

    factory = Gtk.SignalListItemFactory.new()
    factory.connect("setup", setup)
    factory.connect("bind", bind)
    factory.connect("unbind", unbind)
    factory.connect("teardown", teardown)

class Searches(Gtk.Popover):
    __gtype_name__ = "Searches"

    model = GObject.Property(type=Gtk.SingleSelection)
    list = GObject.Property(type=Gtk.SortListModel, default=Gtk.SortListModel(sorter=Gtk.NumericSorter(expression=Gtk.PropertyExpression.new(SearchObject, None, "id")), model=List(SearchObject, unique="name", static=True)))

    def __init__(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        super().__init__(autohide=False, has_arrow=False, child=box)
        self.model = Gtk.SingleSelection(autoselect=False, can_unselect=True)
        self.model.connect("notify::selected", self.__class__.selected_changed, self)
        self.bind_property("list", self.model, "model", DEFAULT_BIND)
        listview = Gtk.ListView(model=self.model, factory=SearchObject.factory)
        listview.set_css_classes(["navigation-sidebar"])
        listview.connect("activate", self.__class__.row_activate)
        box.append(Gtk.ScrolledWindow(propagate_natural_height=True, propagate_natural_width=True, child=listview))
        box.append(Gtk.Separator())
        self.list.bind_property("n-items", box.get_last_child(), "visible", DEFAULT_BIND, bool_bind)
        box.append(Button(callback=SearchObject.new, label="Add New Search", css_classes=["flat"]))
        box.get_last_child().get_first_child().set_xalign(0)
        self.add_css_class(self.__gtype_name__.lower())

    @staticmethod
    def selected_changed(l, p, self):
        item = l.get_selected_item()
        App.default.color_css = ((":root { --search-color: " + item.color.to_string() + "; }") if item else "")
        if item: self.get_parent().add_css_class("has-search")
        else: self.get_parent().remove_css_class("has-search")

    @staticmethod
    def row_activate(l, n):
        if not isinstance(n, int): return
        self = l.get_ancestor(Searches)
        if not self: return
        self.popdown()
        item = l.get_model().get_item(n)
        page = GroupsPage()
        group = Adw.PreferencesGroup()
        page.add(group)
        l = []
        l.append(Adw.EntryRow(title="Name", text=item.name, show_apply_button=True))
        l[-1].connect("apply", self.__class__.change_name)
        for i in (("URL (%QUERY% instead of query)", "URL"), ("Shortcut", "Shortcut")):
            l.append(Adw.EntryRow(title=i[0], name=i[1]))
            item.bind_property(i[1].lower(), l[-1], "text", SYNC_BIND)
        l.append(ColorRow(title="Color", name="Color"))
        item.bind_property("color", l[-1], "rgba", SYNC_BIND)
        for i in l: group.add(i)
        header = Adw.HeaderBar()
        header.pack_end(Button(icon_name="user-trash", tooltip_text="Delete Search", callback=self.__class__.prompt_delete))
        edit = Adw.Dialog(child=Adw.ToastOverlay(child=Adw.ToolbarView(content=page)), content_height=295, content_width=360)
        edit.get_child().get_child().add_top_bar(header)
        item.bind_property("name", edit, "title", DEFAULT_BIND)
        edit.present()

    @staticmethod
    def do_delete(d):
        App.default.data.delete(table="Searches", conditions="Name = ?", conds=(d.dialog.get_title(),))
        Searches.list.default.get_model().remove(d.dialog.get_title())
        if d.dialog: d.dialog.close()
        del d.dialog

    @staticmethod
    def prompt_heading(b, v): return f"Delete {v}?"

    @staticmethod
    def prompt_delete(b):
        delete = Prompt(callback=Searches.do_delete, appearance=Adw.ResponseAppearance.DESTRUCTIVE)
        delete.dialog = b.get_ancestor(Adw.Dialog)
        b.get_ancestor(Adw.Dialog).bind_property("title", delete, "heading", DEFAULT_BIND, Searches.prompt_heading)
        delete.present(delete.dialog)

    @staticmethod
    def change_name(w, p=None):
        d = w.get_ancestor(Adw.Dialog)
        if not d: return
        t = w.get_text()
        if not t: return Toast("Name can't be empty")
        if t in Searches.list.default.get_model(): return Toast(f"{t} already exists")
        Searches.list.default.get_model()[d.get_title()].name = t

    def set_selected(self, name):
        l = [self.model.get_item(i).name for i in range(self.model.get_n_items())]
        self.model.select_item(l.index(name) if name and name in l else Gtk.INVALID_LIST_POSITION, True)

class Search(Adw.Bin):
    __gtype_name__ = "Search"

    text = GObject.Property(type=Gtk.Text)
    preview = GObject.Property(type=Gtk.Button)
    autocomplete = GObject.Property(type=Autocomplete)
    searches = GObject.Property(type=Searches)
    completer = Gio.FilenameCompleter()

    def __init__(self):
        super().__init__(child=Adw.ViewStack(vhomogeneous=False, hhomogeneous=False, enable_transitions=True), css_name="search")
        self.searches = Searches()
        self.searches.set_parent(self)
        self.text = Gtk.Text(placeholder_text="Search", xalign=0.50, hexpand=True)
        self.preview = Button(label="", css_classes=("flat",), callback=self.toggle)
        self.preview.get_first_child().set_properties(use_markup=True, ellipsize=Pango.EllipsizeMode.END, xalign=0.50, hexpand=True)
        self.get_child().add_named(self.preview, "Preview")
        self.get_child().add_named(self.text, "Editing")
        self.autocomplete = Autocomplete(self.text, select=self.__class__.select, model=List(History), bind=self.__class__.bind, setup=self.__class__.setup, text_activate=self.__class__.text_activate, row_activate=self.__class__.row_activate, complete=self.__class__.complete)

    @staticmethod
    def row_activate(text, autocomplete, item):
        self = text.get_root()
        if not self: return
        t = item.uri if item else ""
        if not item or self.search.get_text() == t:
            autocomplete.popdown()
            autocomplete.model.replace()
            return True
        self.search.set_text(t)
        return True

    @staticmethod
    def text_activate(text, autocomplete, s):
        self = text.get_root()
        if not self: return
        if Gdk.ModifierType.SHIFT_MASK in s:
            Tab.create(uri=self.search.get_text())
            return True
        else:
            if self.search.searches: self.search.searches.popdown()
            t = self.stack.get_visible_child().get_selected_page()
            if not t: return
            t = t.get_child()
            if not t: return
            t.webview.load_uri(self.search.get_text())
            self.search.search = ""
            Task.invoke(self.search.toggle)
            Tab.idle_save_all()
            return True

    @staticmethod
    def complete(autocomplete, text):
        self = text.get_ancestor(Search)
        if not self.search:
            for i in Searches.list.default.get_model():
                if i.shortcut and text.get_text().startswith(i.shortcut):
                    self.searches.set_selected(i.name)
                    autocomplete.set_text("" if text.get_text() == i.shortcut else text.get_text().split(i.shortcut, 1)[-1], -1)
                    break
        t = self.get_text(complete=False)
        History.init_list()
        l = [i for i in History.list if t.lower() in i.uri.lower()] if t else []
        if not l and t.startswith(("/", "file://")):
            t = uri_decode(uri_relative_encode(t))
            l = [History(title=basename(i), uri=uri_relative_encode(i.rstrip("/") or "/")) for i in Search.completer.get_completions(t)]
        autocomplete.model.replace(l)

    @staticmethod
    def setup(f, l): l.set_child(Gtk.Label(use_markup=True, xalign=0))

    @staticmethod
    def bind(f, l):
        l.get_child().bindings = [l.get_property("item").bind_property("title", l.get_child(), "label", DEFAULT_BIND, History.title_bind)]

    @staticmethod
    def select(text, autocomplete, item): return autocomplete.set_text(item.uri)

    @staticmethod
    def focus(*_):
        s = App.default.get_active_window().search
        if not s.text.get_mapped(): s.toggle()
        s.search = ""
        s.autocomplete.set_text("")
        s.text.grab_focus()

    def set_text(self, t="", p=-1):
        t = WebKit.uri_for_display(t) or ""
        preview_text = t.split("://", 1)[-1]
        if is_online(t):
            preview_text = preview_text.split("/", 1)[0]
            try:
                domain = tld_get_base_domain(preview_text)
                d, e = domain.replace("www.", "").split(".", 1)
                preview_text = (d + f"<span alpha='50%'>.{e}</span>").join([f"<span alpha='50%'>{i}</span>" for i in preview_text.rsplit(domain, 1)]).replace("<span alpha='50%'>www.</span>", "")
            except Exception as e:
                print(e)
                preview_text = GLib.markup_escape_text(t.split("://", 1)[-1].split("/", 1)[0])
        else:
            preview_text = preview_text.rsplit("/", 1)[-1]
        self.preview.set_label(preview_text if preview_text else "Search")
        self.autocomplete.set_text(t, p)

    def get_text(self, complete=True):
        s = self.text.get_text()
        if self.searches.model.get_selected_item(): return self.searches.model.get_selected_item().url.replace("%QUERY%", s)
        elif complete and s and not "://" in s:
            s = ("file://" if s.startswith("/") else "https://") + s
        return s

    def toggle(self, *_):
        self.get_root().stack.get_visible_child().get_selected_page().get_child().sync()
        self.get_child().set_visible_child_name("Editing" if self.get_child().get_visible_child_name() == "Preview" else "Preview")
        self.get_ancestor(Gtk.Revealer).set_reveal_child(True)
        self.get_child().get_visible_child().grab_focus()

class ExtraSettings(Adw.PreferencesDialog):
    __gtype_name__ = "ExtraSettings"
    zoom = GObject.Property(type=Adw.SpinRow)
    background_color = GObject.Property(type=ColorRow)
    cache_model = GObject.Property(type=Adw.ComboRow)
    preferred_languages = GObject.Property(type=TagRow)
    def __init__(self):
        self.__class__.instance = self
        super().__init__(search_enabled=True, title="Extra Settings", content_height=500, content_width=500)
        self.__class__.settings = self.settings = WebKitFeatures.settings.default
        page = Adw.PreferencesPage()
        groups = [Adw.PreferencesGroup(title=i) for i in ("View", "Context", "Settings")]
        self.add(page)
        for i in groups: page.add(i)
        self.zoom = Adw.SpinRow.new_with_range(0.1, 100.0, 0.1)
        self.zoom.set_title("Zoom")
        self.zoom.set_value(float(Data.setting(self.zoom.get_title(), 1.0)))
        self.preferred_languages = TagRow(title="Preferred Languages", tags=Data.setting("Preferred Languages", "").split(", "))
        c = [i.strip() for i in self.preferred_languages.tags] if self.preferred_languages.tags else None
        WebContext.default.preferred_languages = c
        self.background_color = ColorRow(title="Background Color")
        self.background_color.set_rgba(RGBA(Data.setting(self.background_color.get_title(), "#ffffff")))
        self.cache_model = Adw.ComboRow(title="Cache Model", model=Gtk.StringList.new([i.replace("_", " ").title() for i in dir(WebKit.CacheModel) if i.isupper()]))
        self.load_bar = Adw.SwitchRow(title="Load Bar", active=Data.setting("Load Bar", True))
        for i, t in ((self.preferred_languages, "notify::tags"), (self.zoom, "changed"), (self.background_color, "notify::rgba"), (self.cache_model, "notify::selected"), (self.load_bar, "notify::active")):
            i.connect(t, self.__class__.view_changed)
            groups[1 if i in (self.preferred_languages, self.cache_model) else 0].add(i if isinstance(i, Adw.PreferencesRow) else Adw.PreferencesRow(child=i))
        self.cache_model.set_selected(self.cache_model.get_model().find(Data.setting(self.cache_model.get_title(), "Web Browser")))
        for i in self.settings.list_properties():
            if GObject.ParamFlags.DEPRECATED in i.flags: continue
            default = Data.setting(i.name, self.settings.get_property(i.name))
            t = str(i.value_type)
            if i.name == "hardware-acceleration-policy":
                w = Adw.ComboRow(model=Gtk.StringList.new(("Always", "Never")))
                default = int(default)
                w.v = "selected"
            elif "gchararray" in t:
                if not default:
                    default = ""
                w = Adw.EntryRow()
                w.v = "text"
            elif "bool" in t:
                w = Adw.SwitchRow()
                default = bool(int(default))
                w.v = "active"
            elif "int" in t:
                w = Adw.SpinRow.new_with_range(i.minimum, i.maximum, 1)
                default = float(default)
                w.v = "value"
            else:
                w = None
            if w:
                w.set_property(w.v, default)
                w.connect("changed" if w.v == "text" else f"notify::{w.v}", self.__class__.setting_changed)
                w.set_name(i.get_name())
                w.set_title(i.get_name().replace("-", " ").title().replace("Html5", "HTML5").replace("Webaudio", "WebAudio").replace("Webgl", "WebGL").replace("Webrtc", "WebRTC").replace("Url", "URL").replace("Stdout", "STDOUT").replace("Udp", "UDP").replace("Mediasource", "MediaSource"))
                w.bind_property(w.v, self.settings, i.name, DEFAULT_BIND)
                groups[-1].add(w)

    @staticmethod
    def setting_changed(r, p=None): Data.setting(r.get_name(), None, r.get_property(r.v))

    @staticmethod
    def view_changed(r, p=None):
        if r.get_title() == "Preferred Languages":
            c = [i.strip() for i in r.tags] if r.tags else None
            WebContext.default.preferred_languages = c
        if r.get_title() == "Cache Model": WebContext.default.set_cache_model(next((getattr(WebKit.CacheModel, i) for i in dir(WebKit.CacheModel) if i == r.get_selected_item().get_string().upper().replace(" ", "_")), WebKit.CacheModel.WEB_BROWSER))
        Data.setting(r.get_title(), "" if isinstance(r, TagRow) else None, r.get_rgba().to_string() if isinstance(r, ColorRow) else r.get_value() if isinstance(r, Adw.SpinRow) else r.get_active() if isinstance(r, Adw.SwitchRow) else r.get_text() if isinstance(r, Adw.EntryRow) else ", ".join(r.tags) if isinstance(r, TagRow) else r.get_selected_item().get_string())

    @staticmethod
    def show(*_):
        if not getattr(ExtraSettings, "instance", False): ExtraSettings()
        if ExtraSettings.instance.get_mapped(): ExtraSettings.instance.close()
        ExtraSettings.instance.present()

class WebKitFeatures(Adw.Dialog):
    __gtype_name__ = "WebKitFeatures"

    settings = GObject.Property(type=WebKit.Settings, default=WebKit.Settings())
    status = GObject.Property(type=Adw.StatusPage)

    def __init__(self):
        self.__class__.instance = self
        stack = Adw.ViewStack(vhomogeneous=False)
        view_switcher = Adw.ViewSwitcherSidebar(stack=stack)
        view_switcher.connect("activated", self.__class__.sidebar_activated)
        sidebar_toolbar = Adw.ToolbarView(content=Gtk.ScrolledWindow(child=view_switcher))
        sidebar_toolbar.add_top_bar(Adw.HeaderBar())
        content = Adw.NavigationPage(child=Adw.ToolbarView(content=Gtk.Overlay(child=Gtk.ScrolledWindow(child=stack))))
        search = Gtk.SearchEntry(hexpand=True, placeholder_text="Search")
        search.connect("search-changed", self.__class__.search_changed)
        content.get_child().add_top_bar(Adw.HeaderBar(title_widget=Adw.Clamp(maximum_size=350, child=search)))
        categories = {}
        super().__init__(title="WebKit Features", content_height=800, content_width=800, child=Adw.ToastOverlay(child=Adw.NavigationSplitView(sidebar=Adw.NavigationPage(title="WebKit Features", child=sidebar_toolbar), content=content)))
        search.set_key_capture_widget(self)
        self.status = Adw.StatusPage(visible=False, icon_name="edit-find-symbolic")
        content.get_child().get_content().add_overlay(self.status)
        f = self.settings.get_all_features()
        l = [f.get(n) for n in range(f.get_length())]
        for i in l:
            if i.get_identifier() == "ForceCompositingMode":
                i.get_default_value = return_true
            if not i.get_category() in categories:
                categories[i.get_category()] = Gtk.Box(name=i.get_category(), orientation=Gtk.Orientation.VERTICAL)
                categories[i.get_category()].groups = {}
            s = i.get_status().name.title()
            if not s in categories[i.get_category()].groups:
                categories[i.get_category()].groups[s] = Adw.PreferencesGroup(title=s)
            w = Adw.SwitchRow(subtitle=GLib.markup_escape_text(i.get_details()) if i.get_details() else "", name=i.get_identifier(), active=Data.setting(i.get_identifier(), i.get_default_value()))
            w.feature = i
            self.__class__.setting_changed(w)
            w.connect("notify::active", self.__class__.setting_changed)
            categories[i.get_category()].groups[s].add(w)
        for i in sorted(categories, key=alphabetical_sort):
            for it in sorted(categories[i].groups, key=alphabetical_sort): categories[i].append(categories[i].groups[it])
            stack.add_titled(categories[i], i, i)
        stack.bind_property("visible-child-name", content, "title", DEFAULT_BIND)
        self.add_css_class("settings")
        self.bind_property("css-classes", view_switcher, "mode", DEFAULT_BIND, self.__class__.view_bind)
        self.bind_property("css-classes", self.get_child().get_child(), "collapsed", DEFAULT_BIND, self.__class__.nav_bind)
        stack.connect("notify::visible-child-name", self.__class__.map_status)

    def map_status(self, *_):
        self = self.get_ancestor(WebKitFeatures)
        stack = self.status.get_parent().get_child().get_child().get_child()
        visibles = []
        for box in stack:
            if any([i.get_visible() for i in box]): visibles.append(box.get_name())
        self.status.set_visible(not stack.get_visible_child_name() in visibles)
        self.status.set_title("Nothing Here" if visibles else "No Results")
        self.status.set_description("" if not visibles else "Results in " + (" and " if len(visibles) == 2 else ", ").join(visibles))

    @staticmethod
    def search_changed(s):
        stack = s.get_ancestor(Adw.ToolbarView).get_content().get_child().get_child().get_child()
        if not stack.get_ancestor(WebKitFeatures): return
        s = s.get_text().lower()
        for box in stack:
            for group in box:
                t = False
                for i in group.get_template_child(Adw.PreferencesGroup, "listbox"):
                    i.set_visible(not s or any([s in it.lower() for it in (i.get_title(), i.get_subtitle(), i.get_name())]))
                    t = t or i.get_visible()
                group.set_visible(t)
        stack.get_ancestor(WebKitFeatures).map_status()

    @staticmethod
    def show(*_):
        if not getattr(WebKitFeatures, "instance", False): WebKitFeatures()
        if WebKitFeatures.instance.get_mapped(): WebKitFeatures.instance.close()
        WebKitFeatures.instance.present()

    @staticmethod
    def setting_changed(r, p=None):
        name = GLib.markup_escape_text(r.feature.get_name() or r.feature.get_identifier())
        r.set_title(name if r.get_active() == r.feature.get_default_value() else "<b>" + name + "</b>")
        WebKitFeatures.settings.default.set_feature_enabled(r.feature, r.get_active())
        if not p == None: Data.setting(r.get_name(), None, r.get_active())

    @staticmethod
    def nav_bind(b, v): return "narrow" in v

    @staticmethod
    def view_bind(b, v): return Adw.SidebarMode.PAGE if "narrow" in v else Adw.SidebarMode.SIDEBAR

    @staticmethod
    def sidebar_activated(v): v.get_ancestor(Adw.NavigationSplitView).set_show_content(True)

class SiteDataExceptions(Adw.Dialog):
    __gtype_name__ = "SiteDataExceptions"

    tags = GObject.Property(type=TagRow)

    def __init__(self):
        toolbar = Adw.ToolbarView()
        toolbar.add_top_bar(Adw.HeaderBar())
        super().__init__(title="Site Data Exceptions", content_height=600, content_width=600, child=Adw.ToastOverlay(child=toolbar))
        t = Data.setting("SiteDataExceptions", "")
        self.tags = TagRow(title="Site", tags=t.split(", ") if t else [])
        self.tags.connect("notify::tags", self.__class__.tags_changed)
        group = Adw.PreferencesGroup()
        group.add(self.tags)
        page = GroupsPage()
        page.add(group)
        toolbar.set_content(page)

    @staticmethod
    def tags_changed(*_): Data.setting("SiteDataExceptions", "", ", ".join(App.default.site_data_exceptions.tags.tags))

    @staticmethod
    def show(*_):
        if not hasattr(App.default, "site_data_exceptions"):
            App.default.site_data_exceptions = SiteDataExceptions()
        if App.default.site_data_exceptions.get_mapped(): App.default.site_data_exceptions.close()
        App.default.site_data_exceptions.present(App.default.get_active_window())

    @staticmethod
    def remove_finish(a, r, e=None):
        try: a.remove_finish(r)
        except Exception as e: print(e)
        if e: e.set()

    @staticmethod
    def finish_fetch(a, r, e=None):
        data = [i for i in a.fetch_finish(r) if not i.get_name() in Data.setting("SiteDataExceptions", "").split(", ")]
        if data: a.remove(WebKit.WebsiteDataTypes.ALL, data, None, SiteDataExceptions.remove_finish, e)
        elif e: e.set()

    @staticmethod
    def clear(e=None): NetworkSession().get_website_data_manager().fetch(WebKit.WebsiteDataTypes.ALL, None, SiteDataExceptions.finish_fetch, e)

class ViewFind(Gtk.Box):
    __gtype_name__ = "ViewFind"

    options = GObject.Property(type=Gtk.Box)
    previous = GObject.Property(type=Gtk.Button)
    entry = GObject.Property(type=Gtk.SearchEntry)
    next = GObject.Property(type=Gtk.Button)

    def __init__(self):
        super().__init__(css_classes=("linked", ), css_name="find")
        self.options = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        for i in dir(WebKit.FindOptions):
            if i.isupper():
                b = Button(t=Gtk.ToggleButton, css_classes=("flat",), label=i.replace("_", " ").title())
                b.flag = getattr(WebKit.FindOptions, i)
                b.get_first_child().set_xalign(0)
                self.options.append(b)
        self.entry = Gtk.SearchEntry(placeholder_text="Find")
        self.entry.connect("activate", self.__class__.do_search)
        self.entry.connect("stop-search", self.__class__.stop_search)
        self.entry.connect("previous-match", self.__class__.previous_match)
        self.entry.connect("next-match", self.__class__.next_match)
        self.previous, self.next = [Button(icon_name=f"go-{i}", callback=self.__class__.move_search, tooltip_text=i.title()) for i in ["previous", "next"]]
        for i in (self.previous, self.entry, Button(t=Gtk.MenuButton, popover=Gtk.Popover(child=self.options), icon_name="emblem-system", tooltip_text="Options"), self.next): self.append(i)
        self.connect("map", self.__class__.mapped)

    @staticmethod
    def mapped(w): w.entry.grab_focus()

    @staticmethod
    def previous_match(s):
        f = ViewFind.get_find(s)
        if f: f.search_previous()

    @staticmethod
    def next_match(s):
        f = ViewFind.get_find(s)
        if f: f.search_next()

    @staticmethod
    def get_find(s):
        w = s.get_root()
        t = w.stack.get_visible_child().get_selected_page().get_child()
        if not t.webview and t.webview.get_mapped(): return
        return t.webview.get_find_controller()

    @staticmethod
    def stop_search(s):
        s.get_ancestor(Gtk.Revealer).set_reveal_child(False)
        s.set_text("")
        f = ViewFind.get_find(s)
        if f: f.search_finish()

    @staticmethod
    def do_search(s):
        f = ViewFind.get_find(s)
        if not f: return
        if not s.get_text(): return f.search_finish()
        f.search(s.get_text(), bitwise_or_loop([i.flag for i in s.get_root().find.options if i.get_active()] or [0]), 0)

    @staticmethod
    def move_search(b):
        f = ViewFind.get_find(b)
        if not f: return
        if "Next" in b.get_tooltip_text(): f.search_next()
        else: f.search_previous()

class Download(Gtk.Box):
    __gtype_name__ = "Download"
    download = GObject.Property(type=WebKit.Download)
    progress = GObject.Property(type=Gtk.ProgressBar)
    label = GObject.Property(type=Gtk.Label)
    def __init__(self):
        super().__init__(css_name="download", orientation=Gtk.Orientation.VERTICAL)
        self.bindings = []
        self.connect("notify::download", self.__class__.download_changed)
        box = Gtk.Box(hexpand=True)
        box.append(Button(css_classes=["circular"], icon_name="folder-open", tooltip_text="Open Folder", callback=self.__class__.open_folder))
        self.label = Gtk.Label(hexpand=True, single_line_mode=True, ellipsize=Pango.EllipsizeMode.END)
        self.label.bind_property("label", self.label, "tooltip-text", DEFAULT_BIND)
        box.append(self.label)
        box.append(Button(css_classes=["circular"], icon_name="process-stop", tooltip_text="Remove", callback=self.__class__.remove))
        self.append(box)
        self.progress = Gtk.ProgressBar()
        self.progress.bind_property("fraction", self.progress, "visible", DEFAULT_BIND, self.__class__.progress_bind)
        self.append(self.progress)

    @staticmethod
    def download_changed(self, p=None):
        for i in self.bindings: i.unbind()
        self.bindings = []
        if self.download:
            self.bindings.append(self.download.bind_property("estimated-progress", self.progress, "tooltip-text", DEFAULT_BIND, self.__class__.progress_tooltip_bind))
            self.bindings.append(self.download.bind_property("estimated-progress", self.progress, "fraction", DEFAULT_BIND))
            self.bindings.append(self.download.bind_property("destination", self.label, "label", DEFAULT_BIND, self.__class__.label_bind))

    @staticmethod
    def label_bind(b, v): return basename(v) if v else ""

    @staticmethod
    def progress_tooltip_bind(b, v):
        if v == 1.0: return GLib.format_size(b.get_property("source").get_received_data_length())
        if v == 0: return
        return GLib.format_size(b.get_property("source").get_received_data_length()) + " of " + GLib.format_size(int(round(b.get_property("source").get_received_data_length() / v)))

    @staticmethod
    def progress_bind(b, v): return v != 1.0

    @staticmethod
    def open_folder(b): launch(b.get_ancestor(Download).download.get_destination(), folder=True)

    @staticmethod
    def remove(b):
        self = b.get_ancestor(Download)
        if not self.download.get_estimated_progress() == 1.0: self.download.cancel()
        Downloads.downloads.remove(self.download)

    factory = Gtk.SignalListItemFactory.new()
    @staticmethod
    def setup(f, l): l.set_child(Download())
    factory.connect("setup", setup)
    @staticmethod
    def bind(f, l):
        Task.invoke(l.get_child().get_parent().set_properties, css_classes=[], focusable=False)
        l.get_child().download = l.get_property("item")
    factory.connect("bind", bind)
    @staticmethod
    def unbind(f, l):
        l.get_child().download = None
    factory.connect("unbind", unbind)
    @staticmethod
    def teardown(f, l): l.set_child(None)
    factory.connect("teardown", teardown)

class Downloads(Gtk.Revealer):
    __gtype_name__ = "Downloads"

    downloads = List(WebKit.Download)

    def __init__(self):
        listview = Gtk.ListView(valign=Gtk.Align.START, factory=Download.factory, model=Gtk.NoSelection(model=self.__class__.downloads))
        listview.set_css_classes(["navigation-sidebar"])
        super().__init__(transition_duration=300, transition_type=Gtk.RevealerTransitionType.CROSSFADE, child=Button(t=Gtk.MenuButton, icon_name="folder-download", popover=Gtk.Popover(autohide=False, child=Gtk.ScrolledWindow(propagate_natural_height=True, child=listview)), tooltip_text="Downloads"))
        listview.get_model().bind_property("n-items", self, "reveal-child", DEFAULT_BIND, bool_bind)
        self.add_css_class("downloads")

    @staticmethod
    def do_decide(a, r, d):
        try:
            d.set_destination(a.save_finish(r).peek_path())
            if not d in Downloads.downloads: Downloads.downloads.append(d)
        except Exception as e:
            print(e)
            Task.invoke(d.cancel)
            if d in Downloads.downloads: Downloads.downloads.remove(d)

    @staticmethod
    def decide_destination(d, suggested):
        Gtk.FileDialog(initial_name=suggested).save(App.default.get_active_window(), None, Downloads.do_decide, d)
        return True

    @staticmethod
    def set_error(d, e):
        if d in Downloads.downloads: Downloads.downloads.remove(d)
        if e.message != "User cancelled the download": Toast(e.message, timeout=0)

    @staticmethod
    def handle_started(n, d):
        if not d in Downloads.downloads: Downloads.downloads.append(d)
        d.set_allow_overwrite(True)
        d.connect("failed", Downloads.set_error)
        d.connect("decide-destination", Downloads.decide_destination)

class WebContext:
    memory_pressure_settings = WebKit.MemoryPressureSettings()
    memory_pressure_settings.set_memory_limit(2048)
    memory_pressure_settings.set_poll_interval(10)
    memory_pressure_settings.set_kill_threshold(1)

    @classproperty
    def default(cls):
        if hasattr(cls, "_default"): return cls._default
        cls._default = cls(memory_pressure_settings=cls.memory_pressure_settings)
        cls._default.set_web_process_extensions_directory(App.default.data_folder.get_path())
        return cls._default

    def __new__(cls, default=True, **kwargs):
        if hasattr(cls, "_default"):
            kwargs.setdefault("memory_pressure_settings", cls.memory_pressure_settings)
            kwargs.setdefault("time_zone_override", None)
        self = WebKit.WebContext(**kwargs)
        if hasattr(cls, "_default"):
            self.set_automation_allowed(cls._default.is_automation_allowed())
            self.set_cache_model(cls._default.get_cache_model())
            c = getattr(cls._default, "preferred_languages", None)
            self.preferred_languages = c
            self.set_spell_checking_enabled(cls._default.get_spell_checking_enabled())
            self.set_spell_checking_languages(cls._default.get_spell_checking_languages())
            self.set_web_process_extensions_directory(App.default.data_folder.get_path())
        return self

class NetworkSession:
    @classproperty
    def default(cls):
        if hasattr(cls, "_default"): return cls._default
        cls._default = WebKit.NetworkSession.new(App.default.data_folder.peek_path())
        cls._default.set_memory_pressure_settings(WebContext.memory_pressure_settings)
        cls._default.set_persistent_credential_storage_enabled(False)
        cls._default.set_tls_errors_policy(WebKit.TLSErrorsPolicy.IGNORE)
        cls._default.get_cookie_manager().set_persistent_storage(App.default.data_folder.get_child("storage/cookies").peek_path(), WebKit.CookiePersistentStorage.TEXT)
        cls._default.connect("download-started", Downloads.handle_started)
        return cls._default

    def __new__(cls, ephemeral=False):
        if ephemeral:
            self = WebKit.NetworkSession.new_ephemeral()
            self.set_memory_pressure_settings(WebContext.memory_pressure_settings)
            self.set_persistent_credential_storage_enabled(False)
            self.set_tls_errors_policy(WebKit.TLSErrorsPolicy.IGNORE)
            self.connect("download-started", Downloads.handle_started)
        else:
            self = cls.default
        return self

class UserContentManager:
    def __new__(cls): return cls.default

    @classproperty
    def default(cls):
        if hasattr(cls, "_default"): return cls._default
        cls._default = WebKit.UserContentManager.new()
        UserContentManager.ublock_filters()
        return cls._default

    @staticmethod
    def do_fetch_identifiers(a, r, clear=False):
        UserContentManager.default.remove_all_scripts()
        UserContentManager.default.remove_all_filters()
        UserContentManager.default.remove_all_style_sheets()
        identifiers = a.fetch_identifiers_finish(r)
        for i in identifiers:
            if clear: a.remove(i, None, UserContentManager.do_remove)
            else: a.load(i, None, UserContentManager.load_add_filter)
        f = Path(App.default.data_folder, "filters")
        if exists(f):
            for i in list_dir(f):
                if i in identifiers: continue
                a.save_from_file(i, Gio.File.new_for_path(Path(f, i)), None, UserContentManager.save_add_filter)
        l = []
        f = Path(App.default.data_folder, "style.css")
        if exists(f): l.append(f)
        f = Path(App.default.data_folder, "styles")
        if exists(f):
            for i in list_dir(f): l.append(Path(f, i))
        for i in l: UserContentManager.default.add_style_sheet(WebKit.UserStyleSheet.new(get_contents(i).decode(), WebKit.UserContentInjectedFrames.ALL_FRAMES, WebKit.UserStyleLevel.USER))
        f = Path(App.default.data_folder, "scripts")
        if exists(f):
            for i in list_dir(f): UserContentManager.default.add_script(WebKit.UserScript.new(get_contents(Path(f, i)).decode(), WebKit.UserContentInjectedFrames.ALL_FRAMES, WebKit.UserScriptInjectionTime.START))

    @staticmethod
    def do_remove(a, r): a.remove_finish(r)

    @staticmethod
    def load_add_filter(a, r):
        try: UserContentManager.default.add_filter(a.load_finish(r))
        except: pass

    @staticmethod
    def save_add_filter(a, r):
        try: UserContentManager.default.add_filter(a.save_from_file_finish(r))
        except: pass

    @staticmethod
    def ublock_filters(*_):
        f = Path(CACHE, "webkitgtk", "filters")
        files = ("combined-part1.json", "combined-part2.json")
        if App.default.lookup_action("ublock-filters").get_state().unpack():
            from json import loads as json
            from hashlib import file_digest
            Online.headers.setdefault("User-Agent", "Web")
            result = Online.Request("https://api.github.com/repos/bnema/ublock-webkit-filters/releases/latest")
            if result:
                result = json(result)
                for i in result.get("assets", []):
                    if i.get("name", "none") in files:
                        file = Path(f, i["name"])
                        e = exists(file)
                        if e and i["digest"].split(":", 1)[-1] != file_digest(open(file, "rb"), "sha256").hexdigest() or not e: set_contents(file, contents=Online.Request(i["browser_download_url"]))
            else: Task.invoke(Toast, "Couldn't fetch uBlock Filters")
        else:
            for i in files:
                i = Path(f, i)
                if exists(i): delete(i)
        WebKit.UserContentFilterStore.new(f).fetch_identifiers(None, UserContentManager.do_fetch_identifiers, True)

def id_sort(i): return i["ID"]

def start():
    d = App.default.data.read(table="Windows", column="ID", force_tuple=True)
    if not d:
        App.default.data.set_default(table="Windows", conditions="ID = '1'", values=(1,), names=("ID",))
        d = [1]
    for i in d: Window(i)

def activate(a):
    if a.get_active_window(): a.get_active_window().present()
    else: return open_files(ARGS[1:])

def bitwise_or_loop(vals):
    acc = 0
    for v in vals:
        acc |= v
    return acc

def file_open(a, files, *_): open_files(files)

def do_open_uri(p, r):
    if r != "confirm": return
    uris = str_to_list(p.get_extra_child().get_row(0).get_text())
    if uris: open_files(uris)
def open_uris(*_):
    group = Adw.PreferencesGroup()
    group.add(URIRow())
    Prompt(callback=do_open_uri, confirm_callback=False, heading="Open URIs", extra_child=group).present()

def overview(*_):
    visible_child = App.default.get_active_window().stack.get_visible_child()
    visible_child.overview.set_open(not visible_child.overview.get_open())

def reopen_tab(*_):
    if Tab.closed:
        p = Tab.closed.pop(-1)
        while p in Tab.closed: Tab.closed.remove(p)
        Tab.create(uri=p)
        App.default.lookup_action("reopen-tab").set_enabled(bool(Tab.closed))

def window_removed(a, w):
    if not isinstance(w, Window): return
    for v in w.stack:
        for i in v.get_pages(): i.get_child().unload(force=True)
    if not a.get_active_window(): return
    App.default.data.delete(table="Windows", conditions="ID = ?", conds=(w.get_id(),))

def do_shutdown(a):
    e = Event()
    SiteDataExceptions.clear(e)
    e.wait()
    App.default.data.data.close()
    a.quit()
    App.default.quit()
    close_transmission()
    if not GLib.getenv("FLATPAK_ID"):
        GLib.spawn_command_line_async("killall -9 WebKitWebProcess")
        GLib.spawn_command_line_async("killall -9 WebKitNetworkProcess")

def start_shutdown(a): Task(do_shutdown, a).start()

def shutdown(a):
    for i in Tab.get_all(): i.unload(force=True)
    app = Gio.Application.new(None, Gio.ApplicationFlags.DEFAULT_FLAGS)
    app.connect("activate", start_shutdown)
    app.hold()
    app.run()

def close_transmission(*_):
    GLib.spawn_command_line_sync(TRANSMISSION.replace("daemon", "remote") + " --exit")
    GLib.spawn_command_line_sync("pkill -f transmission-daemon")
    if hasattr(App, "Transmission"):
        GLib.spawn_command_line_sync(f"kill {App.Transmission}")
        del App.Transmission

def open_transmission(*_):
    if not exists(TRANSMISSION): return
    for i in Tab.get_all():
        if i.uri == "Transmission":
            i.get_ancestor(Adw.TabView).set_selected_page(i.tab)
            return
    t = Tab.create(uri="Transmission")
    t.get_ancestor(Adw.TabView).set_selected_page(t.tab)

def open_files(files):
    if not Window.current: start()
    t = None
    for i in files:
        i = i if isinstance(i, str) else i.get_uri() if hasattr(i, "get_uri") else str(i)
        if i.startswith("magnet:?") or Gio.content_type_guess(i)[0] == "application/x-bittorrent":
            if not hasattr(App, "Transmission"):
                if not hasattr(App, "to_open"):
                    App.to_open = []
                App.to_open.append(i)
                open_transmission()
                continue
            open_transmission()
            if i.startswith("file://"):
                i = uri_decode(i)
            GLib.spawn_command_line_sync(TRANSMISSION.replace("daemon", "remote") + f" --add '{i}'")
        else: Tab.create(uri=(("file://" if not i.startswith(("file://", "https://", "http://")) else "") + i))
    return App.default.get_active_window().present()

INFO = {
    "ID": "io.github.kirukomaru11.Web",
    "Developer": "きるこ丸11号",
    "Comment": "Browse the web",
    "Issue URL": "https://github.com/kirukomaru11/Web/issues",
    "Website": "https://github.com/kirukomaru11/Web",
    "Keywords": ["Internet", "Browser"],
    "Categories": ["Network"],
    "Branding": ["#90b6e4", "#e2ecf8"],
    "MimeTypes": ["application/pdf", "text/html", "x-scheme-handler/http", "x-scheme-handler/https", "x-scheme-handler/magnet", "application/x-bittorrent"] + [i for i in Gio.content_types_get_registered() if i.startswith(("audio/", "video/", "image/"))],
}

TRANSMISSION = "/app/bin/transmission-daemon" if FLATPAK_ID else "/usr/bin/transmission-daemon"

APP_CSS = r"""
.downloads popover { min-width: 360px; }
.downloads download { padding: 6px; border-spacing: 8px; }
.downloads download progressbar { padding: 0px 2px;}
.downloads download box { margin: 0px; border-spacing: 6px; }
.downloads listview { border-spacing: 8px; padding: 0px; }
.downloads listview row { margin: 0px; padding: 0px; background: color-mix(in srgb, currentColor 5%, transparent); }
.downloads scrolledwindow scrollbar range trough slider { min-height: 28px; }

dialog.settings stack > box { padding: 14px; border-spacing: 14px; }

dialog tagrow { margin: 10px; }

find { margin: 10px 0px; backdrop-filter: blur(20px) brightness(0.9); background: color-mix(in srgb, var(--window-bg-color) 35%, transparent); border-radius: 9px; }
find popover button { outline: none; font-weight: normal; }

tabbar:not(.visible) separator { opacity: 0; }
tabbar:not(.visible) tab:selected:not(:hover) { background: none; }
tabbar:not(.visible) tab:selected:not(:hover) button,
tabbar:not(.visible) tab:selected:not(:hover) button image { -gtk-icon-source: none; -gtk-icon-size: 1px; opacity: 0; padding: 0px; margin: 0px; min-height: 0px; min-width: 0px; }

.bottom-bar search { margin: 4px 6px 2px 6px; }
search {
 min-height: 34px;
 border-spacing: 8px;
 border-radius: 10px;
 background: color-mix(in srgb, currentColor 8%, transparent);
 outline: 0 solid transparent;
 outline-offset: 4px;
 transition: outline-color 200ms cubic-bezier(0.25, 0.46, 0.45, 0.94), outline-width 200ms cubic-bezier(0.25, 0.46, 0.45, 0.94), outline-offset 200ms cubic-bezier(0.25, 0.46, 0.45, 0.94);
}
search button { outline: none; font-weight: normal; }
search placeholder { opacity: var(--dim-opacity); }
search.has-search { outline-color: var(--search-color); }
search.has-search,
search:not(.has-search):focus-within { outline-width: 2px; outline-offset: -2px; }
search:not(.has-search):focus-within { outline-color: color-mix(in srgb, var(--accent-color) 50%, transparent); }
search > stack > text { margin: 0px 10px; }

.searches listview { margin: 0px; padding: 0px; }
.searches listview row { margin: 0px; padding: 0px; }
.searches listview row label { padding: 0px 8px; border-radius: 9px; }
.searches > contents > box { border-spacing: 10px; }
.searches scrolledwindow scrollbar range trough slider { min-height: 18px; }

:drop(active) label.highlight { box-shadow: 0 0 0 1px var(--accent-bg-color) inset; }
"""

CAMEL_CASE_SPLIT = Regex(r"[A-Z](?:[a-z]+|[A-Z]*(?=[A-Z]|$))")

SHORTCUTS = {
        "Tabs": {
            "New": "app.new-tab",
            "Close": "app.close-tab",
            "Reopen Closed": "app.reopen-tab",
            "Move to Other Bar": "app.move-tab",
            "Overview": "app.overview",
            "Reload": "F5 <primary>r",
            **Adw.TabView.shortcuts
        },
        "Search": {
            "Focus Search": "app.search",
            "Search": "Return",
            "Search in Background": "<shift>Return",
            "Hide Autocomplete/Show Preview": "Escape",
            "Paste (Files/URI)": "<primary>v",
        },
        "Window": {
            "New": "app.new-window",
            "Open URIs": "app.open-uris",
            "WebKit Features": "app.webkit-features",
            "Extra Settings": "app.extra-settings",
            "Find": "win.find-bar",
            "Fullscreen": "win.fullscreen",
            "Second Bar": "win.second-view"
        }
}

DATA_INIT = """
CREATE TABLE IF NOT EXISTS Searches (ID INTEGER, Name TEXT NOT NULL UNIQUE, URL TEXT, Shortcut TEXT, Color TEXT);
CREATE TABLE IF NOT EXISTS Settings (Key TEXT PRIMARY KEY NOT NULL, Value TEXT);
CREATE TABLE IF NOT EXISTS Tabs (Window INTEGER NOT NULL DEFAULT 1, TabView INTEGER NOT NULL DEFAULT 1, ID INTEGER, URI TEXT DEFAULT '', UNIQUE ('Window', 'TabView', 'ID'), FOREIGN KEY (Window) REFERENCES Windows(ID) ON DELETE CASCADE ON UPDATE CASCADE);
CREATE TABLE IF NOT EXISTS Windows (ID INTEGER PRIMARY KEY AUTOINCREMENT, 'Default Width' INTEGER NOT NULL DEFAULT 360, 'Default Height' INTEGER NOT NULL DEFAULT 760, 'Fullscreen' INTEGER NOT NULL DEFAULT 0, 'Second View' INTEGER NOT NULL DEFAULT 1, Maximized INTEGER NOT NULL DEFAULT 0);
"""

ACTIONS = [
    ("open-transmission", open_transmission),
    ("open-uris", open_uris, "<primary><shift>o"),
    ("overview", overview, "<primary>o"),
    ("reopen-tab", reopen_tab, "<primary><shift>t"),
    ("new-window", Window.create, "<primary>n"),
    ("new-tab", Tab.create, "<primary>t"),
    ("move-tab", Tab.operation, "<primary>d"),
    ("search", Search.focus, "<primary>s"),
    ("close-tab", Tab.operation, "<primary>w"),
    ("webkit-features", WebKitFeatures.show, "<primary><shift>f"),
    ("extra-settings", ExtraSettings.show, "<primary>p"),
    ("site-data-exceptions", SiteDataExceptions.show),
    ("inspector", Tab.operation, "F12")
]

for i in ("move-tab", "close-tab", "mute-tab", "copy-tab", "tab-switch-session", "tab-unload", "set-user-agent", "set-preferred-languages", "set-time-zone-override"): ACTIONS.append((f"context-{i}", Tab.operation))

def main():
    App(info=INFO,
       shortcuts=SHORTCUTS,
       data=DATA_INIT,
       file_open=file_open,
       activate=activate,
       shutdown=shutdown,
       window_removed=window_removed,
       data_folder=Gio.File.new_for_path(get_parent(DATA)),
       actions=ACTIONS)
    for i, v in {"uBlock Filters": False}.items(): App.default.data.persist_action(App.default, i, (i, v), "Settings", "Value", "Key = ?", (i,))
    App.default.lookup_action("ublock-filters").connect("notify::state", UserContentManager.ublock_filters)
    App.default.add_action(Gio.SimpleAction.new("context-search", get_variant("").get_type()))
    App.default.lookup_action("context-search").connect("activate", Tab.context_search)
    UserContentManager()
    SiteDataExceptions.clear()
    WebKitFeatures()
    ExtraSettings()
    App.default.set_accels_for_action("win.find-bar", ["<primary>f"])
    App.default.set_accels_for_action("win.fullscreen", ["F11"])
    App.default.set_accels_for_action("win.second-view", ["<primary><shift>b"])
    App.default.lookup_action("reopen-tab").set_enabled(False)
    Searches.list.default.get_model().extend(App.default.data.read(table="Searches", return_dict=True, force_tuple=True))
    App.default.main(css=APP_CSS)

if __name__ == "__main__": main()