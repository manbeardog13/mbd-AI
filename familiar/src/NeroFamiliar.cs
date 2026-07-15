// Nero Desktop Familiar — PROTOTYPE (placeholder art)
// Native WPF host, compiled with the in-box .NET Framework csc.exe (zero install).
// Proves: per-pixel transparency, click-through + no-activate, roaming movement,
// tray controls, aggressive idle suspension, fullscreen/battery auto-pause,
// drag-to-move, a file-based host event interface, and clean shutdown.
// NO LLM, NO network, NO autostart, no admin.

using System;
using System.IO;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Media;
using System.Windows.Media.Imaging;
using System.Windows.Media.Effects;
using System.Windows.Interop;
using System.Windows.Threading;
using System.Runtime.InteropServices;
using WinForms = System.Windows.Forms;
using Drawing = System.Drawing;

namespace NeroFamiliar
{
    public enum St { Idle, Walk, Sleep, Listen, Think, Speak, Celebrate, Concern, Summon, Dismiss }

    public class FamiliarWindow : Window
    {
        // ---- Win32 ----
        const int GWL_EXSTYLE = -20;
        const int WS_EX_TRANSPARENT = 0x20, WS_EX_LAYERED = 0x80000, WS_EX_NOACTIVATE = 0x8000000, WS_EX_TOOLWINDOW = 0x80;
        [DllImport("user32.dll")] static extern int GetWindowLong(IntPtr h, int i);
        [DllImport("user32.dll")] static extern int SetWindowLong(IntPtr h, int i, int v);
        [DllImport("user32.dll")] static extern IntPtr GetForegroundWindow();
        [DllImport("user32.dll")] static extern bool GetWindowRect(IntPtr h, out RECT r);
        [StructLayout(LayoutKind.Sequential)] struct RECT { public int L, T, R, B; }
        [StructLayout(LayoutKind.Sequential)] struct SPS { public byte ac, bf, bl, flag; public int life, full; }
        [DllImport("kernel32.dll")] static extern bool GetSystemPowerStatus(out SPS s);

        // ---- state ----
        readonly Image _img = new Image();
        readonly Border _bubble;
        readonly TextBlock _bubbleText = new TextBlock();
        readonly DispatcherTimer _t = new DispatcherTimer();
        readonly DropShadowEffect _glow;
        ImageSource[] _idle, _walk;
        int _frame;
        St _state = St.Summon;
        double _x, _y, _dir = 1, _speed = 2.2;
        bool _paused, _hidden, _effects = true, _interactive;
        int _observe;              // ticks to pause and "observe"
        double _fade = 0;          // for summon/dismiss
        WinForms.NotifyIcon _tray;
        FileSystemWatcher _watch;
        string _runtimeDir, _cmdFile, _settings;
        int _bubbleTicks;

        public FamiliarWindow()
        {
            // window: borderless, per-pixel transparent, topmost, off-taskbar
            WindowStyle = WindowStyle.None; AllowsTransparency = true; Background = Brushes.Transparent;
            ResizeMode = ResizeMode.NoResize; ShowInTaskbar = false; Topmost = true;
            Width = 220; Height = 240; Title = "Nero Familiar";

            _glow = new DropShadowEffect { Color = Color.FromRgb(150, 120, 255), BlurRadius = 28, ShadowDepth = 0, Opacity = 0.75 };
            _img.Effect = _glow; _img.Stretch = Stretch.Uniform;

            _bubbleText.Foreground = new SolidColorBrush(Color.FromRgb(230, 224, 255));
            _bubbleText.FontFamily = new FontFamily("Segoe UI"); _bubbleText.FontSize = 12; _bubbleText.TextWrapping = TextWrapping.Wrap; _bubbleText.MaxWidth = 190;
            _bubble = new Border {
                Background = new SolidColorBrush(Color.FromArgb(210, 18, 16, 30)),
                BorderBrush = new SolidColorBrush(Color.FromArgb(180, 150, 120, 255)), BorderThickness = new Thickness(1),
                CornerRadius = new CornerRadius(10), Padding = new Thickness(10, 6, 10, 6),
                Child = _bubbleText, Visibility = Visibility.Collapsed,
                HorizontalAlignment = HorizontalAlignment.Center, VerticalAlignment = VerticalAlignment.Top, Margin = new Thickness(0, 2, 0, 0)
            };

            var grid = new Grid();
            grid.Children.Add(_img);
            grid.Children.Add(_bubble);
            Content = grid;

            // paths (assets + runtime live beside the exe's parent 'familiar' folder)
            string baseDir = AppDomain.CurrentDomain.BaseDirectory;                 // ...\familiar\bin
            string root = Directory.GetParent(baseDir.TrimEnd('\\')).FullName;      // ...\familiar
            string art = Path.Combine(root, "assets", "placeholder");
            _runtimeDir = Path.Combine(root, "runtime");
            Directory.CreateDirectory(_runtimeDir);
            _cmdFile = Path.Combine(_runtimeDir, "command.txt");
            _settings = Path.Combine(_runtimeDir, "settings.ini");
            LoadFrames(art);
            LoadSettings();

            // start bottom-left of the work area (respects taskbar)
            var wa = SystemParameters.WorkArea;
            _x = wa.Left + 40; _y = wa.Bottom - Height - 4;
            Left = _x; Top = _y;

            Loaded += (s, e) => { BuildTray(); SetupWatcher(); };
            SourceInitialized += OnInit;
            MouseLeftButtonDown += (s, e) => { if (_interactive) { try { DragMove(); } catch { } } };

            _t.Tick += Tick;
            SetInterval();
            _t.Start();
        }

