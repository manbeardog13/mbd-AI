// Nero Companion Runtime v2 — identity-locked, event-driven desktop familiar.
// Native WPF, explicit launch only. No model, network, voice, shell, gate, or autostart.

using System;
using System.Collections;
using System.Collections.Generic;
using System.IO;
using System.Reflection;
using System.Runtime.InteropServices;
using System.Security.Cryptography;
using System.Web.Script.Serialization;
using System.Threading;
using System.Windows;
using System.Windows.Automation;
using System.Windows.Automation.Peers;
using System.Windows.Controls;
using System.Windows.Input;
using System.Windows.Interop;
using System.Windows.Media;
using System.Windows.Media.Effects;
using System.Windows.Media.Imaging;
using System.Windows.Threading;
using WinForms = System.Windows.Forms;
using Drawing = System.Drawing;

[assembly: AssemblyTitle("Nero Void Guardian Desktop Familiar")]
[assembly: AssemblyDescription("Opt-in, display-only Nero desktop familiar")]
[assembly: AssemblyProduct("Nero Desktop Familiar")]
[assembly: AssemblyCompany("Nero")]
[assembly: AssemblyVersion("2.0.0.0")]
[assembly: AssemblyFileVersion("2.0.0.0")]

namespace NeroFamiliar
{
    public enum St {
        BootArrival, IdleBreathe, IdleLookCursor, IdleBoredTailTwirl,
        IdleBananaGag, ListenNameCalled, Thinking, Speaking, ClaudeChannel,
        CodexBuild, DualAgentAscension, TaskSuccess, TaskFailure,
        AttentionRequired, CriticalAlert, RepositoryPush, RunToAnchor,
        DismissGoodnight, Hidden
    }

    sealed class StateDef
    {
        public readonly St State;
        public readonly bool Loop;
        public readonly int Fps, DurationMs, Priority;
        public readonly int[] Frames;
        public readonly St Next;
        public readonly bool MissingArt;
        public readonly string AccessibleLabel;

        public StateDef(St state, bool loop, int fps, int durationMs, int priority,
                        int[] frames, St next, bool missingArt, string label)
        {
            State = state; Loop = loop; Fps = fps; DurationMs = durationMs;
            Priority = priority; Frames = frames; Next = next;
            MissingArt = missingArt; AccessibleLabel = label;
        }
    }

    sealed class PendingEvent
    {
        public string Name, Label;
        public StateDef Definition;
        public DateTime Created;
    }

    public sealed class FamiliarWindow : Window
    {
        const int GWL_EXSTYLE = -20;
        const int WS_EX_TRANSPARENT = 0x20, WS_EX_LAYERED = 0x80000;
        const int WS_EX_NOACTIVATE = 0x8000000, WS_EX_TOOLWINDOW = 0x80;
        const int MaxQueueDepth = 32, CoalesceMilliseconds = 750;
        const int CellWidth = 192, CellHeight = 208;

        [DllImport("user32.dll")] static extern int GetWindowLong(IntPtr h, int i);
        [DllImport("user32.dll")] static extern int SetWindowLong(IntPtr h, int i, int v);
        [DllImport("user32.dll")] static extern IntPtr GetForegroundWindow();
        [DllImport("user32.dll")] static extern bool GetWindowRect(IntPtr h, out RECT r);
        [StructLayout(LayoutKind.Sequential)] struct RECT { public int L, T, R, B; }
        [StructLayout(LayoutKind.Sequential)] struct SPS { public byte ac, bf, bl, flag; public int life, full; }
        [DllImport("kernel32.dll")] static extern bool GetSystemPowerStatus(out SPS s);

        readonly Grid _root = new Grid();
        readonly Grid _character = new Grid();
        readonly Image _image = new Image();
        readonly Canvas _effectsLayer = new Canvas();
        readonly Border _bubble;
        readonly TextBlock _bubbleText = new TextBlock();
        readonly Border _mission;
        readonly TextBlock _missionState = new TextBlock();
        readonly TextBlock _missionDetail = new TextBlock();
        readonly TextBlock _stateBadge = new TextBlock();
        readonly TextBlock _screenReaderStatus = new TextBlock();
        readonly TextBlock _neroFx = EffectGlyph("◆", Color.FromRgb(255, 45, 170));
        readonly TextBlock _claudeFx = EffectGlyph("◌", Color.FromRgb(242, 184, 75));
        readonly TextBlock _codexFx = EffectGlyph("⬡", Color.FromRgb(141, 227, 255));
        readonly RotateTransform _claudeRotate = new RotateTransform();
        readonly RotateTransform _codexRotate = new RotateTransform();
        readonly ScaleTransform _spriteScale = new ScaleTransform(1, 1);
        readonly DispatcherTimer _timer = new DispatcherTimer();
        readonly DropShadowEffect _glow;
        readonly Dictionary<St, StateDef> _states = new Dictionary<St, StateDef>();
        readonly Dictionary<string, St> _events = new Dictionary<string, St>(StringComparer.OrdinalIgnoreCase);
        readonly Dictionary<string, DateTime> _lastEvent = new Dictionary<string, DateTime>(StringComparer.OrdinalIgnoreCase);
        readonly List<PendingEvent> _queue = new List<PendingEvent>();
        readonly BitmapSource[] _frames = new BitmapSource[16];
        readonly object _spoolLock = new object();

        StateDef _active;
        DateTime _activeSince;
        double _x, _targetX, _fade;
        bool _paused, _hidden, _effects = true, _interactive, _missionOpen;
        bool _reducedMotion, _contractValid;
        string _activeEvent = "";
        string _startupWarning = "";
        string _bubbleTarget = "";
        int _bubbleCursor;
        double _typeBudget;
        DateTime _bubbleUntil;
        DateTime _settleAt = DateTime.MaxValue;
        DateTime _zoomUntil = DateTime.MinValue;
        DateTime _nextIdleAt = DateTime.MaxValue;
        int _idleCursor, _displayScale = 1;
        BitmapSource _fallbackFrame;
        WinForms.NotifyIcon _tray;
        FileSystemWatcher _watch;
        string _runtimeDir, _eventDir, _settingsFile;

        static TextBlock EffectGlyph(string glyph, Color color)
        {
            return new TextBlock {
                Text = glyph, FontSize = 32, FontWeight = FontWeights.Bold,
                Foreground = new SolidColorBrush(color), Visibility = Visibility.Collapsed,
                Effect = new DropShadowEffect { Color = color, BlurRadius = 18, ShadowDepth = 0, Opacity = 0.9 }
            };
        }

