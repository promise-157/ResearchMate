using System.Runtime.InteropServices;

namespace ResearchMate.WindowsWslHost;

internal static class ShortcutIconManager
{
    internal const long MaximumIconBytes = 5 * 1024 * 1024;

    internal static string CustomIconPath => Path.Combine(
        Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
        "ResearchMate",
        "shortcut-icon.ico");

    internal static string ShortcutPath => Path.Combine(
        Environment.GetFolderPath(Environment.SpecialFolder.DesktopDirectory),
        "ResearchMate.lnk");

    internal static void ValidateIcon(string sourcePath)
    {
        if (!string.Equals(Path.GetExtension(sourcePath), ".ico", StringComparison.OrdinalIgnoreCase))
        {
            throw new InvalidDataException("只支持 .ico 图标文件");
        }
        var info = new FileInfo(sourcePath);
        if (!info.Exists)
        {
            throw new FileNotFoundException("所选图标文件不存在", sourcePath);
        }
        if (info.Length is < 6 or > MaximumIconBytes)
        {
            throw new InvalidDataException("ICO 文件必须大于 6 字节且不超过 5 MiB");
        }
        Span<byte> header = stackalloc byte[6];
        using var stream = File.OpenRead(sourcePath);
        if (stream.Read(header) != header.Length ||
            header[0] != 0 || header[1] != 0 || header[2] != 1 || header[3] != 0)
        {
            throw new InvalidDataException("所选文件不是有效的 Windows ICO");
        }
        var imageCount = BitConverter.ToUInt16(header[4..]);
        if (imageCount is 0 or > 256 || info.Length < 6 + (16L * imageCount))
        {
            throw new InvalidDataException("ICO 图像目录无效");
        }
        var entries = new byte[16 * imageCount];
        if (stream.Read(entries) != entries.Length)
        {
            throw new InvalidDataException("ICO 图像目录不完整");
        }
        for (var index = 0; index < imageCount; index++)
        {
            var entry = entries.AsSpan(index * 16, 16);
            var imageBytes = BitConverter.ToUInt32(entry[8..12]);
            var imageOffset = BitConverter.ToUInt32(entry[12..16]);
            if (imageBytes == 0 || imageOffset < 6 + entries.Length ||
                imageOffset + (ulong)imageBytes > (ulong)info.Length)
            {
                throw new InvalidDataException("ICO 图像数据范围无效");
            }
        }
    }

    internal static string ApplyCustomIcon(string sourcePath)
    {
        ValidateIcon(sourcePath);
        if (!File.Exists(ShortcutPath))
        {
            throw new FileNotFoundException("未找到 ResearchMate 桌面快捷方式", ShortcutPath);
        }
        Directory.CreateDirectory(Path.GetDirectoryName(CustomIconPath)!);
        var temporaryPath = CustomIconPath + ".new";
        File.Copy(sourcePath, temporaryPath, overwrite: true);
        File.Move(temporaryPath, CustomIconPath, overwrite: true);
        SetShortcutIcon(CustomIconPath);
        return CustomIconPath;
    }

    internal static void RestoreDefaultIcon()
    {
        if (!File.Exists(ShortcutPath))
        {
            throw new FileNotFoundException("未找到 ResearchMate 桌面快捷方式", ShortcutPath);
        }
        SetShortcutIcon(Application.ExecutablePath);
        if (File.Exists(CustomIconPath))
        {
            File.Delete(CustomIconPath);
        }
    }

    private static void SetShortcutIcon(string iconPath)
    {
        var shellLinkType = Type.GetTypeFromCLSID(
            new Guid("00021401-0000-0000-C000-000000000046"),
            throwOnError: true)!;
        var shellLink = (IShellLinkW)Activator.CreateInstance(shellLinkType)!;
        var persistFile = (IPersistFile)shellLink;
        try
        {
            persistFile.Load(ShortcutPath, 0);
            shellLink.SetIconLocation(iconPath, 0);
            persistFile.Save(ShortcutPath, true);
        }
        finally
        {
            Marshal.FinalReleaseComObject(shellLink);
        }
    }

    [ComImport]
    [InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
    [Guid("000214F9-0000-0000-C000-000000000046")]
    private interface IShellLinkW
    {
        void GetPath(IntPtr file, int maximumPath, IntPtr data, uint flags);
        void GetIDList(out IntPtr itemIdList);
        void SetIDList(IntPtr itemIdList);
        void GetDescription(IntPtr name, int maximumName);
        void SetDescription([MarshalAs(UnmanagedType.LPWStr)] string name);
        void GetWorkingDirectory(IntPtr directory, int maximumPath);
        void SetWorkingDirectory([MarshalAs(UnmanagedType.LPWStr)] string directory);
        void GetArguments(IntPtr arguments, int maximumPath);
        void SetArguments([MarshalAs(UnmanagedType.LPWStr)] string arguments);
        void GetHotkey(out short hotkey);
        void SetHotkey(short hotkey);
        void GetShowCmd(out int showCommand);
        void SetShowCmd(int showCommand);
        void GetIconLocation(IntPtr iconPath, int iconPathLength, out int iconIndex);
        void SetIconLocation([MarshalAs(UnmanagedType.LPWStr)] string iconPath, int iconIndex);
        void SetRelativePath([MarshalAs(UnmanagedType.LPWStr)] string path, uint reserved);
        void Resolve(IntPtr windowHandle, uint flags);
        void SetPath([MarshalAs(UnmanagedType.LPWStr)] string path);
    }

    [ComImport]
    [InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
    [Guid("0000010B-0000-0000-C000-000000000046")]
    private interface IPersistFile
    {
        void GetClassID(out Guid classId);
        [PreserveSig]
        int IsDirty();
        void Load([MarshalAs(UnmanagedType.LPWStr)] string fileName, uint mode);
        void Save([MarshalAs(UnmanagedType.LPWStr)] string fileName, bool remember);
        void SaveCompleted([MarshalAs(UnmanagedType.LPWStr)] string fileName);
        void GetCurFile([MarshalAs(UnmanagedType.LPWStr)] out string fileName);
    }
}