        void LoadFrames(string art)
        {
            Func<string, ImageSource> L = f => {
                var p = Path.Combine(art, f);
                if (!File.Exists(p)) return null;
                var bi = new BitmapImage(); bi.BeginInit(); bi.CacheOption = BitmapCacheOption.OnLoad;
                bi.UriSource = new Uri(p); bi.EndInit(); bi.Freeze(); return bi;
            };
            _idle = new[] { L("idle_0.png"), L("idle_1.png") };
            _walk = new[] { L("walk_0.png"), L("walk_1.png"), L("walk_2.png"), L("walk_3.png") };
            _img.Source = _idle[0];
        }

        void OnInit(object s, EventArgs e)
        {
            var h = new WindowInteropHelper(this).Handle;
            int ex = GetWindowLong(h, GWL_EXSTYLE) | WS_EX_LAYERED | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE;
            SetWindowLong(h, GWL_EXSTYLE, ex);
            ApplyClickThrough();
        }

        void ApplyClickThrough()
        {
            var h = new WindowInteropHelper(this).Handle; if (h == IntPtr.Zero) return;
            int ex = GetWindowLong(h, GWL_EXSTYLE);
            if (_interactive) ex &= ~WS_EX_TRANSPARENT; else ex |= WS_EX_TRANSPARENT;
            SetWindowLong(h, GWL_EXSTYLE, ex);
        }

        // ---- animation + roaming ----
        void SetInterval()
        {
            int ms = 180;                                   // idle
            if (_state == St.Walk) ms = 66;                 // ~15fps while moving
            if (_state == St.Summon || _state == St.Dismiss) ms = 40;
            if (_paused || _hidden || _state == St.Sleep) ms = 1000; // suspend-ish: cheap heartbeat
            _t.Interval = TimeSpan.FromMilliseconds(ms);
        }

        bool FullscreenAppActive()
        {
            var fg = GetForegroundWindow();
            var self = new WindowInteropHelper(this).Handle;
            if (fg == IntPtr.Zero || fg == self) return false;
            RECT r; if (!GetWindowRect(fg, out r)) return false;
            double sw = SystemParameters.PrimaryScreenWidth, sh = SystemParameters.PrimaryScreenHeight;
            return (r.R - r.L) >= sw - 2 && (r.B - r.T) >= sh - 2;
        }
        bool BatterySaver() { SPS s; return GetSystemPowerStatus(out s) && s.flag == 1; }