        public FamiliarWindow()
        {
            WindowStyle = WindowStyle.None; AllowsTransparency = true;
            Background = Brushes.Transparent; ResizeMode = ResizeMode.NoResize;
            ShowInTaskbar = false; Topmost = true; Width = CellWidth; Height = 300;
            Title = "Nero Companion Runtime";

            _reducedMotion = !SystemParameters.ClientAreaAnimation;
            _glow = new DropShadowEffect {
                Color = Color.FromRgb(181, 51, 255), BlurRadius = 25,
                ShadowDepth = 0, Opacity = 0.72
            };
            _image.Effect = _glow; _image.Stretch = Stretch.None;
            _image.Width = CellWidth; _image.Height = CellHeight;
            _image.HorizontalAlignment = HorizontalAlignment.Left;
            _image.VerticalAlignment = VerticalAlignment.Top;
            _image.RenderTransformOrigin = new Point(0.5, 0.5);
            _image.RenderTransform = _spriteScale;
            RenderOptions.SetBitmapScalingMode(_image, BitmapScalingMode.NearestNeighbor);
            AutomationProperties.SetName(_image, "Nero, Void Guardian desktop familiar");
            AutomationProperties.SetLiveSetting(_screenReaderStatus, AutomationLiveSetting.Assertive);
            AutomationProperties.SetName(_screenReaderStatus, "Nero familiar status");

            BuildContract();
            _bubble = BuildBubble();
            _mission = BuildMissionPanel();
            BuildScene();

            string baseDir = AppDomain.CurrentDomain.BaseDirectory;
            string root = Directory.GetParent(baseDir.TrimEnd('\\')).FullName;
            _runtimeDir = Path.Combine(root, "runtime");
            _eventDir = Path.Combine(_runtimeDir, "command.d");
            _settingsFile = Path.Combine(_runtimeDir, "settings.ini");
            Directory.CreateDirectory(_runtimeDir);
            Directory.CreateDirectory(_eventDir);
            LoadAtlas(Path.Combine(root, "assets", "nero", "nero-voidcaster-v2.png"));
            ValidateContract(Path.Combine(root, "nero_companion_runtime_v2.json"));
            LoadSettings();

            var work = SystemParameters.WorkArea;
            _x = work.Right - Width - 24; _targetX = _x;
            Left = _x; Top = work.Bottom - Height - 6;

            Loaded += delegate {
                BuildTray();
                ApplyDisplayScale(_displayScale);
                if (_contractValid) SetupWatcher();
            };
            SourceInitialized += OnSourceInitialized;
            MouseEnter += delegate { ApplyCursorPose(true); };
            MouseMove += delegate { if (_interactive) ApplyCursorPose(true); };
            MouseLeave += delegate { ResetCursorPose(); ApplyVisualState(); };
            MouseRightButtonUp += delegate { if (_interactive && _root.ContextMenu != null) _root.ContextMenu.IsOpen = true; };
            MouseLeftButtonDown += OnMouseDown;
            PreviewKeyDown += delegate(object sender, KeyEventArgs e) {
                if (e.Key == Key.Escape) {
                    _bubble.Visibility = Visibility.Collapsed;
                    _bubbleTarget = ""; _bubbleText.Text = "";
                    e.Handled = true;
                }
            };

            _timer.Tick += Tick;
            Activate("runtime.started", _states[St.BootArrival],
                _startupWarning.Length > 0 ? _startupWarning : "Welcome back.");
            _timer.Start();
        }

        void BuildContract()
        {
            int[] breathe = { 0,1,2,3,4,5,6,7,6,5,4,3,2,1 };
            int[] attentive = { 8,9,10,11 };
            int[] action = { 12,13,14,15,14,13 };
            Add(St.BootArrival, false, 12, 1400, 70, breathe, St.IdleBreathe, true, "Nero is arriving");
            Add(St.IdleBreathe, true, 8, 0, 0, breathe, St.IdleBreathe, false, "Nero is idle");
            Add(St.IdleLookCursor, false, 10, 900, 5, attentive, St.IdleBreathe, false, "Nero is looking toward the cursor");
            Add(St.IdleBoredTailTwirl, false, 12, 1800, 5, breathe, St.IdleBreathe, true, "Nero is waiting patiently");
            Add(St.IdleBananaGag, false, 10, 2400, 5, breathe, St.IdleBreathe, true, "Nero has a question");
            Add(St.ListenNameCalled, false, 12, 650, 35, attentive, St.Thinking, false, "Nero heard you");
            Add(St.Thinking, true, 8, 0, 30, new int[] { 11,12,11,10 }, St.IdleBreathe, false, "Nero is thinking");
            Add(St.Speaking, true, 10, 0, 30, breathe, St.IdleBreathe, false, "Nero is speaking");
            Add(St.ClaudeChannel, true, 12, 0, 45, breathe, St.IdleBreathe, false, "Claude is active through Nero");
            Add(St.CodexBuild, true, 12, 0, 45, breathe, St.IdleBreathe, false, "Codex is building through Nero");
            Add(St.DualAgentAscension, true, 16, 0, 60, action, St.IdleBreathe, true, "Claude and Codex are both active");
            Add(St.TaskSuccess, false, 14, 1500, 50, action, St.IdleBreathe, false, "Task completion is confirmed");
            Add(St.TaskFailure, false, 12, 1700, 65, breathe, St.AttentionRequired, true, "A task failed");
            Add(St.AttentionRequired, true, 8, 0, 80, action, St.IdleBreathe, false, "Your action is required");
            Add(St.CriticalAlert, true, 12, 0, 100, breathe, St.IdleBreathe, true, "Critical system risk");
            Add(St.RepositoryPush, false, 14, 1200, 45, action, St.IdleBreathe, true, "Repository push is confirmed");
            Add(St.RunToAnchor, true, 14, 0, 25, breathe, St.IdleBreathe, false, "Nero is moving");
            Add(St.DismissGoodnight, false, 10, 1600, 40, breathe, St.Hidden, true, "Nero is leaving");
            Add(St.Hidden, true, 1, 0, -1, new int[0], St.IdleBreathe, false, "Nero is hidden");

            Map("runtime.started", St.BootArrival); Map("user.mentions_nero", St.ListenNameCalled);
            Map("nero.thinking", St.Thinking); Map("nero.speaking", St.Speaking);
            Map("claude.started", St.ClaudeChannel); Map("codex.started", St.CodexBuild);
            Map("agents.dual_active", St.DualAgentAscension); Map("task.succeeded", St.TaskSuccess);
            Map("task.failed", St.TaskFailure); Map("user.action_required", St.AttentionRequired);
            Map("system.critical", St.CriticalAlert); Map("git.push_succeeded", St.RepositoryPush);
            Map("pet.reposition", St.RunToAnchor); Map("pet.dismiss", St.DismissGoodnight);
            Map("all.work_complete", St.IdleBreathe);
        }

        void Add(St state, bool loop, int fps, int duration, int priority, int[] frames,
                 St next, bool missing, string label)
        {
            _states[state] = new StateDef(state, loop, fps, duration, priority, frames, next, missing, label);
        }
        void Map(string name, St state) { _events[name] = state; }

