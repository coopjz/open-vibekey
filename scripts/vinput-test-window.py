import gi
gi.require_version('Gtk','3.0')
from gi.repository import Gtk
w=Gtk.Window(title='VibeKey · fcitx5-vinput 语音实测')
w.set_default_size(720,380);w.connect('destroy',Gtk.main_quit)
b=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=12);b.set_border_width(20);w.add(b)
l=Gtk.Label(label='点击下面输入框，按住 VibeKey 上键说中文，松开后等待文字出现。\n本窗口使用独立 Fcitx5；其他程序继续使用原输入法。');l.set_line_wrap(True);b.pack_start(l,False,False,0)
s=Gtk.ScrolledWindow();v=Gtk.TextView();v.set_wrap_mode(Gtk.WrapMode.WORD_CHAR);s.add(v);b.pack_start(s,True,True,0)
w.show_all();v.grab_focus();Gtk.main()