        void Tick(object s, EventArgs e)
        {
            // auto-pause conditions (checked cheaply every tick)
            bool suspend = FullscreenAppActive() || BatterySaver();
            if (suspend && Visibility == Visibility.Visible && _state != St.Sleep) { Visibility = Visibility.Hidden; }
            else if (!suspend && !_hidden && Visibility == Visibility.Hidden && _state != St.Sleep) { Visibility = Visibility.Visible; }
            if (suspend) { SetInterval(); return; }
            if (_paused || _hidden) { SetInterval(); return; }

            // fade for summon/dismiss
            if (_state == St.Summon) { _fade += 0.08; Opacity = Math.Min(1, _fade); if (_fade >= 1) Go(St.Idle); }
            else if (_state == St.Dismiss) { _fade -= 0.06; Opacity = Math.Max(0, _fade); if (_fade <= 0) { Visibility = Visibility.Hidden; _hidden = true; Go(St.Idle); } }

            _frame++;
            if (_state == St.Walk)
            {
                _img.Source = _walk[_frame % _walk.Length];
                _x += _dir * _speed;
                var wa = SystemParameters.WorkArea;
                if (_x < wa.Left + 8) { _x = wa.Left + 8; _dir = 1; _img.RenderTransform = null; }
                else if (_x > wa.Right - Width - 8) { _x = wa.Right - Width - 8; _dir = -1; }
                _img.RenderTransformOrigin = new Point(0.5, 0.5);
                _img.RenderTransform = new ScaleTransform(_dir, 1);
                Left = _x;
                if (--_observe <= 0 && (_frame % 6 == 0)) MaybeChangeGait();
            }
            else if (_state == St.Idle)
            {
                _img.Source = _idle[(_frame / 3) % _idle.Length];   // slow breathing
                if (--_observe <= 0) MaybeChangeGait();
            }
            else if (_state == St.Sleep) { _img.Source = _idle[0]; _img.Opacity = 0.55; }

            if (_bubbleTicks > 0 && --_bubbleTicks == 0) _bubble.Visibility = Visibility.Collapsed;
            SetInterval();
        }

        readonly Random _rng = new Random();
        void MaybeChangeGait()
        {
            _observe = _rng.Next(20, 70);
            if (_state == St.Idle && _rng.NextDouble() < 0.6) Go(St.Walk);
            else if (_state == St.Walk && _rng.NextDouble() < 0.4) Go(St.Idle);
            if (_rng.NextDouble() < 0.3) _dir = _rng.NextDouble() < 0.5 ? -1 : 1;
        }

        void Go(St st)
        {
            _state = st; _img.Opacity = 1;
            if (st == St.Summon) { _fade = 0; Opacity = 0; Visibility = Visibility.Visible; _hidden = false; }
            SetInterval();
        }

        void Bubble(string text, int ticks)
        {
            _bubbleText.Text = text; _bubble.Visibility = Visibility.Visible; _bubbleTicks = ticks;
        }

        // ---- host event interface (file-based, event-driven = near-zero idle) ----
        void SetupWatcher()
        {
            try {
                _watch = new FileSystemWatcher(_runtimeDir, "command.txt") { NotifyFilter = NotifyFilters.LastWrite | NotifyFilters.CreationTime, EnableRaisingEvents = true };
                _watch.Changed += OnCmd; _watch.Created += OnCmd;
            } catch { }
        }
        void OnCmd(object s, FileSystemEventArgs e)
        {
            string raw = ""; try { System.Threading.Thread.Sleep(30); raw = File.ReadAllText(_cmdFile).Trim(); } catch { return; }
            if (raw.Length == 0) return;
            Dispatcher.Invoke(() => Dispatch(raw));
        }
        // documented commands: summon | listen | think | speak|msg | celebrate | concern | sleep | dismiss
        void Dispatch(string raw)
        {
            string cmd = raw, arg = "";
            int bar = raw.IndexOf('|'); if (bar >= 0) { cmd = raw.Substring(0, bar).Trim(); arg = raw.Substring(bar + 1).Trim(); }
            switch (cmd.ToLowerInvariant())
            {
                case "summon": Go(St.Summon); Bubble("…", 30); break;
                case "listen": Go(St.Listen); Bubble("listening", 40); Go(St.Idle); break;
                case "think": Go(St.Think); Bubble("thinking…", 40); Go(St.Idle); break;
                case "speak": Go(St.Speak); Bubble(arg.Length > 0 ? arg : "…", 90); Go(St.Idle); break;
                case "celebrate": Go(St.Celebrate); Bubble("✦", 40); Go(St.Idle); break;
                case "concern": Go(St.Concern); Bubble("hm.", 40); Go(St.Idle); break;
                case "sleep": Go(St.Sleep); break;
                case "dismiss": Go(St.Dismiss); break;
                case "wake": _hidden = false; Visibility = Visibility.Visible; Go(St.Idle); break;
                default: break;
            }
        }