        Border BuildBubble()
        {
            _bubbleText.Foreground = new SolidColorBrush(Color.FromRgb(239, 233, 255));
            _bubbleText.FontFamily = new FontFamily("Segoe UI"); _bubbleText.FontSize = 12;
            _bubbleText.TextWrapping = TextWrapping.Wrap; _bubbleText.MaxWidth = 170;
            _bubbleText.LineHeight = 16;
            AutomationProperties.SetLiveSetting(_bubbleText, AutomationLiveSetting.Polite);
            var scroll = new ScrollViewer {
                Content = _bubbleText, MaxHeight = 160,
                VerticalScrollBarVisibility = ScrollBarVisibility.Auto,
                HorizontalScrollBarVisibility = ScrollBarVisibility.Disabled
            };
            return new Border {
                Background = new SolidColorBrush(Color.FromArgb(228, 12, 10, 23)),
                BorderBrush = new SolidColorBrush(Color.FromArgb(220, 255, 45, 170)),
                BorderThickness = new Thickness(1), CornerRadius = new CornerRadius(12),
                Padding = new Thickness(8, 6, 8, 6), Child = scroll,
                Visibility = Visibility.Collapsed, HorizontalAlignment = HorizontalAlignment.Center,
                VerticalAlignment = VerticalAlignment.Top, Margin = new Thickness(3, 0, 3, 0)
            };
        }

