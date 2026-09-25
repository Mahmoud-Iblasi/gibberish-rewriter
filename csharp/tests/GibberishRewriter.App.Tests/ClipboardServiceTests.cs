using GibberishRewriter.App.Win;
using static GibberishRewriter.App.Win.NativeMethods;

namespace GibberishRewriter.App.Tests;

public class ClipboardServiceTests
{
    [Theory]
    [InlineData(13u, true)]      // CF_UNICODETEXT
    [InlineData(8u, true)]       // CF_DIB
    [InlineData(15u, true)]      // CF_HDROP (file lists)
    [InlineData(0xC0F0u, true)]  // a registered format, such as "HTML Format"
    [InlineData(2u, false)]      // CF_BITMAP
    [InlineData(3u, false)]      // CF_METAFILEPICT
    [InlineData(9u, false)]      // CF_PALETTE
    [InlineData(14u, false)]     // CF_ENHMETAFILE
    [InlineData(0x80u, false)]   // CF_OWNERDISPLAY
    [InlineData(0x8Eu, false)]   // CF_DSPENHMETAFILE
    [InlineData(0x200u, false)]  // CF_PRIVATEFIRST
    [InlineData(0x3FFu, false)]  // CF_GDIOBJLAST
    public void IsMemoryFormat_skips_GDI_and_private_formats(uint format, bool expected) =>
        Assert.Equal(expected, ClipboardService.IsMemoryFormat(format));

    [IntegrationFact]
    public void Text_and_an_image_survive_save_set_text_and_restore()
    {
        using var owner = new OwnerThread();
        var clipboard = new ClipboardService(() => owner.Handle, _ => { }, Thread.Sleep);
        var usersClipboard = clipboard.Save();
        try
        {
            TestThreads.OnSta(() =>
            {
                using var image = new Bitmap(3, 2);
                var data = new DataObject();
                data.SetText("Gibberish Rewriter clipboard test");
                data.SetImage(image);
                Clipboard.SetDataObject(data, copy: true);
                return true;
            });
            var saved = clipboard.Save();

            clipboard.SetText("converted");
            Assert.Equal("converted", clipboard.ReadText());
            Assert.True(IsClipboardFormatAvailable(RegisterClipboardFormat("CanIncludeInClipboardHistory")));

            clipboard.Restore(saved);
            Assert.Equal("Gibberish Rewriter clipboard test", clipboard.ReadText());
            Assert.Equal(new Size(3, 2), TestThreads.OnSta(() => Clipboard.GetImage()?.Size));
        }
        finally
        {
            clipboard.Restore(usersClipboard);
        }
    }
}