        // ---- tray controls ----
        void BuildTray()
        {
            _tray = new WinForms.NotifyIcon { Text = "Nero Familiar", Visible = true, Icon = MakeIcon() };
            var m = new WinForms.ContextMenuStrip();
            var pause = new WinForms.ToolStripMenuItem("Pause");
            pause.Click += (s, e) => { _paused = !_paused; pause.Text = _paused ? "Resume" : "Pause"; SetInterval(); };
            var sleep = new WinForms.ToolStripMenuItem("Sleep"); sleep.Click += (s, e) => Go(_state == St.Sleep ? St.Idle : St.Sleep);
            var hide = new WinForms.ToolStripMenuItem("Hide");
            hide.Click += (s, e) => { _hidden = !_hidden; Visibility = _hidden ? Visibility.Hidden : Visibility.Visible; hide.Text = _hidden ? "Show" : "Hide"; SetInterval(); };
            var inter = new WinForms.ToolStripMenuItem("Interactive (allow drag)"); inter.CheckOnClick = true;
            inter.Click += (s, e) => { _interactive = inter.Checked; ApplyClickThrough(); };
            var fx = new WinForms.ToolStripMenuItem("Disable Effects"); fx.CheckOnClick = true;
            fx.Click += (s, e) => { _effects = !fx.Checked; _img.Effect = _effects ? _glow : null; SaveSettings(); };
            var exit = new WinForms.ToolStripMenuItem("Exit"); exit.Click += (s, e) => Shutdown();
            m.Items.AddRange(new WinForms.ToolStripItem[] { pause, sleep, hide, inter, fx, new WinForms.ToolStripSeparator(), exit });
            _tray.ContextMenuStrip = m;
            _tray.MouseDoubleClick += (s, e) => { _hidden = false; Visibility = Visibility.Visible; Go(St.Summon); };
        }

        Drawing.Icon MakeIcon()
        {
            var bmp = new Drawing.Bitmap(32, 32);
            using (var g = Drawing.Graphics.FromImage(bmp)) {
                g.SmoothingMode = Drawing.Drawing2D.SmoothingMode.AntiAlias; g.Clear(Drawing.Color.Transparent);
                g.FillEllipse(new Drawing.SolidBrush(Drawing.Color.FromArgb(230, 20, 16, 34)), 4, 4, 24, 24);
                g.FillEllipse(new Drawing.SolidBrush(Drawing.Color.FromArgb(255, 170, 140, 255)), 11, 13, 4, 6);
                g.FillEllipse(new Drawing.SolidBrush(Drawing.Color.FromArgb(255, 170, 140, 255)), 18, 13, 4, 6);
            }
            return Drawing.Icon.FromHandle(bmp.GetHicon());
        }

        void LoadSettings()
        {
            try { if (File.Exists(_settings)) foreach (var line in File.ReadAllLines(_settings)) if (line.StartsWith("effects=")) _effects = line.EndsWith("1"); }
            catch { }
            _img.Effect = _effects ? _glow : null;
        }
        void SaveSettings() { try { File.WriteAllText(_settings, "effects=" + (_effects ? "1" : "0") + "\nautostart=0\n"); } catch { } }

        void Shutdown()
        {
            try { SaveSettings(); } catch { }
            try { if (_watch != null) { _watch.EnableRaisingEvents = false; _watch.Dispose(); } } catch { }
            try { _t.Stop(); } catch { }
            try { if (_tray != null) { _tray.Visible = false; _tray.Dispose(); } } catch { }
            Application.Current.Shutdown();
        }

        protected override void OnClosed(EventArgs e) { try { if (_tray != null) { _tray.Visible = false; _tray.Dispose(); } } catch { } base.OnClosed(e); }
    }

    public class Program
    {
        [STAThread]
        public static void Main()
        {
            var app = new Application { ShutdownMode = ShutdownMode.OnExplicitShutdown };
            var w = new FamiliarWindow();
            w.Show();
            app.Run();
        }
    }
}