        void BuildScene()
        {
            _root.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(0) });
            _root.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(CellWidth) });
            Grid.SetColumn(_mission, 0); _root.Children.Add(_mission);

            _character.Width = CellWidth; _character.Height = CellHeight;
            _character.HorizontalAlignment = HorizontalAlignment.Left;
            _character.VerticalAlignment = VerticalAlignment.Bottom;
            _character.Children.Add(_image);
            _claudeFx.RenderTransformOrigin = new Point(0.5, 0.5); _claudeFx.RenderTransform = _claudeRotate;
            _codexFx.RenderTransformOrigin = new Point(0.5, 0.5); _codexFx.RenderTransform = _codexRotate;
            Canvas.SetLeft(_neroFx, 80); Canvas.SetTop(_neroFx, 82); _effectsLayer.Children.Add(_neroFx);
            Canvas.SetLeft(_claudeFx, 18); Canvas.SetTop(_claudeFx, 48); _effectsLayer.Children.Add(_claudeFx);
            Canvas.SetLeft(_codexFx, 146); Canvas.SetTop(_codexFx, 64); _effectsLayer.Children.Add(_codexFx);
            _stateBadge.FontSize = 11; _stateBadge.FontWeight = FontWeights.SemiBold;
            _stateBadge.Foreground = new SolidColorBrush(Color.FromRgb(223, 215, 242));
            _stateBadge.Background = new SolidColorBrush(Color.FromArgb(190, 12, 10, 23));
            _stateBadge.Padding = new Thickness(7, 3, 7, 3);
            Canvas.SetLeft(_stateBadge, 6); Canvas.SetTop(_stateBadge, 178); _effectsLayer.Children.Add(_stateBadge);
            _screenReaderStatus.Width = 1; _screenReaderStatus.Height = 1;
            _screenReaderStatus.Opacity = 0; _screenReaderStatus.IsHitTestVisible = false;
            Canvas.SetLeft(_screenReaderStatus, 0); Canvas.SetTop(_screenReaderStatus, 0);
            _effectsLayer.Children.Add(_screenReaderStatus);
            _character.Children.Add(_effectsLayer); _character.Children.Add(_bubble);
            Grid.SetColumn(_character, 1); _root.Children.Add(_character);
            _root.ContextMenu = BuildContextMenu();
            Content = _root;
        }

        Border BuildMissionPanel()
        {
            var stack = new StackPanel { Margin = new Thickness(18) };
            stack.Children.Add(new TextBlock {
                Text = "NERO / MISSION CONTROL", Foreground = new SolidColorBrush(Color.FromRgb(255, 45, 170)),
                FontFamily = new FontFamily("Segoe UI Semibold"), FontSize = 14
            });
            stack.Children.Add(new TextBlock {
                Text = "Void Guardian", Foreground = Brushes.White, FontSize = 22,
                Margin = new Thickness(0, 4, 0, 14)
            });
            _missionState.Foreground = new SolidColorBrush(Color.FromRgb(230, 220, 255));
            _missionState.FontSize = 13; stack.Children.Add(_missionState);
            _missionDetail.Foreground = new SolidColorBrush(Color.FromRgb(180, 174, 202));
            _missionDetail.FontSize = 11; _missionDetail.TextWrapping = TextWrapping.Wrap;
            _missionDetail.Margin = new Thickness(0, 10, 0, 0); stack.Children.Add(_missionDetail);
            stack.Children.Add(new TextBlock {
                Text = "Display-only familiar. Source systems remain authoritative; no gate or external action executes here.",
                Foreground = new SolidColorBrush(Color.FromRgb(140, 132, 164)), FontSize = 10,
                Margin = new Thickness(0, 16, 0, 0), TextWrapping = TextWrapping.Wrap
            });
            return new Border {
                Background = new SolidColorBrush(Color.FromArgb(242, 8, 8, 16)),
                BorderBrush = new SolidColorBrush(Color.FromArgb(220, 181, 51, 255)),
                BorderThickness = new Thickness(1), CornerRadius = new CornerRadius(16),
                Margin = new Thickness(6, 6, 10, 6), Child = stack, Visibility = Visibility.Collapsed
            };
        }

        ContextMenu BuildContextMenu()
        {
            var menu = new ContextMenu();
            var mission = new MenuItem { Header = "Mission Control" };
            mission.Click += delegate { ToggleMission(); };
            var pause = new MenuItem { Header = "Pause" };
            pause.Click += delegate { _paused = !_paused; pause.Header = _paused ? "Resume" : "Pause"; };
            var clear = new MenuItem { Header = "Clear active alert" };
            clear.Click += delegate { ClearLatchedAlert(); };
            var reduced = new MenuItem { Header = "Reduced motion", IsCheckable = true, IsChecked = _reducedMotion };
            reduced.Click += delegate { _reducedMotion = reduced.IsChecked; ApplyVisualState(); PulseEffects(); SaveSettings(); };
            var scale = BuildWpfScaleMenu();
            var hide = new MenuItem { Header = "Hide" }; hide.Click += delegate { Receive("pet.dismiss", "Goodnight."); };
            menu.Items.Add(mission); menu.Items.Add(pause); menu.Items.Add(clear);
            menu.Items.Add(reduced); menu.Items.Add(scale); menu.Items.Add(hide);
            return menu;
        }

        MenuItem BuildWpfScaleMenu()
        {
            var root = new MenuItem { Header = "Scale" };
            for (int value = 1; value <= 3; value++) {
                int selected = value;
                var item = new MenuItem { Header = value + "x" };
                item.Click += delegate { ApplyDisplayScale(selected); SaveSettings(); };
                root.Items.Add(item);
            }
            return root;
        }

        void LoadAtlas(string path)
        {
            _fallbackFrame = CreateFallbackFrame();
            UseFallbackFrames();
            try {
                if (!File.Exists(path)) throw new FileNotFoundException("sprite atlas missing", path);
                var bitmap = new BitmapImage(); bitmap.BeginInit();
                bitmap.CacheOption = BitmapCacheOption.OnLoad; bitmap.UriSource = new Uri(path);
                bitmap.EndInit(); bitmap.Freeze();
                if (bitmap.PixelWidth != 1536 || bitmap.PixelHeight != 416)
                    throw new InvalidDataException("sprite atlas must be 1536x416");
                for (int row = 0; row < 2; row++) for (int col = 0; col < 8; col++) {
                    var crop = new CroppedBitmap(bitmap, new Int32Rect(col * CellWidth, row * CellHeight, CellWidth, CellHeight));
                    crop.Freeze(); _frames[row * 8 + col] = crop;
                }
            } catch {
                _startupWarning = "Sprite atlas unavailable; safe fallback is active.";
            }
        }

        void UseFallbackFrames()
        {
            if (_fallbackFrame == null) _fallbackFrame = CreateFallbackFrame();
            for (int i = 0; i < _frames.Length; i++) _frames[i] = _fallbackFrame;
        }

        static BitmapSource CreateFallbackFrame()
        {
            var visual = new DrawingVisual();
            using (DrawingContext dc = visual.RenderOpen()) {
                var armor = new SolidColorBrush(Color.FromRgb(14, 13, 22));
                var magenta = new SolidColorBrush(Color.FromRgb(255, 45, 170));
                var violet = new SolidColorBrush(Color.FromRgb(181, 51, 255));
                var cyan = new SolidColorBrush(Color.FromRgb(141, 227, 255));
                dc.DrawEllipse(magenta, null, new Point(72, 55), 27, 39);
                dc.DrawEllipse(magenta, null, new Point(120, 55), 27, 39);
                dc.DrawEllipse(armor, new Pen(violet, 3), new Point(96, 112), 48, 65);
                dc.DrawRectangle(armor, new Pen(cyan, 3), new Rect(70, 66, 52, 15));
                dc.DrawEllipse(violet, null, new Point(96, 126), 7, 7);
                dc.DrawLine(new Pen(armor, 12), new Point(134, 74), new Point(165, 174));
                dc.DrawEllipse(armor, new Pen(cyan, 3), new Point(166, 178), 18, 25);
            }
            var bitmap = new RenderTargetBitmap(CellWidth, CellHeight, 96, 96, PixelFormats.Pbgra32);
            bitmap.Render(visual); bitmap.Freeze(); return bitmap;
        }

        void ValidateContract(string path)
        {
            try {
                string json = File.ReadAllText(path);
                object parsed = new JavaScriptSerializer().DeserializeObject(json);
                IDictionary root = parsed as IDictionary;
                IList states = root == null ? null : root["states"] as IList;
                IList events = root == null ? null : root["events"] as IList;
                IDictionary runtime = root == null ? null : root["runtime"] as IDictionary;
                IDictionary eventQueue = runtime == null ? null : runtime["eventQueue"] as IDictionary;
                _contractValid = root != null &&
                    Convert.ToString(root["specVersion"]) == "2.0.0" &&
                    Convert.ToString(root["id"]) == "nero-voidcaster" &&
                    ContractIdsMatch(states, "id", new string[] {
                        "boot_arrival","idle_breathe","idle_look_cursor","idle_bored_tail_twirl",
                        "idle_banana_gag","listen_name_called","thinking","speaking","claude_channel",
                        "codex_build","dual_agent_ascension","task_success","task_failure",
                        "attention_required","critical_alert","repository_push","run_to_anchor",
                        "dismiss_goodnight","hidden" }) &&
                    ContractIdsMatch(events, "event", new string[] {
                        "runtime.started","user.mentions_nero","nero.thinking","nero.speaking",
                        "claude.started","codex.started","agents.dual_active","task.succeeded",
                        "task.failed","user.action_required","system.critical","git.push_succeeded",
                        "pet.reposition","pet.dismiss","all.work_complete" }) &&
                    eventQueue != null && Convert.ToInt32(eventQueue["maxDepth"]) == MaxQueueDepth &&
                    Convert.ToInt32(eventQueue["coalesceRepeatedEventsWithinMs"]) == CoalesceMilliseconds &&
                    ValidateStateRecords(states) && ValidateEventRecords(events) &&
                    ValidateEventChannel(runtime) && ValidateAssets(root, path);
                if (!_contractValid) {
                    _startupWarning = "Runtime contract mismatch; fallback-only safe mode is active.";
                    UseFallbackFrames();
                }
            } catch {
                _contractValid = false;
                _startupWarning = "Runtime contract unavailable; fallback-only safe mode is active.";
                UseFallbackFrames();
            }
        }

        static bool ContractIdsMatch(IList items, string key, string[] expected)
        {
            if (items == null || items.Count != expected.Length) return false;
            var actual = new HashSet<string>(StringComparer.Ordinal);
            foreach (object item in items) {
                IDictionary record = item as IDictionary;
                string value = record == null ? "" : Convert.ToString(record[key]);
                if (value.Length == 0 || !actual.Add(value)) return false;
            }
            return actual.SetEquals(expected);
        }

        bool ValidateStateRecords(IList items)
        {
            foreach (object item in items) {
                IDictionary record = item as IDictionary; if (record == null) return false;
                string id = Convert.ToString(record["id"]); StateDef definition = null;
                foreach (StateDef candidate in _states.Values)
                    if (StateId(candidate.State) == id) { definition = candidate; break; }
                if (definition == null || !(record["loop"] is bool) ||
                    (bool)record["loop"] != definition.Loop ||
                    Convert.ToInt32(record["fps"]) != definition.Fps ||
                    Convert.ToInt32(record["priority"]) != definition.Priority) return false;
                object duration = record["durationMs"];
                if ((definition.DurationMs == 0 && duration != null) ||
                    (definition.DurationMs != 0 && Convert.ToInt32(duration) != definition.DurationMs)) return false;
                object next = record["next"];
                if ((!definition.Loop && Convert.ToString(next) != StateId(definition.Next)) ||
                    (definition.Loop && next != null)) return false;
            }
            return true;
        }

        bool ValidateEventRecords(IList items)
        {
            foreach (object item in items) {
                IDictionary record = item as IDictionary; if (record == null) return false;
                string name = Convert.ToString(record["event"]); St state;
                if (!_events.TryGetValue(name, out state) ||
                    Convert.ToString(record["state"]) != StateId(state) ||
                    Convert.ToInt32(record["priority"]) !=
                        (name == "all.work_complete" ? 1 : _states[state].Priority)) return false;
            }
            return true;
        }

        bool ValidateAssets(IDictionary root, string contractPath)
        {
            IDictionary assets = root["assets"] as IDictionary;
            IDictionary atlas = assets == null ? null : assets["runtimeAtlas"] as IDictionary;
            IDictionary groups = assets == null ? null : assets["frameGroups"] as IDictionary;
            IDictionary fallbacks = assets == null ? null : assets["fallbackRegistry"] as IDictionary;
            if (atlas == null || groups == null || fallbacks == null ||
                Convert.ToString(assets["basePath"]) != "assets/nero/" ||
                Convert.ToString(atlas["file"]) != "nero-voidcaster-v2.png") return false;
            string atlasPath = Path.Combine(Path.GetDirectoryName(contractPath), "assets", "nero",
                Convert.ToString(atlas["file"]));
            if (!File.Exists(atlasPath) || ComputeSha256(atlasPath) != Convert.ToString(atlas["sha256"])) return false;
            var expectedGroups = new Dictionary<string, int[]> {
                {"idle_breathe", new int[] {0,1,2,3,4,5,6,7,6,5,4,3,2,1}},
                {"attentive", new int[] {8,9,10,11}}, {"action", new int[] {12,13,14,15,14,13}},
                {"thinking", new int[] {11,12,11,10}}
            };
            if (groups.Count != expectedGroups.Count) return false;
            foreach (var pair in expectedGroups) {
                IList values = groups[pair.Key] as IList;
                if (values == null || values.Count != pair.Value.Length) return false;
                for (int i = 0; i < values.Count; i++) if (Convert.ToInt32(values[i]) != pair.Value[i]) return false;
            }
            var missing = new HashSet<string>(StringComparer.Ordinal);
            foreach (StateDef definition in _states.Values) if (definition.MissingArt) missing.Add(StateId(definition.State));
            var declared = new HashSet<string>(StringComparer.Ordinal);
            foreach (object key in fallbacks.Keys) declared.Add(Convert.ToString(key));
            return missing.SetEquals(declared);
        }

        static bool ValidateEventChannel(IDictionary runtime)
        {
            IDictionary channel = runtime == null ? null : runtime["eventChannel"] as IDictionary;
            IList fields = channel == null ? null : channel["envelopeFields"] as IList;
            if (channel == null || fields == null || fields.Count != 4 ||
                Convert.ToString(channel["kind"]) != "ordered-atomic-spool" ||
                Convert.ToString(channel["directory"]) != "runtime/command.d" ||
                Convert.ToInt32(channel["maxPending"]) != 32 ||
                Convert.ToInt32(channel["maxPendingBytes"]) != 16384) return false;
            string[] expected = {"event", "label", "confirmed", "provenance"};
            for (int i = 0; i < expected.Length; i++)
                if (Convert.ToString(fields[i]) != expected[i]) return false;
            return true;
        }

        static string ComputeSha256(string path)
        {
            using (var stream = File.OpenRead(path))
            using (var sha = SHA256.Create())
                return BitConverter.ToString(sha.ComputeHash(stream)).Replace("-", "").ToLowerInvariant();
        }

        void OnSourceInitialized(object sender, EventArgs e)
        {
            IntPtr h = new WindowInteropHelper(this).Handle;
            int ex = GetWindowLong(h, GWL_EXSTYLE) | WS_EX_LAYERED | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE;
            SetWindowLong(h, GWL_EXSTYLE, ex); ApplyClickThrough();
        }

        void ApplyClickThrough()
        {
            IntPtr h = new WindowInteropHelper(this).Handle; if (h == IntPtr.Zero) return;
            int ex = GetWindowLong(h, GWL_EXSTYLE);
            if (_interactive) ex &= ~(WS_EX_TRANSPARENT | WS_EX_NOACTIVATE);
            else ex |= WS_EX_TRANSPARENT | WS_EX_NOACTIVATE;
            SetWindowLong(h, GWL_EXSTYLE, ex);
        }

        void OnMouseDown(object sender, MouseButtonEventArgs e)
        {
            if (!_interactive) return;
            _zoomUntil = DateTime.UtcNow.AddMilliseconds(_reducedMotion ? 80 : 220);
            ApplyCursorPose(true);
            if (e.ClickCount >= 2) { ToggleMission(); return; }
            double beforeLeft = Left, beforeTop = Top;
            try { DragMove(); } catch { }
            bool moved = Math.Abs(Left - beforeLeft) > 4 || Math.Abs(Top - beforeTop) > 4;
            if (moved) {
                double destination = Left;
                double direction = Math.Sign(destination - beforeLeft);
                if (direction == 0) direction = 1;
                _x = destination; _targetX = destination;
                if (!_reducedMotion) Left = destination - direction * 24;
                Receive("pet.reposition", "Moving to a new anchor.");
                _settleAt = DateTime.UtcNow.AddMilliseconds(_reducedMotion ? 80 : 900);
            } else {
                Bubble("I'm here, Toni.", 2600);
            }
        }

        void ApplyCursorPose(bool hovered)
        {
            double zoom = hovered && !_reducedMotion ? 1.05 : 1.0;
            double pointerX = Mouse.GetPosition(this).X;
            _spriteScale.ScaleX = (pointerX < ActualWidth / 2.0 ? -1 : 1) * zoom;
            _spriteScale.ScaleY = zoom;
            if (_effects) _glow.Opacity = hovered ? 0.92 : 0.76;
        }

        void ResetCursorPose()
        {
            _spriteScale.ScaleX = 1; _spriteScale.ScaleY = 1;
        }

        void Tick(object sender, EventArgs e)
        {
            bool suspend = FullscreenAppActive() || BatterySaver();
            if (suspend && Visibility == Visibility.Visible) Visibility = Visibility.Hidden;
            else if (!suspend && !_hidden && _active.State != St.Hidden && Visibility == Visibility.Hidden) Visibility = Visibility.Visible;
            if (suspend || _paused || _hidden) { _timer.Interval = TimeSpan.FromMilliseconds(1000); return; }

            TypeBubble();
            DateTime now = DateTime.UtcNow;
            if (_active.State == St.IdleBreathe && now >= _nextIdleAt) {
                St[] idleStates = { St.IdleLookCursor, St.IdleBoredTailTwirl, St.IdleBananaGag };
                St idle = idleStates[_idleCursor++ % idleStates.Length];
                Activate("idle.scheduler", _states[idle], "");
                if (idle == St.IdleLookCursor) ApplyCursorPose(false);
            }
            if (_active.State == St.Hidden) { Visibility = Visibility.Hidden; _hidden = true; return; }
            if (_active.State == St.BootArrival) {
                double p = Math.Min(1, (DateTime.UtcNow - _activeSince).TotalMilliseconds / 900.0);
                _fade = _reducedMotion ? 1 : p; Opacity = _fade;
            } else if (_active.State == St.DismissGoodnight) {
                double p = Math.Min(1, (DateTime.UtcNow - _activeSince).TotalMilliseconds / 1500.0);
                Opacity = _reducedMotion ? 0 : 1 - p;
            } else Opacity = 1;

            if (_active.State == St.RunToAnchor && !_reducedMotion) {
                double delta = _targetX - Left;
                if (Math.Abs(delta) > 2) Left += Math.Sign(delta) * Math.Min(5, Math.Abs(delta));
            }
            if (_active.State == St.RunToAnchor &&
                (now >= _settleAt || Math.Abs(_targetX - Left) <= 2)) {
                Left = _targetX; _settleAt = DateTime.MaxValue;
                Activate("reposition.settled", _states[St.IdleBreathe], "Settled.");
                DrainQueue();
            }
            if (now >= _zoomUntil && !IsMouseOver) ResetCursorPose();

            if (_active.Frames.Length > 0) {
                int logical = (int)((DateTime.UtcNow - _activeSince).TotalSeconds * _active.Fps);
                int index = _active.Frames[logical % _active.Frames.Length];
                _image.Source = _frames[index] ?? _frames[0];
            } else _image.Source = null;

            if (!_active.Loop && _active.DurationMs > 0 &&
                (DateTime.UtcNow - _activeSince).TotalMilliseconds >= _active.DurationMs) {
                StateDef next = _states[_active.Next];
                Activate("state.completed", next, "");
                DrainQueue();
            }
            PulseEffects();
            _timer.Interval = TimeSpan.FromMilliseconds(Math.Max(40, 1000 / Math.Max(1, _active.Fps)));
        }

        void TypeBubble()
        {
            if (_bubbleTarget.Length == 0) return;
            if (_reducedMotion) { _bubbleText.Text = _bubbleTarget; _bubbleCursor = _bubbleTarget.Length; }
            else if (_bubbleCursor < _bubbleTarget.Length) {
                _typeBudget += 52.0 * _timer.Interval.TotalSeconds;
                int count = Math.Min(_bubbleTarget.Length, _bubbleCursor + (int)_typeBudget);
                _typeBudget -= (int)_typeBudget; _bubbleCursor = count;
                _bubbleText.Text = _bubbleTarget.Substring(0, _bubbleCursor);
            }
            if (_bubbleCursor >= _bubbleTarget.Length && DateTime.UtcNow >= _bubbleUntil)
                _bubble.Visibility = Visibility.Collapsed;
        }

        void PulseEffects()
        {
            if (!_effects) return;
            if (_reducedMotion) {
                _claudeRotate.Angle = 0; _codexRotate.Angle = 0;
                _neroFx.Opacity = 1; _claudeFx.Opacity = 1; _codexFx.Opacity = 1;
                return;
            }
            double elapsed = (DateTime.UtcNow - _activeSince).TotalSeconds;
            double pulse = 0.74 + 0.18 * Math.Sin(elapsed * Math.PI * 2);
            _claudeRotate.Angle = (elapsed * 90) % 360;
            _codexRotate.Angle = -(elapsed * 90) % 360;
            _neroFx.Opacity = pulse; _claudeFx.Opacity = pulse; _codexFx.Opacity = pulse;
        }

        void Receive(string eventName, string label)
        {
            St state;
            if (!_events.TryGetValue(eventName, out state)) return;
            if (!_contractValid && !eventName.Equals("pet.dismiss", StringComparison.OrdinalIgnoreCase)) return;
            DateTime now = DateTime.UtcNow, previous;
            if (_lastEvent.TryGetValue(eventName, out previous) &&
                (now - previous).TotalMilliseconds < CoalesceMilliseconds) return;
            _lastEvent[eventName] = now;
            StateDef definition = _states[state];
            var pending = new PendingEvent { Name = eventName, Label = CleanLabel(label), Definition = definition, Created = now };
            bool dismiss = state == St.DismissGoodnight;
            bool complete = state == St.IdleBreathe &&
                eventName.Equals("all.work_complete", StringComparison.OrdinalIgnoreCase);
            if (dismiss) {
                _queue.Clear();
                Activate(pending.Name, pending.Definition, pending.Label);
                return;
            }
            if (complete) {
                if (_active != null && IsLatchedAlert(_active.State)) {
                    Bubble("Alert remains latched. Use Clear active alert after acknowledgement.", 3600);
                    return;
                }
                _queue.Clear();
                Activate(pending.Name, pending.Definition, pending.Label);
                return;
            }
            if (_active != null && IsLatchedAlert(_active.State)) {
                if (IsLatchedAlert(state) && definition.Priority > _active.Priority)
                    Activate(pending.Name, pending.Definition, pending.Label);
                else QueuePending(pending);
                return;
            }
            if (_active == null || _active.State == St.IdleBreathe ||
                definition.Priority > _active.Priority) {
                Activate(pending.Name, pending.Definition, pending.Label);
            } else QueuePending(pending);
        }

        void QueuePending(PendingEvent pending)
        {
            if (_queue.Count >= MaxQueueDepth) {
                _queue.Sort(delegate(PendingEvent a, PendingEvent b) {
                    int byPriority = a.Definition.Priority.CompareTo(b.Definition.Priority);
                    return byPriority != 0 ? byPriority : b.Created.CompareTo(a.Created);
                });
                if (pending.Definition.Priority <= _queue[0].Definition.Priority) return;
                _queue.RemoveAt(0);
            }
            _queue.Add(pending);
        }

        static bool IsLatchedAlert(St state)
        {
            return state == St.CriticalAlert || state == St.AttentionRequired || state == St.TaskFailure;
        }

        void ClearLatchedAlert()
        {
            if (_active == null || !IsLatchedAlert(_active.State)) {
                Bubble("No active alert to clear.", 2200);
                return;
            }
            Activate("alert.cleared", _states[St.IdleBreathe], "Alert acknowledged.");
            DrainQueue();
        }

        void Activate(string eventName, StateDef definition, string label)
        {
            _activeEvent = eventName; _active = definition; _activeSince = DateTime.UtcNow;
            _hidden = definition.State == St.Hidden;
            _stateBadge.Text = StateId(definition.State);
            _missionState.Text = "State: " + StateId(definition.State);
            _missionDetail.Text = "Event: " + eventName + (definition.MissingArt ? "\nArt fallback: idle_breathe" : "");
            AutomationProperties.SetName(_root, definition.AccessibleLabel);
            AnnounceState(definition.AccessibleLabel);
            if (definition.State == St.IdleBreathe)
            {
                _nextIdleAt = DateTime.UtcNow.AddSeconds(_reducedMotion ? 18 : 10);
                if (!IsMouseOver) ResetCursorPose();
            }
            else if (definition.State != St.IdleLookCursor &&
                     definition.State != St.IdleBoredTailTwirl &&
                     definition.State != St.IdleBananaGag)
                _nextIdleAt = DateTime.MaxValue;
            ApplyVisualState();
            if (!String.IsNullOrWhiteSpace(label)) Bubble(label, definition.Loop ? 4500 : Math.Max(1800, definition.DurationMs));
            if (definition.State == St.Hidden) Visibility = Visibility.Hidden;
            else { Visibility = Visibility.Visible; _hidden = false; }
        }

        void AnnounceState(string label)
        {
            _screenReaderStatus.Text = label;
            AutomationProperties.SetName(_screenReaderStatus, label);
            try {
                AutomationPeer peer = UIElementAutomationPeer.FromElement(_screenReaderStatus);
                if (peer == null) peer = UIElementAutomationPeer.CreatePeerForElement(_screenReaderStatus);
                if (peer != null) peer.RaiseAutomationEvent(AutomationEvents.LiveRegionChanged);
            } catch { }
        }

        void DrainQueue()
        {
            if (_queue.Count == 0) return;
            _queue.Sort(delegate(PendingEvent a, PendingEvent b) {
                int byPriority = b.Definition.Priority.CompareTo(a.Definition.Priority);
                return byPriority != 0 ? byPriority : a.Created.CompareTo(b.Created);
            });
            PendingEvent next = _queue[0];
            if (_active != null && _active.State != St.IdleBreathe &&
                next.Definition.Priority < _active.Priority) return;
            _queue.RemoveAt(0);
            Activate(next.Name, next.Definition, next.Label);
        }

        void ApplyVisualState()
        {
            bool claude = _active != null && (_active.State == St.ClaudeChannel || _active.State == St.DualAgentAscension);
            bool codex = _active != null && (_active.State == St.CodexBuild || _active.State == St.DualAgentAscension || _active.State == St.RepositoryPush);
            _claudeFx.Visibility = claude ? Visibility.Visible : Visibility.Collapsed;
            _codexFx.Visibility = codex ? Visibility.Visible : Visibility.Collapsed;
            _neroFx.Visibility = _active != null && _active.State != St.Hidden ? Visibility.Visible : Visibility.Collapsed;
            bool risk = _active != null && (_active.State == St.CriticalAlert || _active.State == St.TaskFailure || _active.State == St.AttentionRequired);
            _stateBadge.Foreground = new SolidColorBrush(risk ? Color.FromRgb(255, 125, 137) : Color.FromRgb(223, 215, 242));
            _glow.Color = risk ? Color.FromRgb(255, 70, 100) : Color.FromRgb(181, 51, 255);
            _glow.BlurRadius = _reducedMotion ? 14 : (_active != null && _active.Priority >= 60 ? 34 : 24);
            _glow.Opacity = _effects ? 0.76 : 0;
        }

        static string StateId(St state)
        {
            switch (state) {
                case St.BootArrival: return "boot_arrival"; case St.IdleBreathe: return "idle_breathe";
                case St.IdleLookCursor: return "idle_look_cursor"; case St.IdleBoredTailTwirl: return "idle_bored_tail_twirl";
                case St.IdleBananaGag: return "idle_banana_gag"; case St.ListenNameCalled: return "listen_name_called";
                case St.Thinking: return "thinking"; case St.Speaking: return "speaking";
                case St.ClaudeChannel: return "claude_channel"; case St.CodexBuild: return "codex_build";
                case St.DualAgentAscension: return "dual_agent_ascension"; case St.TaskSuccess: return "task_success";
                case St.TaskFailure: return "task_failure"; case St.AttentionRequired: return "attention_required";
                case St.CriticalAlert: return "critical_alert"; case St.RepositoryPush: return "repository_push";
                case St.RunToAnchor: return "run_to_anchor"; case St.DismissGoodnight: return "dismiss_goodnight";
                default: return "hidden";
            }
        }

        static string CleanLabel(string text)
        {
            if (text == null) return "";
            text = text.Replace("\r", " ").Replace("\n", " ").Replace("\0", " ").Trim();
            return text.Length > 160 ? text.Substring(0, 160) : text;
        }

        void Bubble(string text, int milliseconds)
        {
            _bubbleTarget = CleanLabel(text); _bubbleCursor = 0; _typeBudget = 0;
            _bubbleText.Text = _reducedMotion ? _bubbleTarget : "";
            if (_reducedMotion) _bubbleCursor = _bubbleTarget.Length;
            _bubbleUntil = DateTime.UtcNow.AddMilliseconds(milliseconds);
            _bubble.Visibility = _bubbleTarget.Length == 0 ? Visibility.Collapsed : Visibility.Visible;
        }

        void ToggleMission()
        {
            _missionOpen = !_missionOpen;
            _mission.Visibility = _missionOpen ? Visibility.Visible : Visibility.Collapsed;
            _root.ColumnDefinitions[0].Width = new GridLength(_missionOpen ? 310 : 0);
            ApplyDisplayScale(_displayScale);
            var work = SystemParameters.WorkArea;
            if (Left + Width > work.Right) Left = Math.Max(work.Left, work.Right - Width - 8);
        }

        void ApplyDisplayScale(int scale)
        {
            _displayScale = Math.Max(1, Math.Min(3, scale));
            _character.LayoutTransform = new ScaleTransform(_displayScale, _displayScale);
            if (_root.ColumnDefinitions.Count > 1)
                _root.ColumnDefinitions[1].Width = new GridLength(CellWidth * _displayScale);
            Width = CellWidth * _displayScale + (_missionOpen ? 310 : 0);
            Height = Math.Max(300, CellHeight * _displayScale);
            RenderOptions.SetBitmapScalingMode(_image, BitmapScalingMode.NearestNeighbor);
            var work = SystemParameters.WorkArea;
            if (Left + Width > work.Right) Left = Math.Max(work.Left, work.Right - Width - 8);
            if (Top + Height > work.Bottom) Top = Math.Max(work.Top, work.Bottom - Height - 8);
        }

        bool FullscreenAppActive()
        {
            IntPtr foreground = GetForegroundWindow(); IntPtr self = new WindowInteropHelper(this).Handle;
            if (foreground == IntPtr.Zero || foreground == self) return false;
            RECT rect; if (!GetWindowRect(foreground, out rect)) return false;
            return (rect.R - rect.L) >= SystemParameters.PrimaryScreenWidth - 2 &&
                   (rect.B - rect.T) >= SystemParameters.PrimaryScreenHeight - 2;
        }
        bool BatterySaver() { SPS status; return GetSystemPowerStatus(out status) && status.flag == 1; }

        void SetupWatcher()
        {
            try {
                _watch = new FileSystemWatcher(_eventDir, "*.cmd");
                _watch.NotifyFilter = NotifyFilters.LastWrite | NotifyFilters.CreationTime | NotifyFilters.FileName;
                _watch.Changed += OnCommand; _watch.Created += OnCommand; _watch.Renamed += OnCommand;
                _watch.EnableRaisingEvents = true;
                DrainEventSpool();
            } catch (Exception ex) {
                _missionDetail.Text = "IPC unavailable: " + CleanLabel(ex.Message);
                Bubble("Familiar event channel is unavailable.", 5000);
            }
        }

        void OnCommand(object sender, FileSystemEventArgs e)
        {
            DrainEventSpool();
        }

        void DrainEventSpool()
        {
            lock (_spoolLock) {
                string[] paths;
                try { paths = Directory.GetFiles(_eventDir, "*.cmd"); }
                catch { return; }
                Array.Sort(paths, StringComparer.Ordinal);
                foreach (string path in paths) ProcessEventFile(path);
            }
        }

        void ProcessEventFile(string path)
        {
            string raw = "";
            try {
                System.Threading.Thread.Sleep(15);
                raw = File.ReadAllText(path).Trim();
            } catch { return; }
            if (raw.Length == 0 || raw.Length > 1024 || raw.IndexOfAny(new char[] {'\r','\n','\0'}) >= 0) {
                QuarantineEnvelope(path); return;
            }
            bool accepted = false;
            try {
                if (Dispatcher.CheckAccess()) accepted = DispatchEnvelope(raw);
                else accepted = (bool)Dispatcher.Invoke(
                    new Func<bool>(delegate { return DispatchEnvelope(raw); }));
            } catch { accepted = false; }
            if (accepted) { try { File.Delete(path); } catch { } }
            else QuarantineEnvelope(path);
        }

        void QuarantineEnvelope(string path)
        {
            try {
                string destination = path + ".bad";
                if (File.Exists(destination)) destination += "." + Guid.NewGuid().ToString("N");
                File.Move(path, destination);
                _missionDetail.Text = "Rejected event envelope: " + Path.GetFileName(destination);
            } catch { }
        }

        bool DispatchEnvelope(string raw)
        {
            IDictionary envelope;
            try { envelope = new JavaScriptSerializer().DeserializeObject(raw) as IDictionary; }
            catch { return false; }
            if (envelope == null || envelope.Count != 4 ||
                !envelope.Contains("event") || !envelope.Contains("label") ||
                !envelope.Contains("confirmed") || !envelope.Contains("provenance")) return false;
            string eventName = envelope["event"] as string;
            string label = envelope["label"] as string;
            string provenance = envelope["provenance"] as string;
            if (eventName == null || label == null || provenance == null ||
                !(envelope["confirmed"] is bool) || !_events.ContainsKey(eventName) ||
                CleanLabel(label) != label) return false;
            bool confirmed = (bool)envelope["confirmed"];
            bool authoritativeSuccess = eventName == "task.succeeded" || eventName == "git.push_succeeded";
            bool validProvenance = provenance.Length > 0 && provenance.Length <= 160 &&
                CleanLabel(provenance) == provenance;
            if (authoritativeSuccess && (!confirmed || !validProvenance)) return false;
            if (!authoritativeSuccess && (confirmed || provenance.Length != 0)) return false;
            Receive(eventName, label);
            return true;
        }

        void BuildTray()
        {
            _tray = new WinForms.NotifyIcon { Text = "Nero — Void Guardian", Visible = true, Icon = MakeIcon() };
            var menu = new WinForms.ContextMenuStrip();
            var mission = new WinForms.ToolStripMenuItem("Mission Control"); mission.Click += delegate { ToggleMission(); };
            var pause = new WinForms.ToolStripMenuItem("Pause"); pause.Click += delegate { _paused = !_paused; pause.Text = _paused ? "Resume" : "Pause"; };
            var clear = new WinForms.ToolStripMenuItem("Clear active alert"); clear.Click += delegate { ClearLatchedAlert(); };
            var interactive = new WinForms.ToolStripMenuItem("Interactive"); interactive.CheckOnClick = true;
            interactive.Click += delegate { _interactive = interactive.Checked; ApplyClickThrough(); };
            var reduced = new WinForms.ToolStripMenuItem("Reduced motion"); reduced.CheckOnClick = true; reduced.Checked = _reducedMotion;
            reduced.Click += delegate { _reducedMotion = reduced.Checked; ApplyVisualState(); SaveSettings(); };
            var scale = new WinForms.ToolStripMenuItem("Scale");
            for (int value = 1; value <= 3; value++) {
                int selected = value;
                var item = new WinForms.ToolStripMenuItem(value + "x");
                item.Click += delegate { ApplyDisplayScale(selected); SaveSettings(); };
                scale.DropDownItems.Add(item);
            }
            var hide = new WinForms.ToolStripMenuItem("Dismiss"); hide.Click += delegate { Receive("pet.dismiss", "Goodnight."); };
            var exit = new WinForms.ToolStripMenuItem("Exit"); exit.Click += delegate { Shutdown(); };
            menu.Items.AddRange(new WinForms.ToolStripItem[] { mission, pause, clear, interactive, reduced, scale, hide, new WinForms.ToolStripSeparator(), exit });
            _tray.ContextMenuStrip = menu;
            _tray.MouseDoubleClick += delegate {
                _hidden = false; Visibility = Visibility.Visible;
                if (_contractValid) Receive("runtime.started", "Welcome back.");
                else Activate("safe-mode.restart", _states[St.BootArrival], _startupWarning);
            };
        }

        Drawing.Icon MakeIcon()
        {
            var bitmap = new Drawing.Bitmap(32, 32);
            using (var graphics = Drawing.Graphics.FromImage(bitmap)) {
                graphics.SmoothingMode = Drawing.Drawing2D.SmoothingMode.AntiAlias;
                graphics.Clear(Drawing.Color.Transparent);
                var black = new Drawing.SolidBrush(Drawing.Color.FromArgb(245, 8, 8, 15));
                var magenta = new Drawing.SolidBrush(Drawing.Color.FromArgb(255, 255, 45, 170));
                var violet = new Drawing.SolidBrush(Drawing.Color.FromArgb(255, 181, 51, 255));
                graphics.FillEllipse(black, 3, 3, 26, 26);
                graphics.FillPolygon(magenta, new Drawing.Point[] { new Drawing.Point(16,5), new Drawing.Point(25,16), new Drawing.Point(16,27), new Drawing.Point(7,16) });
                graphics.FillEllipse(violet, 12, 12, 8, 8);
                black.Dispose(); magenta.Dispose(); violet.Dispose();
            }
            return Drawing.Icon.FromHandle(bitmap.GetHicon());
        }

        void LoadSettings()
        {
            try {
                if (!File.Exists(_settingsFile)) return;
                foreach (string line in File.ReadAllLines(_settingsFile)) {
                    if (line == "effects=0") _effects = false;
                    if (line == "reduced_motion=1") _reducedMotion = true;
                    if (line.StartsWith("scale=", StringComparison.Ordinal)) {
                        int parsed;
                        if (Int32.TryParse(line.Substring(6), out parsed))
                            _displayScale = Math.Max(1, Math.Min(3, parsed));
                    }
                }
            } catch { }
            ApplyVisualState();
        }

        void SaveSettings()
        {
            try {
                File.WriteAllText(_settingsFile,
                    "effects=" + (_effects ? "1" : "0") +
                    "\nreduced_motion=" + (_reducedMotion ? "1" : "0") +
                    "\nscale=" + _displayScale + "\nautostart=0\n");
            } catch { }
        }

        void Shutdown()
        {
            SaveSettings();
            try { if (_watch != null) { _watch.EnableRaisingEvents = false; _watch.Dispose(); } } catch { }
            _timer.Stop();
            try { if (_tray != null) { _tray.Visible = false; _tray.Dispose(); } } catch { }
            Application.Current.Shutdown();
        }

        protected override void OnClosed(EventArgs e)
        {
            try { if (_tray != null) { _tray.Visible = false; _tray.Dispose(); } } catch { }
            base.OnClosed(e);
        }
    }

    public static class Program
    {
        [STAThread]
        public static void Main()
        {
            bool createdNew;
            using (var singleInstance = new Mutex(true, "Local\\Nero.VoidGuardian.DesktopFamiliar.v2", out createdNew)) {
                if (!createdNew) return;
                try {
                    var app = new Application { ShutdownMode = ShutdownMode.OnExplicitShutdown };
                    var window = new FamiliarWindow(); window.Show(); app.Run();
                } finally {
                    try { singleInstance.ReleaseMutex(); } catch { }
                }
            }
        }
    }
}
