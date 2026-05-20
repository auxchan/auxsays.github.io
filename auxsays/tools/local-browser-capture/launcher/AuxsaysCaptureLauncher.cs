using System;
using System.Diagnostics;
using System.IO;
using System.Windows.Forms;

namespace AuxsaysCaptureLauncher
{
    internal static class Program
    {
        [STAThread]
        private static void Main()
        {
            string launcherDir = AppDomain.CurrentDomain.BaseDirectory;
            string scriptPath = Path.Combine(launcherDir, "AuxsaysCaptureLauncher.ps1");
            string powershellPath = Path.Combine(
                Environment.GetFolderPath(Environment.SpecialFolder.Windows),
                "System32",
                "WindowsPowerShell",
                "v1.0",
                "powershell.exe"
            );

            if (!File.Exists(scriptPath))
            {
                MessageBox.Show(
                    "Could not find AuxsaysCaptureLauncher.ps1 next to this EXE.",
                    "AUXSAYS Capture Launcher",
                    MessageBoxButtons.OK,
                    MessageBoxIcon.Error
                );
                return;
            }

            if (!File.Exists(powershellPath))
            {
                powershellPath = "powershell.exe";
            }

            ProcessStartInfo info = new ProcessStartInfo();
            info.FileName = powershellPath;
            info.Arguments = "-NoProfile -ExecutionPolicy Bypass -File " + Quote(scriptPath);
            info.WorkingDirectory = launcherDir;
            info.UseShellExecute = false;
            info.CreateNoWindow = true;

            try
            {
                Process.Start(info);
            }
            catch (Exception ex)
            {
                MessageBox.Show(
                    ex.Message,
                    "AUXSAYS Capture Launcher",
                    MessageBoxButtons.OK,
                    MessageBoxIcon.Error
                );
            }
        }

        private static string Quote(string value)
        {
            return "\"" + value.Replace("\"", "\\\"") + "\"";
        }
    }
}
